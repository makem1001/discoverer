"""
发现者（Discoverer）— LLM 服务封装

负责：
  1. 自然语言策略解析（NL → 结构化 Strategy）
  2. 回测结果 AI 解读
  3. 策略体检报告生成

使用 DeepSeek API（兼容 OpenAI SDK），支持通过环境变量切换模型。

P0-4 增强：
  - parse_strategy() 增加重试（2次，间隔500ms）+ timeout=10
  - _validate_parsed_strategy() 校验信号有效性
  - _auto_fix_strategy() 自动修复解析错误
"""

from __future__ import annotations

import json
import logging
import time
import asyncio
from typing import Optional, List

from openai import OpenAI

from config import (
    LLM_API_KEY, LLM_BASE_URL, LLM_MODEL,
    LLM_PARSE_TEMPERATURE, LLM_INTERPRET_TEMPERATURE,
)
from models.schemas import (
    ParseResult, InterpretResult, Strategy, SignalCondition, HoldingRule,
)
from models.signals import ALL_SIGNALS, ALL_HOLDING_RULES, get_signal_by_id, get_holding_rule_by_id

logger = logging.getLogger("discoverer.llm")

# ══════════════════════════════════════════════════════════════════
# 风险免责声明
# ══════════════════════════════════════════════════════════════════

RISK_DISCLAIMER = "\n\n⚠️ 风险提示：以上分析基于历史数据回测，历史表现不代表未来收益。本平台所有内容仅供学习研究，不构成任何投资建议。投资有风险，入市需谨慎。"


# ══════════════════════════════════════════════════════════════════
# Prompt 模板
# ══════════════════════════════════════════════════════════════════

PARSE_SYSTEM_PROMPT = """你是一个专业的A股量化策略解析助手。你的任务是将用户用自然语言描述的股票交易策略，精确地映射到已知的技术信号和持有规则。

## 可用信号列表（共69个）：
{signals_list}

## 可用持有规则（共8个）：
{holding_rules_list}

## 输出要求
你必须输出严格的JSON格式，结构如下：
```json
{{
  "entry_conditions": [
    {{"signal_id": "信号ID", "operator": "trigger|cross_above|cross_below|gt|lt", "threshold": 0.0}}
  ],
  "exit_conditions": [
    {{"signal_id": "信号ID", "operator": "trigger|cross_above|cross_below|gt|lt", "threshold": 0.0}}
  ],
  "holding_rule_id": "持有规则ID（可为null）",
  "explanation": "用通俗易懂的中文解释你如何理解用户的策略，以及映射到了哪些信号",
  "warnings": ["任何需要注意的警告信息"],
  "confidence": 0.0-1.0之间的数字，表示你对解析结果的信心
}}
```

## 解析规则
1. 优先匹配信号名称、别名、常见说法
2. 如果用户提到了参数（如"站上10日线"），提取到params中
3. 如果用户没有提到卖出条件，默认使用"next_signal_reverse"作为持有规则
4. 多个条件之间默认为AND关系
5. 如果无法匹配任何信号，confidence应该很低，并在warnings中说明
6. 仅返回JSON，不要有其他内容

【合规要求】禁止在解析结果中使用"建议买入"、"建议卖出"、"推荐"等诱导性措辞。输出应客观描述信号含义和统计表现。
"""

INTERPRET_SYSTEM_PROMPT = """你是一位资深的A股量化分析师。请根据回测结果数据，生成专业、通俗易懂的中文解读报告。

## 输出要求
请以JSON格式输出，包含以下字段：
```json
{{
  "summary": "策略整体表现总结（2-3句话）",
  "risk_analysis": "风险分析：最大回撤、胜率、盈亏比等角度（2-3句话）",
  "benchmark_comparison": "与市场基准对比（如沪深300长期年化约7-8%）（1-2句话）",
  "suggestion": "改进建议或注意事项（1-2句话）"
}}
```

## 风格要求
- 语言通俗易懂，面向普通股民
- 数据引用要准确
- 不要过度乐观或悲观，客观中立
- 必须提醒"历史表现不代表未来收益"

【合规要求】禁止给出任何买卖建议或投资建议。使用"信号提示"代替"建议"，使用"历史表现"代替"推荐"。
"""

