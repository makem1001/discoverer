"""
策略模板匹配器 — LLM 降级链 Level 1

基于 jieba 分词 + Jaccard 相似度匹配 15+ 预置策略模板。
命中后直接构建 Strategy，跳过 LLM 调用。
"""

from __future__ import annotations

try:
    import jieba
    _jieba_available = True
except ImportError:
    jieba = None  # type: ignore
    _jieba_available = False
    import logging
    logging.getLogger("discoverer.strategy_templates").warning(
        "jieba 未安装，策略模板匹配降级，将跳过模板匹配直接使用 LLM"
    )

from typing import Optional, List, Set
from dataclasses import dataclass, field


@dataclass
class StrategyTemplate:
    """策略模板数据类"""
    name: str
    keywords: List[str]  # 用于匹配的中文关键词集合
    description: str
    strategy_spec: dict   # 可以直接构建 Strategy 的字段（entry_signals, exit_signals, holding_rule）


# ── 信号ID映射表：将模板中的抽象信号名映射到实际系统信号ID ──
_SIGNAL_ID_MAP: dict[str, str] = {
    "macd_golden_cross": "macd_golden_cross",
    "macd_death_cross": "macd_death_cross",
    "kdj_oversold": "kdj_oversold",
    "kdj_overbought": "kdj_overbought",
    "ma_bullish_alignment": "ma_bullish_alignment",
    "ma_bearish_alignment": "ma_bearish_alignment",
    "breakout_20d_high": "breakout_20day_high",
    "volume_breakout": "vol_breakout_1_5",
    "volume_shrink": "vol_shrink_half",
    "rsi_oversold": "rsi_oversold_14",
    "rsi_overbought": "rsi_overbought_14",
    "boll_lower_touch": "boll_lower_touch",
    "boll_upper_touch": "boll_upper_touch",
    "boll_middle_reach": "boll_mid_break_up",
    "double_bottom": "hammer",  # 无独立双底信号，回退锤子线
    "v_shape_reversal": "hammer",  # 无独立V型反转信号，回退锤子线
    "ma_trend_up": "ma_bullish_alignment",
    "ma_trend_down": "ma_bearish_alignment",
    "strength_breakout": "momentum_5d_strong",
    "strength_fade": "momentum_5d_weak",
    "trailing_stop_5pct": "stop_loss",
    "trailing_stop_3pct": "stop_loss",
    "stop_loss_pct": "stop_loss",
    "stop_profit_pct": "stop_profit",
    "ma_golden_cross": "ma_golden_cross",
    "ma_death_cross": "ma_death_cross",
}


def map_signal_id(abstract_id: str) -> str:
    """将模板中的抽象信号ID映射到系统实际信号ID"""
    return _SIGNAL_ID_MAP.get(abstract_id, abstract_id)


def build_strategy_from_spec(strategy_spec: dict) -> "Strategy":
    """从模板 strategy_spec 构建完整的 Strategy 对象。

    Args:
        strategy_spec: 包含 entry_signals, exit_signals, holding_rule 的字典

    Returns:
        Strategy 对象
    """
    from models.schemas import Strategy, SignalCondition, HoldingRule
    from models.signals import get_signal_by_id, get_holding_rule_by_id

    entry_conditions = []
    for sig_name in strategy_spec.get("entry_signals", []):
        mapped_id = map_signal_id(sig_name)
        sig_def = get_signal_by_id(mapped_id)
        if sig_def:
            entry_conditions.append(SignalCondition(
                signal_id=mapped_id,
                operator="cross_above" if "cross" in mapped_id or "golden" in mapped_id else "trigger",
                threshold=0.0,
            ))

    exit_conditions = []
    for sig_name in strategy_spec.get("exit_signals", []):
        mapped_id = map_signal_id(sig_name)
        sig_def = get_signal_by_id(mapped_id)
        if sig_def:
            exit_conditions.append(SignalCondition(
                signal_id=mapped_id,
                operator="cross_below" if "cross" in mapped_id or "death" in mapped_id else "trigger",
                threshold=0.0,
            ))

    # 持有规则
    holding_rule = None
    hr_spec = strategy_spec.get("holding_rule", {})
    if hr_spec:
        hr_id = hr_spec.get("rule_id", "next_signal_reverse")
        holding_rule = get_holding_rule_by_id(hr_id)
        if holding_rule is None:
            holding_rule = get_holding_rule_by_id("next_signal_reverse")

    return Strategy(
        id="",
        name=strategy_spec.get("name", "模板策略"),
        raw_text="",
        entry_conditions=entry_conditions,
        exit_conditions=exit_conditions,
        holding_rule=holding_rule,
    )


