"""
测试：69个信号定义 + 8个持有规则 + 13个经典策略

验证：
  1. 信号定义数量正确（69个）
  2. 持有规则数量正确（8个）
  3. 经典策略数量正确（13个）
  4. 所有信号 ID 唯一
  5. 辅助函数正确性
  6. 经典策略中引用的信号/规则全部存在
  7. SignalService 可正确初始化
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pandas as pd
import numpy as np

from models.signals import (
    ALL_SIGNALS, ALL_HOLDING_RULES, CLASSIC_STRATEGIES,
    get_signal_by_id, get_holding_rule_by_id, get_classic_strategy,
    build_strategy_from_classic,
)
from models.schemas import Signal, HoldingRule


class TestSignalDefinitions:
    """69个信号定义验证"""

    CATEGORY_COUNTS = {
        "均线": 12, "MACD": 6, "KDJ": 6, "RSI": 6,
        "布林带": 5, "成交量": 8, "形态": 10, "趋势": 6,
        "动量": 6, "波动率": 4,
    }

    def test_total_signal_count(self):
        """验证信号总数为 69"""
        assert len(ALL_SIGNALS) == 69, f"期望 69 个信号，实际 {len(ALL_SIGNALS)}"

    def test_category_counts(self):
        """验证每个分类的信号数量"""
        from collections import Counter
        actual = Counter(s.category for s in ALL_SIGNALS)
        for cat, expected_count in self.CATEGORY_COUNTS.items():
            assert actual[cat] == expected_count, \
                f"分类 '{cat}' 期望 {expected_count} 个，实际 {actual[cat]} 个"

    def test_all_signal_ids_unique(self):
        """验证所有信号 ID 唯一"""
        ids = [s.id for s in ALL_SIGNALS]
        assert len(ids) == len(set(ids)), f"信号 ID 有重复: {len(ids)} vs {len(set(ids))}"

    def test_all_signal_ids_not_empty(self):
        """验证所有信号 ID 非空"""
        for s in ALL_SIGNALS:
            assert s.id, f"信号 {s.name} 的 ID 为空"

    def test_all_signals_have_names(self):
        """验证所有信号有名称为"""
        for s in ALL_SIGNALS:
            assert s.name, f"信号 {s.id} 的名称为空"

    def test_all_signals_have_category(self):
        """验证所有信号有分类"""
        for s in ALL_SIGNALS:
            assert s.category, f"信号 {s.id} 的分类为空"

    def test_get_signal_by_id_found(self):
        """验证按 ID 查找有效信号"""
        s = get_signal_by_id("macd_golden_cross")
        assert s is not None
        assert s.name == "MACD金叉"
        assert s.category == "MACD"

    def test_get_signal_by_id_not_found(self):
        """验证查找不存在的信号返回 None"""
        s = get_signal_by_id("nonexistent_signal")
        assert s is None

    def test_get_signal_by_id_each(self):
        """验证每个信号都能通过 ID 找到"""
        for s in ALL_SIGNALS:
            found = get_signal_by_id(s.id)
            assert found is not None, f"信号 {s.id} 无法通过 get_signal_by_id 找到"
            assert found.id == s.id

    def test_ma_signals_list(self):
        """验证均线类信号包含关键信号"""
        ma_ids = {s.id for s in ALL_SIGNALS if s.category == "均线"}
        expected = {
            "ma_golden_cross", "ma_death_cross",
            "ma_golden_cross_10_30", "ma_death_cross_10_30",
            "ma_golden_cross_20_60", "ma_death_cross_20_60",
            "price_above_ma5", "price_below_ma5",
            "price_above_ma20", "price_below_ma20",
            "ma_bullish_alignment", "ma_bearish_alignment",
        }
        assert ma_ids == expected, f"均线信号不符: {ma_ids ^ expected}"


class TestHoldingRules:
    """8个持有规则验证"""

    def test_total_holding_rules_count(self):
        assert len(ALL_HOLDING_RULES) == 8, f"期望 8 个持有规则，实际 {len(ALL_HOLDING_RULES)}"

    def test_all_rule_ids_unique(self):
        ids = [r.id for r in ALL_HOLDING_RULES]
        assert len(ids) == len(set(ids)), "持有规则 ID 有重复"

    def test_get_holding_rule_by_id_found(self):
        r = get_holding_rule_by_id("hold_n_days")
        assert r is not None
        assert r.name == "持有N天"
        assert r.params.get("days") == 5

    def test_get_holding_rule_by_id_not_found(self):
        r = get_holding_rule_by_id("nonexistent_rule")
        assert r is None

    def test_get_holding_rule_by_id_each(self):
        for r in ALL_HOLDING_RULES:
            found = get_holding_rule_by_id(r.id)
            assert found is not None, f"持有规则 {r.id} 无法找到"
            assert found.id == r.id

    def test_key_rules_exist(self):
        """验证关键持有规则存在"""
        rule_ids = {r.id for r in ALL_HOLDING_RULES}
        expected = {
            "hold_n_days", "stop_loss", "stop_profit",
            "trailing_stop", "next_signal_reverse",
            "ma_cross_exit", "hold_until_end", "atr_trailing_stop",
        }
        assert rule_ids == expected, f"持有规则不符: {rule_ids ^ expected}"


class TestClassicStrategies:
    """13个经典策略验证"""

    def test_total_classic_strategies_count(self):
        assert len(CLASSIC_STRATEGIES) == 13, \
            f"期望 13 个经典策略，实际 {len(CLASSIC_STRATEGIES)}"

    def test_all_classic_strategy_ids_unique(self):
        ids = [s["id"] for s in CLASSIC_STRATEGIES]
        assert len(ids) == len(set(ids)), "经典策略 ID 有重复"

    def test_get_classic_strategy_found(self):
        cs = get_classic_strategy("macd_golden_death")
        assert cs is not None
        assert cs["name"] == "MACD金叉死叉"
        assert cs["entry_signal"] == "macd_golden_cross"
        assert cs["exit_signal"] == "macd_death_cross"

    def test_get_classic_strategy_not_found(self):
        cs = get_classic_strategy("nonexistent")
        assert cs is None

    def test_all_entry_signals_exist(self):
        """验证所有经典策略的买入信号都是有效信号"""
        for cs in CLASSIC_STRATEGIES:
            entry = cs["entry_signal"]
            s = get_signal_by_id(entry)
            assert s is not None, \
                f"经典策略 '{cs['id']}' 的 entry_signal '{entry}' 不存在"

    def test_all_exit_signals_exist_or_none(self):
        """验证所有经典策略的卖出信号有效或为 None"""
        for cs in CLASSIC_STRATEGIES:
            exit_sig = cs.get("exit_signal")
            if exit_sig is not None:
                s = get_signal_by_id(exit_sig)
                assert s is not None, \
                    f"经典策略 '{cs['id']}' 的 exit_signal '{exit_sig}' 不存在"

    def test_all_holding_rules_exist(self):
        """验证所有经典策略的持有规则存在"""
        for cs in CLASSIC_STRATEGIES:
            hr_id = cs["holding_rule"]
            hr = get_holding_rule_by_id(hr_id)
            assert hr is not None, \
                f"经典策略 '{cs['id']}' 的 holding_rule '{hr_id}' 不存在"

    def test_build_strategy_from_classic(self):
        """验证从经典策略构建 Strategy 对象"""
        strategy = build_strategy_from_classic("macd_golden_death")
        assert strategy is not None
        assert strategy.name == "MACD金叉死叉"
        assert len(strategy.entry_conditions) == 1
        assert strategy.entry_conditions[0].signal_id == "macd_golden_cross"
        assert len(strategy.exit_conditions) == 1
        assert strategy.exit_conditions[0].signal_id == "macd_death_cross"
        assert strategy.holding_rule is not None
        assert strategy.holding_rule.id == "next_signal_reverse"

    def test_build_strategy_from_classic_nonexistent(self):
        strategy = build_strategy_from_classic("nonexistent")
        assert strategy is None

    def test_build_strategy_each_classic(self):
        """验证所有13个经典策略都能成功构建"""
        for cs in CLASSIC_STRATEGIES:
            strategy = build_strategy_from_classic(cs["id"])
            assert strategy is not None, \
                f"经典策略 '{cs['id']}' 构建失败"
            assert strategy.name == cs["name"]
            # entry_conditions 至少一个（有 entry_signal）
            assert len(strategy.entry_conditions) >= 1

    def test_build_strategy_with_no_exit_signal(self):
        """验证 exit_signal=None 的策略构建正确"""
        # "ma_golden_hold_10d" 的 exit_signal 为 None
        strategy = build_strategy_from_classic("ma_golden_hold_10d")
        assert strategy is not None
        assert len(strategy.exit_conditions) == 0
        # "bullish_alignment_hold" 的 exit_signal 也为 None
        strategy2 = build_strategy_from_classic("bullish_alignment_hold")
        assert strategy2 is not None
        assert len(strategy2.exit_conditions) == 0

    def test_classic_strategy_fields(self):
        """验证每个经典策略包含所有必要字段"""
        required_fields = {"id", "name", "description", "entry_signal", "holding_rule"}
        for cs in CLASSIC_STRATEGIES:
            missing = required_fields - set(cs.keys())
            assert not missing, \
                f"经典策略 '{cs.get('id', '?')}' 缺少字段: {missing}"


class TestSignalServiceInit:
    """SignalService 初始化测试"""

    def test_signal_service_import(self):
        """验证 SignalService 可正常导入和实例化"""
        from services.signal_service import SignalService
        svc = SignalService()
        assert svc is not None

    def test_signal_service_compute_unknown_signal(self):
        """验证计算未知信号返回全 False Series"""
        from services.signal_service import SignalService
        svc = SignalService()
        df = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "open": np.random.randn(30).cumsum() + 100,
            "high": np.random.randn(30).cumsum() + 102,
            "low": np.random.randn(30).cumsum() + 98,
            "close": np.random.randn(30).cumsum() + 100,
            "volume": np.random.randint(1000000, 10000000, 30),
        })
        result = svc.compute_signal(df, "nonexistent_signal")
        assert result is not None
        assert not result.any(), "未知信号应返回全 False"

    def test_signal_service_all_69_methods_exist(self):
        """验证 SignalService 包含所有 69 个信号的计算方法"""
        from services.signal_service import SignalService
        svc = SignalService()
        method_names = {m for m in dir(svc) if m.startswith("_calc_") and not m.startswith("_calc_ma") and not m.startswith("_calc_macd") and not m.startswith("_calc_kdj") and not m.startswith("_calc_rsi") and not m.startswith("_calc_boll") and not m.startswith("_calc_atr")}

        for s in ALL_SIGNALS:
            expected_method = f"_calc_{s.id}"
            assert hasattr(svc, expected_method), \
                f"SignalService 缺少方法 {expected_method} (信号: {s.name})"


class TestMockSignalComputation:
    """使用 Mock 数据验证关键信号计算"""

    @pytest.fixture
    def sample_df(self):
        """生成模拟日线数据"""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        n = len(dates)
        # 生成趋势模拟价格
        trend = np.linspace(0, 20, n)
        noise = np.random.randn(n) * 2
        close = 100 + trend + noise.cumsum() * 0.5
        open_p = close - np.random.randn(n) * 1
        high = np.maximum(open_p, close) + np.abs(np.random.randn(n)) * 1
        low = np.minimum(open_p, close) - np.abs(np.random.randn(n)) * 1
        volume = np.random.randint(5000000, 20000000, n)

        return pd.DataFrame({
            "date": dates,
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })

    def test_compute_ma_golden_cross(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "ma_golden_cross")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)
        # 应该有至少一些触发
        assert result.dtype == bool

    def test_compute_macd_golden_cross(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "macd_golden_cross")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_rsi_oversold(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "rsi_oversold_14")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_boll_lower_touch(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "boll_lower_touch")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_vol_breakout(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "vol_breakout_1_5")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_hammer(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "hammer")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_gap_up(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "gap_up")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_new_high_20(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "new_high_20")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_momentum_5d(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "momentum_5d_strong")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_atr_high(self, sample_df):
        from services.signal_service import SignalService
        svc = SignalService()
        result = svc.compute_signal(sample_df, "atr_high")
        assert isinstance(result, pd.Series)
        assert len(result) == len(sample_df)

    def test_compute_all_69_signals_no_exception(self, sample_df):
        """验证所有69个信号计算不抛异常"""
        from services.signal_service import SignalService
        svc = SignalService()
        failed = []
        for s in ALL_SIGNALS:
            try:
                result = svc.compute_signal(sample_df, s.id)
                assert isinstance(result, pd.Series)
                assert len(result) == len(sample_df)
            except Exception as e:
                failed.append((s.id, str(e)))
        assert not failed, f"以下信号计算失败: {failed}"