CHECKUP_SYSTEM_PROMPT = """你是一位严谨的量化策略检验分析师。请根据策略体检数据，生成一份"体检报告"。

## 输出要求
生成一段300字以内的中文体检报告，包含：
1. 信号组合在过去的表现总结
2. 策略的可靠性评估（触发频率、胜率稳定性）
3. 适用市场环境的判断
4. 风险提示

## 风格
- 像医生写体检报告：客观、准确、有依据
- 用数据说话
- 必须包含"历史表现不代表未来收益"的提醒

【合规要求】禁止给出投资建议。报告应以"历史数据回测显示"开头，强调历史表现不代表未来收益。
"""

# ══════════════════════════════════════════════════════════════════
# 已知有效信号ID集合（用于校验）
# ══════════════════════════════════════════════════════════════════

_VALID_SIGNAL_IDS: set = {s.id for s in ALL_SIGNALS}


class LLMService:
    """LLM服务：自然语言解析 + AI解读"""

    def __init__(self):
        self.client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
        )
        self.model = LLM_MODEL

    # ── 自然语言解析（P0-4 增强版：重试 + 超时 + 校验 + 自动修复）─────

    def parse_strategy(self, natural_language: str, stock_code: str = "") -> ParseResult:
        """将自然语言策略描述解析为结构化 Strategy（同步版本，保持向后兼容）。

        Args:
            natural_language: 用户白话描述
            stock_code: 关联股票代码

        Returns:
            ParseResult
        """
        max_retries = 2
        last_error = ""

        for attempt in range(max_retries + 1):
            try:
                # 调用 LLM API（带超时保护，通过 signal alarm）
                response = self._call_llm_parse_with_timeout(
                    natural_language, stock_code, timeout=10.0
                )

                if response is None:
                    last_error = "LLM API 超时"
                    if attempt < max_retries:
                        time.sleep(0.5)
                        continue
                    return ParseResult(
                        success=False,
                        parse_level="llm",
                        error_message=f"LLM 解析失败: {last_error}",
                    )

                # 提取和校验
                parsed = self._extract_json(response)
                if parsed is None:
                    last_error = "LLM返回格式异常，无法解析"
                    if attempt < max_retries:
                        time.sleep(0.5)
                        continue
                    return ParseResult(
                        success=False,
                        explanation="LLM返回格式异常，无法解析",
                        warnings=["解析失败，请尝试更简洁清晰的描述"],
                        parse_level="llm",
                    )

                errors = self._validate_parsed_strategy(parsed)
                if not errors:
                    # 校验通过，直接构建
                    return self._build_parse_result(parsed, natural_language, stock_code)

                # 自动修复
                if attempt == 0:
                    parsed = self._auto_fix_strategy(parsed, errors)
                    result = self._build_parse_result(parsed, natural_language, stock_code)
                    result.warnings.append(f"自动修复: {'; '.join(errors)}")
                    return result
                else:
                    last_error = "; ".join(errors)

            except Exception as e:
                last_error = str(e)
                logger.warning(f"LLM 解析尝试 {attempt + 1}/{max_retries + 1} 失败: {e}")

            if attempt < max_retries:
                time.sleep(0.5)

        # 所有重试失败
        return ParseResult(
            success=False,
            parse_level="llm",
            explanation="",
            warnings=[f"LLM调用失败: {last_error}"],
            error_message=f"LLM 解析失败: {last_error}",
        )

    async def parse_strategy_async(self, natural_language: str, stock_code: str = "") -> ParseResult:
        """异步版本的策略解析（含重试和超时）。

        Args:
            natural_language: 用户白话描述
            stock_code: 关联股票代码

        Returns:
            ParseResult
        """
        max_retries = 2
        last_error = ""

        for attempt in range(max_retries + 1):
            try:
                # 构建信号列表描述
                signals_desc = self._build_signals_description()
                holding_desc = self._build_holding_rules_description()

                system_prompt = PARSE_SYSTEM_PROMPT.format(
                    signals_list=signals_desc,
                    holding_rules_list=holding_desc,
                )

                user_prompt = f"请解析以下策略描述：\n{natural_language}"

                # 超时 10 秒
                response = await asyncio.wait_for(
                    self._call_llm_api_async(system_prompt, user_prompt),
                    timeout=10.0,
                )

                content = response or ""
                parsed = self._extract_json(content)

                if parsed is None:
                    last_error = "LLM返回格式异常，无法解析"
                    if attempt < max_retries:
                        await asyncio.sleep(0.5)
                        continue
                    return ParseResult(
                        success=False,
                        explanation="LLM返回格式异常，无法解析",
                        warnings=["解析失败，请尝试更简洁清晰的描述"],
                        parse_level="llm",
                    )

                # 校验
                errors = self._validate_parsed_strategy(parsed)
                if not errors:
                    return self._build_parse_result(parsed, natural_language, stock_code)

                # 自动修复
                if attempt == 0:
                    parsed = self._auto_fix_strategy(parsed, errors)
                    result = self._build_parse_result(parsed, natural_language, stock_code)
                    result.warnings.append(f"自动修复: {'; '.join(errors)}")
                    return result
                else:
                    last_error = "; ".join(errors)

            except asyncio.TimeoutError:
                last_error = "LLM API 超时"
            except Exception as e:
                last_error = str(e)

            if attempt < max_retries:
                await asyncio.sleep(0.5)

        # 所有重试失败
        return ParseResult(
            success=False,
            parse_level="llm",
            error_message=f"LLM 解析失败: {last_error}",
        )

    def _call_llm_parse_with_timeout(
        self, natural_language: str, stock_code: str, timeout: float
    ) -> Optional[str]:
        """调用 LLM API 进行策略解析（同步，带 timeout）。

        Returns:
            LLM 响应文本，超时时返回 None
        """
        import signal

        class TimeoutError(Exception):
            pass

        def _handler(signum, frame):
            raise TimeoutError("LLM API 超时")

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(int(timeout))
        try:
            signals_desc = self._build_signals_description()
            holding_desc = self._build_holding_rules_description()

            system_prompt = PARSE_SYSTEM_PROMPT.format(
                signals_list=signals_desc,
                holding_rules_list=holding_desc,
            )
            user_prompt = f"请解析以下策略描述：\n{natural_language}"

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_PARSE_TEMPERATURE,
                max_tokens=2000,
            )
            return response.choices[0].message.content or ""
        except TimeoutError:
            logger.warning("LLM API 调用超时")
            return None
        except Exception as e:
            raise e
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    async def _call_llm_api_async(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """异步调用 LLM API。

        Returns:
            LLM 响应文本
        """
        import asyncio

        def _sync_call():
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_PARSE_TEMPERATURE,
                max_tokens=2000,
            )
            return response.choices[0].message.content or ""

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _sync_call)

    def _build_parse_result(
        self, parsed: dict, natural_language: str, stock_code: str
    ) -> ParseResult:
        """从LLM解析结果构建 ParseResult。

        Args:
            parsed: LLM返回的JSON解析结果
            natural_language: 原始用户输入
            stock_code: 股票代码

        Returns:
            ParseResult
        """
        # 构建 entry_conditions
        entry_conditions = []
        for ec in parsed.get("entry_conditions", []):
            sid = ec.get("signal_id", "")
            if sid and get_signal_by_id(sid):
                entry_conditions.append(SignalCondition(
                    signal_id=sid,
                    operator=ec.get("operator", "trigger"),
                    threshold=float(ec.get("threshold", 0.0)),
                ))
            else:
                logger.warning(f"未识别的买入信号: {sid}")

        # 构建 exit_conditions
        exit_conditions = []
        for ec in parsed.get("exit_conditions", []):
            sid = ec.get("signal_id", "")
            if sid and get_signal_by_id(sid):
                exit_conditions.append(SignalCondition(
                    signal_id=sid,
                    operator=ec.get("operator", "trigger"),
                    threshold=float(ec.get("threshold", 0.0)),
                ))
            elif sid:
                logger.warning(f"未识别的卖出信号: {sid}")

        # 持有规则
        holding_rule = None
        rule_id = parsed.get("holding_rule_id")
        if rule_id:
            hr = get_holding_rule_by_id(rule_id)
            if hr:
                holding_rule = hr

        strategy = Strategy(
            id="",
            name=f"自定义策略-{natural_language[:20]}",
            raw_text=natural_language,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            holding_rule=holding_rule,
            params={"stock_code": stock_code},
        )

        confidence = parsed.get("confidence", 0.5)

        return ParseResult(
            success=confidence > 0.3 and len(entry_conditions) > 0,
            parsed_strategy=strategy,
            explanation=parsed.get("explanation", ""),
            warnings=parsed.get("warnings", []),
            parse_level="llm",
        )

    # ── P0-4 新增：校验与自动修复 ──────────────────────

    def _validate_parsed_strategy(self, parsed: dict) -> List[str]:
        """校验 LLM 解析结果的有效性。

        Args:
            parsed: LLM返回的JSON解析结果

        Returns:
            错误信息列表（空列表表示校验通过）
        """
        errors: List[str] = []

        # 检查 entry 非空
        entry_conditions = parsed.get("entry_conditions", [])
        if not entry_conditions:
            errors.append("缺少买入条件(entry_conditions)")

        # 检查信号ID有效性
        all_conditions = entry_conditions + parsed.get("exit_conditions", [])
        invalid_ids: List[str] = []
        for cond in all_conditions:
            sid = cond.get("signal_id", "")
            if sid and sid not in _VALID_SIGNAL_IDS:
                invalid_ids.append(sid)

        if invalid_ids:
            errors.append(f"无效信号ID: {', '.join(invalid_ids[:5])}")

        # 无矛盾信号对检查：不应同时包含金叉和死叉作为 entry
        all_signals_str = " ".join(str(all_conditions))
        has_golden = any(k in all_signals_str.lower() for k in ["golden_cross", "金叉"])
        has_death = any(k in all_signals_str.lower() for k in ["death_cross", "死叉"])
        if has_golden and has_death:
            # 仅当同时出现在 entry 或同时出现在 exit 时才算矛盾
            entry_signals_str = " ".join(str(entry_conditions))
            entry_has_golden = any(k in entry_signals_str.lower() for k in ["golden_cross", "金叉"])
            entry_has_death = any(k in entry_signals_str.lower() for k in ["death_cross", "死叉"])
            if entry_has_golden and entry_has_death:
                errors.append("信号矛盾：entry 同时包含金叉和死叉")

        return errors

    def _auto_fix_strategy(self, parsed: dict, errors: List[str]) -> dict:
        """自动修复解析错误。

        Args:
            parsed: 原始解析结果
            errors: 校验发现的错误列表

        Returns:
            修复后的解析结果
        """
        fixed = dict(parsed)

        for error in errors:
            if "缺少买入条件" in error:
                # 默认：均线金叉
                fixed["entry_conditions"] = [
                    {"signal_id": "ma_golden_cross", "operator": "cross_above", "threshold": 0.0}
                ]

            if "无效信号ID" in error:
                # 去除无效信号ID
                fixed["entry_conditions"] = [
                    c for c in fixed.get("entry_conditions", [])
                    if c.get("signal_id", "") in _VALID_SIGNAL_IDS
                ]
                fixed["exit_conditions"] = [
                    c for c in fixed.get("exit_conditions", [])
                    if c.get("signal_id", "") in _VALID_SIGNAL_IDS
                ]
                # 如果去除后 entry 为空，补默认
                if not fixed.get("entry_conditions"):
                    fixed["entry_conditions"] = [
                        {"signal_id": "ma_golden_cross", "operator": "cross_above", "threshold": 0.0}
                    ]

            if "信号矛盾" in error:
                # 保留第一个非矛盾信号（去掉死叉）
                fixed["entry_conditions"] = [
                    c for c in fixed.get("entry_conditions", [])
                    if "death" not in str(c).lower() and "死叉" not in str(c)
                ]
                if not fixed.get("entry_conditions"):
                    fixed["entry_conditions"] = [
                        {"signal_id": "ma_golden_cross", "operator": "cross_above", "threshold": 0.0}
                    ]

        # 补默认 holding_rule_id
        if not fixed.get("holding_rule_id"):
            fixed["holding_rule_id"] = "next_signal_reverse"

        # 确保 confidence 合理
        if fixed.get("confidence", 0) < 0.3:
            fixed["confidence"] = 0.4  # 修复后略高于阈值

        return fixed

    # ── 回测结果解读 ────────────────────────────────────

    def interpret_backtest(self, result_summary: dict) -> InterpretResult:
        """对回测结果进行 AI 解读。

        Args:
            result_summary: 回测结果摘要

        Returns:
            InterpretResult
        """
        total_return = result_summary.get("total_return", 0) * 100
        annual_return = result_summary.get("annual_return", 0) * 100
        max_dd = result_summary.get("max_drawdown", 0) * 100
        win_rate = result_summary.get("win_rate", 0) * 100
        sharpe = result_summary.get("sharpe_ratio", 0)
        total_trades = result_summary.get("total_trades", 0)

        user_prompt = f"""请分析以下回测结果：

股票：{result_summary.get('stock_name', '未知')}（{result_summary.get('stock_code', '')}）
策略：{result_summary.get('strategy_name', '自定义策略')}
回测指标：
- 总收益率：{total_return:.2f}%
- 年化收益率：{annual_return:.2f}%
- 最大回撤：{max_dd:.2f}%
- 胜率：{win_rate:.1f}%
- 夏普比率：{sharpe:.2f}
- 总交易次数：{total_trades}
- 盈利次数：{result_summary.get('win_trades', 0)}
- 亏损次数：{result_summary.get('lose_trades', 0)}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": INTERPRET_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_INTERPRET_TEMPERATURE,
                max_tokens=1500,
            )

            content = response.choices[0].message.content or ""
            parsed = self._extract_json(content)

            if parsed is None:
                return InterpretResult(
                    summary=content[:200],
                    risk_analysis="",
                    benchmark_comparison="",
                    suggestion=self._sanitize_output("历史表现不代表未来收益，请谨慎参考。"),
                )

            return InterpretResult(
                summary=parsed.get("summary", ""),
                risk_analysis=parsed.get("risk_analysis", ""),
                benchmark_comparison=parsed.get("benchmark_comparison", ""),
                suggestion=self._sanitize_output(parsed.get("suggestion", "历史表现不代表未来收益，请谨慎参考。")),
            )

        except Exception as e:
            logger.error(f"LLM 解读失败: {e}")
            return InterpretResult(
                summary="回测解读暂时不可用",
                risk_analysis="",
                benchmark_comparison="",
                suggestion=self._sanitize_output("历史表现不代表未来收益，请谨慎参考。"),
            )

    # ── 体检报告生成 ────────────────────────────────────

    def generate_checkup_report(self, checkup_data: dict) -> str:
        """生成策略体检报告。

        Args:
            checkup_data: 体检结果数据

        Returns:
            AI报告文本
        """
        trigger_rate = checkup_data.get("trigger_rate", 0) * 100
        win_rate = checkup_data.get("win_rate", 0) * 100
        avg_return = checkup_data.get("avg_return", 0) * 100
        best_return = checkup_data.get("best_return", 0) * 100
        worst_return = checkup_data.get("worst_return", 0) * 100
        triggered = checkup_data.get("triggered", 0)
        total_tests = checkup_data.get("total_tests", 0)
        signal_names = checkup_data.get("signal_names", [])

        user_prompt = f"""请生成策略体检报告：

