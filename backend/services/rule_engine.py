"""
规则引擎 — LLM 降级链 Level 3 兜底

基于关键词→信号映射规则，在 LLM 和模板均失败时提供兜底解析。
确保系统在任何情况下都能生成可用的策略。
"""

from __future__ import annotations

import jieba
from typing import List, Set, Dict


class RuleEngine:
    """基于关键词-信号映射的规则引擎"""

    def __init__(self):
        jieba.initialize()
        self._rules: List[Dict] = self._build_rules()

    def _build_rules(self) -> List[Dict]:
        """构建 30+ 关键词→信号映射规则（按优先级降序，更具体优先）"""
        return [
            # 趋势类
            {"keywords": ["多头排列"], "signal": "ma_bullish_alignment", "type": "entry", "priority": 10},
            {"keywords": ["空头排列"], "signal": "ma_bearish_alignment", "type": "exit", "priority": 10},
            {"keywords": ["上涨趋势"], "signal": "ma_bullish_alignment", "type": "entry", "priority": 8},
            {"keywords": ["下跌趋势"], "signal": "ma_bearish_alignment", "type": "exit", "priority": 8},
            {"keywords": ["趋势向上"], "signal": "ma_bullish_alignment", "type": "entry", "priority": 8},
            {"keywords": ["趋势向下"], "signal": "ma_bearish_alignment", "type": "exit", "priority": 8},
            # MACD 类
            {"keywords": ["macd金叉"], "signal": "macd_golden_cross", "type": "entry", "priority": 9},
            {"keywords": ["macd死叉"], "signal": "macd_death_cross", "type": "exit", "priority": 9},
            {"keywords": ["macd", "金叉"], "signal": "macd_golden_cross", "type": "entry", "priority": 7},
            {"keywords": ["macd", "死叉"], "signal": "macd_death_cross", "type": "exit", "priority": 7},
            {"keywords": ["金叉"], "signal": "ma_golden_cross", "type": "entry", "priority": 6},
            {"keywords": ["死叉"], "signal": "ma_death_cross", "type": "exit", "priority": 6},
            {"keywords": ["底背离"], "signal": "macd_divergence_bullish", "type": "entry", "priority": 9},
            {"keywords": ["顶背离"], "signal": "macd_divergence_bearish", "type": "exit", "priority": 9},
            # KDJ 类
            {"keywords": ["kdj超卖"], "signal": "kdj_oversold", "type": "entry", "priority": 9},
            {"keywords": ["kdj超买"], "signal": "kdj_overbought", "type": "exit", "priority": 9},
            {"keywords": ["kdj", "超卖"], "signal": "kdj_oversold", "type": "entry", "priority": 8},
            {"keywords": ["kdj", "超买"], "signal": "kdj_overbought", "type": "exit", "priority": 8},
            {"keywords": ["超卖"], "signal": "rsi_oversold_14", "type": "entry", "priority": 5},
            {"keywords": ["超买"], "signal": "rsi_overbought_14", "type": "exit", "priority": 5},
            # RSI 类
            {"keywords": ["rsi超卖"], "signal": "rsi_oversold_14", "type": "entry", "priority": 9},
            {"keywords": ["rsi超买"], "signal": "rsi_overbought_14", "type": "exit", "priority": 9},
            # 布林带
            {"keywords": ["布林下轨"], "signal": "boll_lower_touch", "type": "entry", "priority": 10},
            {"keywords": ["布林上轨"], "signal": "boll_upper_touch", "type": "exit", "priority": 10},
            {"keywords": ["下轨"], "signal": "boll_lower_touch", "type": "entry", "priority": 6},
            {"keywords": ["上轨"], "signal": "boll_upper_touch", "type": "exit", "priority": 6},
            # 突破类
            {"keywords": ["放量突破"], "signal": "vol_breakout_1_5", "type": "entry", "priority": 10},
            {"keywords": ["放量"], "signal": "vol_breakout_1_5", "type": "entry", "priority": 5},
            {"keywords": ["突破高点"], "signal": "breakout_20day_high", "type": "entry", "priority": 10},
            {"keywords": ["突破", "高点"], "signal": "breakout_20day_high", "type": "entry", "priority": 7},
            {"keywords": ["新高"], "signal": "breakout_20day_high", "type": "entry", "priority": 6},
            {"keywords": ["突破"], "signal": "breakout_20day_high", "type": "entry", "priority": 4},
            # 形态类
            {"keywords": ["双底"], "signal": "hammer", "type": "entry", "priority": 9},
            {"keywords": ["w底"], "signal": "hammer", "type": "entry", "priority": 9},
            {"keywords": ["v型反转"], "signal": "hammer", "type": "entry", "priority": 9},
            {"keywords": ["反转"], "signal": "hammer", "type": "entry", "priority": 5},
            # 卖出类
            {"keywords": ["止损"], "signal": "ma_death_cross", "type": "exit", "priority": 8},
            {"keywords": ["止盈"], "signal": "rsi_overbought_14", "type": "exit", "priority": 8},
            {"keywords": ["移动止损"], "signal": "boll_mid_break_down", "type": "exit", "priority": 9},
            {"keywords": ["追涨"], "signal": "momentum_5d_strong", "type": "entry", "priority": 7},
            {"keywords": ["强势"], "signal": "momentum_5d_strong", "type": "entry", "priority": 5},
            {"keywords": ["抄底"], "signal": "rsi_oversold_14", "type": "entry", "priority": 6},
        ]

    def _match_rules(self, tokens: Set[str]) -> List[Dict]:
        """匹配规则（按优先级排序，更具体的关键词优先）

        Args:
            tokens: jieba 分词后的 token 集合

        Returns:
            匹配到的规则列表（按 priority 降序）
        """
        matched: List[Dict] = []
        tokens_lower = {t.lower() for t in tokens}

        for rule in self._rules:
            rule_keywords = [k.lower() for k in rule["keywords"]]
            # 所有关键词都必须在 tokens 中出现才匹配
            if all(k in tokens_lower for k in rule_keywords):
                matched.append(rule)

        # 按优先级降序排序（高优先级 = 更具体的规则）
        matched.sort(key=lambda r: r["priority"], reverse=True)
        return matched

    def parse(self, user_input: str) -> dict:
        """规则引擎解析用户输入

        Args:
            user_input: 用户输入的自然语言策略描述

        Returns:
            ParseResult 兼容字典
        """
        # jieba 分词
        tokens = set(w for w in jieba.cut(user_input) if len(w.strip()) > 1)
        matched_rules = self._match_rules(tokens)

        entry_signals: List[str] = []
        exit_signals: List[str] = []

        for rule in matched_rules:
            signal = rule["signal"]
            if rule["type"] == "entry" and signal not in entry_signals:
                entry_signals.append(signal)
            elif rule["type"] == "exit" and signal not in exit_signals:
                exit_signals.append(signal)

        # 至少 1 个 entry_condition
        if not entry_signals:
            entry_signals = ["ma_golden_cross"]  # 默认：均线金叉
        # 至少 1 个 exit
        if not exit_signals:
            exit_signals = ["ma_death_cross"]  # 默认：均线死叉

        warnings: List[str] = []
        if len(matched_rules) < 2:
            warnings.append("由规则引擎解析，可能不够精确")

        return {
            "success": True,
            "parse_level": "rule_engine",
            "strategy_spec": {
                "name": "规则引擎策略",
                "entry_signals": entry_signals,
                "exit_signals": exit_signals,
                "holding_rule": {"rule_id": "next_signal_reverse"},
            },
            "explanation": f"规则引擎解析：匹配到 {len(matched_rules)} 条规则",
            "warnings": warnings,
            "error_message": "",
        }