class TemplateMatcher:
    """基于 jieba 分词 + Jaccard 相似度的策略模板匹配器"""

    SIMILARITY_THRESHOLD: float = 0.6  # Jaccard 阈值

    def __init__(self):
        if jieba is not None:
            jieba.initialize()
        self._templates: List[StrategyTemplate] = self._build_templates()

    def _build_templates(self) -> List[StrategyTemplate]:
        """构建 15+ 预置策略模板"""
        return [
            StrategyTemplate(
                name="MACD金叉买入",
                keywords=["macd", "金叉", "买入", "diff", "dea"],
                description="MACD指标DIF线上穿DEA线",
                strategy_spec={
                    "name": "MACD金叉买入",
                    "entry_signals": ["macd_golden_cross"],
                    "exit_signals": ["macd_death_cross"],
                    "holding_rule": {"rule_id": "next_signal_reverse"},
                }
            ),
            StrategyTemplate(
                name="MACD死叉卖出",
                keywords=["macd", "死叉", "卖出", "diff", "dea"],
                description="MACD指标DIF线下穿DEA线",
                strategy_spec={
                    "name": "MACD死叉卖出",
                    "entry_signals": ["macd_death_cross"],
                    "exit_signals": ["macd_golden_cross", "stop_loss_pct"],
                    "holding_rule": {"rule_id": "next_signal_reverse"},
                }
            ),
            StrategyTemplate(
                name="KDJ超卖反弹",
                keywords=["kdj", "超卖", "j值", "反弹"],
                description="KDJ指标进入超卖区后金叉反弹",
                strategy_spec={
                    "name": "KDJ超卖反弹",
                    "entry_signals": ["kdj_oversold"],
                    "exit_signals": ["kdj_overbought"],
                    "holding_rule": {"rule_id": "next_signal_reverse"},
                }
            ),
            StrategyTemplate(
                name="KDJ超买回落",
                keywords=["kdj", "超买", "j值", "回落"],
                description="KDJ指标进入超买区后死叉回落",
                strategy_spec={
                    "name": "KDJ超买回落",
                    "entry_signals": ["kdj_overbought"],
                    "exit_signals": ["kdj_oversold", "stop_loss_pct"],
                    "holding_rule": {"rule_id": "next_signal_reverse"},
                }
            ),
            StrategyTemplate(
                name="均线多头排列",
                keywords=["均线", "多头排列", "多头", "ma多头"],
                description="短期均线在长期均线之上排列",
                strategy_spec={
                    "name": "均线多头排列",
                    "entry_signals": ["ma_bullish_alignment"],
                    "exit_signals": ["ma_bearish_alignment"],
                    "holding_rule": {"rule_id": "hold_until_end"},
                }
            ),
            StrategyTemplate(
                name="均线空头排列",
                keywords=["均线", "空头排列", "空头", "ma空头"],
                description="短期均线在长期均线之下排列",
                strategy_spec={
                    "name": "均线空头排列",
                    "entry_signals": ["ma_bearish_alignment"],
                    "exit_signals": ["ma_bullish_alignment", "stop_loss_pct"],
                    "holding_rule": {"rule_id": "next_signal_reverse"},
                }
            ),
            StrategyTemplate(
                name="突破20日高点",
                keywords=["突破", "高点", "20日", "新高", "突破高点"],
                description="股价突破过去20个交易日的最高价",
                strategy_spec={
                    "name": "突破20日高点",
                    "entry_signals": ["breakout_20d_high"],
                    "exit_signals": ["trailing_stop_5pct"],
                    "holding_rule": {"rule_id": "trailing_stop"},
                }
            ),
            StrategyTemplate(
                name="放量突破",
                keywords=["放量", "突破", "成交量放大", "量价齐升"],
                description="成交量放大且股价突破关键阻力位",
                strategy_spec={
                    "name": "放量突破",
                    "entry_signals": ["volume_breakout"],
                    "exit_signals": ["volume_shrink"],
                    "holding_rule": {"rule_id": "next_signal_reverse"},
                }
            ),
            StrategyTemplate(
                name="RSI超卖买入",
                keywords=["rsi", "超卖", "超跌"],
                description="RSI指标进入超卖区后回升",
                strategy_spec={
                    "name": "RSI超卖买入",
                    "entry_signals": ["rsi_oversold"],
                    "exit_signals": ["rsi_overbought"],
                    "holding_rule": {"rule_id": "next_signal_reverse"},
                }
            ),
            StrategyTemplate(
                name="布林下轨反弹",
                keywords=["布林", "下轨", "boll", "下轨反弹"],
                description="股价触及布林带下轨后反弹",
                strategy_spec={
                    "name": "布林下轨反弹",
                    "entry_signals": ["boll_lower_touch"],
                    "exit_signals": ["boll_middle_reach"],
                    "holding_rule": {"rule_id": "hold_n_days"},
                }
            ),
            StrategyTemplate(
                name="布林上轨回落",
                keywords=["布林", "上轨", "boll", "上轨回落"],
                description="股价触及布林带上轨后回落",
                strategy_spec={
                    "name": "布林上轨回落",
                    "entry_signals": ["boll_upper_touch"],
                    "exit_signals": ["boll_middle_reach", "stop_loss_pct"],
                    "holding_rule": {"rule_id": "next_signal_reverse"},
                }
            ),
            StrategyTemplate(
                name="双底形态",
                keywords=["双底", "w底", "二次探底"],
                description="股价形成W型双底形态后反弹",
                strategy_spec={
                    "name": "双底形态",
                    "entry_signals": ["double_bottom"],
                    "exit_signals": ["trailing_stop_5pct"],
                    "holding_rule": {"rule_id": "trailing_stop"},
                }
            ),
            StrategyTemplate(
                name="V型反转",
                keywords=["v型", "v形", "反转", "深V"],
                description="股价急剧下跌后快速回升",
                strategy_spec={
                    "name": "V型反转",
                    "entry_signals": ["v_shape_reversal"],
                    "exit_signals": ["trailing_stop_3pct"],
                    "holding_rule": {"rule_id": "trailing_stop"},
                }
            ),
            StrategyTemplate(
                name="趋势跟踪买入",
                keywords=["趋势", "跟踪", "上涨趋势", "上升通道"],
                description="跟踪MA趋势线，趋势向上时买入",
                strategy_spec={
                    "name": "趋势跟踪买入",
                    "entry_signals": ["ma_trend_up"],
                    "exit_signals": ["ma_trend_down"],
                    "holding_rule": {"rule_id": "hold_until_end"},
                }
            ),
            StrategyTemplate(
                name="强势股追涨",
                keywords=["强势", "追涨", "领涨", "涨停"],
                description="强势板块领涨股突破后追入",
                strategy_spec={
                    "name": "强势股追涨",
                    "entry_signals": ["strength_breakout"],
                    "exit_signals": ["trailing_stop_5pct", "strength_fade"],
                    "holding_rule": {"rule_id": "trailing_stop"},
                }
            ),
        ]

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """jieba 分词 + 转小写，过滤单字"""
        if jieba is None:
            # Fallback: simple whitespace/char split
            return set(text.lower().replace('，', ' ').replace('。', ' ').split())
        words = jieba.cut(text)
        return set(w.lower() for w in words if len(w.strip()) > 1)

    @staticmethod
    def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
        """计算 Jaccard 相似度

        Jaccard(A, B) = |A ∩ B| / |A ∪ B|
        """
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        if not union:
            return 0.0
        return len(intersection) / len(union)

    def match(self, user_input: str) -> Optional[dict]:
        """匹配策略模板，返回 ParseResult 兼容字典或 None

        Args:
            user_input: 用户输入的自然语言策略描述

        Returns:
            ParseResult 兼容字典 或 None（未命中）
        """
        user_tokens = self._tokenize(user_input)

        best_score = 0.0
        best_template: Optional[StrategyTemplate] = None

        for template in self._templates:
            # 对每个模板的 keywords 集合计算相似度
            template_tokens = set(k.lower() for k in template.keywords)
            score = self._jaccard_similarity(user_tokens, template_tokens)
            if score > best_score:
                best_score = score
                best_template = template

        if best_score < self.SIMILARITY_THRESHOLD or best_template is None:
            return None

        return {
            "success": True,
            "parse_level": "template",
            "strategy_name": best_template.name,
            "strategy_spec": best_template.strategy_spec,
            "explanation": f"模板匹配: {best_template.description} (相似度: {best_score:.2f})",
            "warnings": [],
            "error_message": "",
        }