验证信号：{', '.join(signal_names)}
测试范围：{total_tests} 个交易日×股票组合
实际触发次数：{triggered} 次
触发概率：{trigger_rate:.2f}%
触发后胜率：{win_rate:.1f}%
触发后平均收益：{avg_return:.2f}%
触发后最佳收益：{best_return:.2f}%
触发后最差收益：{worst_return:.2f}%
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CHECKUP_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_INTERPRET_TEMPERATURE,
                max_tokens=1000,
            )

            content = response.choices[0].message.content or ""
            report = self._sanitize_output(content.strip())
            return report

        except Exception as e:
            logger.error(f"LLM 体检报告生成失败: {e}")
            return self._sanitize_output(f"体检报告生成失败: {str(e)}\n\n历史表现不代表未来收益，请谨慎参考。")

    # ── 辅助方法 ────────────────────────────────────────

    @staticmethod
    def _sanitize_output(text: str) -> str:
        """过滤违规关键词并追加风险免责声明"""
        import re
        violations = [
            r'建议买入', r'建议卖出', r'强烈建议', r'推荐买入', r'推荐卖出',
            r'可以买入', r'应该卖出', r'值得买入', r'值得关注', r'建议关注',
            r'建议加仓', r'建议减仓', r'建议持有', r'建议清仓',
        ]
        for pattern in violations:
            text = re.sub(pattern, '历史数据统计显示', text)
        # 去除连续的重复替换
        text = re.sub(r'(历史数据统计显示\s*){2,}', '历史数据统计显示', text)
        return text + RISK_DISCLAIMER

    def _build_signals_description(self) -> str:
        """构建信号列表描述文本"""
        lines = []
        for s in ALL_SIGNALS:
            lines.append(f"- {s.id}: {s.name}（{s.category}）— {s.description}")
        return "\n".join(lines)

    def _build_holding_rules_description(self) -> str:
        """构建持有规则描述文本"""
        lines = []
        for r in ALL_HOLDING_RULES:
            lines.append(f"- {r.id}: {r.name} — {r.description}")
        return "\n".join(lines)

    @staticmethod
    def _extract_json(content: str) -> dict | None:
        """从LLM响应中提取JSON（处理markdown代码块包裹）"""
        content = content.strip()

        # 去掉 markdown 代码块标记
        if content.startswith("```"):
            lines = content.split("\n")
            # 去掉第一行（```json 或 ```）
            if lines[0].startswith("```"):
                lines = lines[1:]
            # 去掉最后一行（```）
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        # 查找 JSON 对象的起止位置
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end + 1]

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}, 内容: {content[:200]}")
            return None
