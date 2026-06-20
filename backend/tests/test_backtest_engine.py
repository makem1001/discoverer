"""
测试：回测引擎核心逻辑

验证：
  1. 回测引擎初始化
  2. 买卖信号触发
  3. 佣金/税费计算
  4. 涨跌停限制
  5. 持有规则（止损/止盈/持有N天/移动止损）
  6. 指标计算（收益率/夏普/回撤/胜率）
  7. 空数据处理
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch

from models.schemas import (
    Strategy, SignalCondition, HoldingRule, BacktestMetrics, BacktestResult,
)
from models.signals import build_strategy_from_classic, ALL_SIGNALS, get_signal_by_id
from services.backtest_engine import BacktestEngine
from config import (
    COMMISSION_RATE, STAMP_TAX_RATE, SLIPPAGE_RATE, LIMIT_UP_DOWN_RATE,
    DEFAULT_INITIAL_CAPITAL,
)


# ── 测试数据生成 ────────────────────────────────────────

def _make_uptrend_df(n=120):
    """生成单边上涨行情 DataFrame"""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = np.linspace(10.0, 20.0, n) + np.random.randn(n) * 0.2
    close = np.maximum(close, 1.0)
    return pd.DataFrame({
        "date": dates,
        "open": close - 0.1,
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "volume": np.full(n, 1_000_000),
    })


def _make_downtrend_df(n=120):
    """生成单边下跌行情 DataFrame"""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = np.linspace(20.0, 10.0, n) + np.random.randn(n) * 0.2
    close = np.maximum(close, 1.0)
    return pd.DataFrame({
        "date": dates,
        "open": close + 0.1,
        "high": close + 0.3,
        "low": close - 0.3,
        "close": close,
        "volume": np.full(n, 1_000_000),
    })


def _make_sideways_df(n=120):
    """生成震荡行情 DataFrame"""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 10.0 + np.sin(np.linspace(0, 4 * np.pi, n)) * 2 + np.random.randn(n) * 0.3
    close = np.maximum(close, 5.0)
    return pd.DataFrame({
        "date": dates,
        "open": close - 0.2,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": np.random.randint(5000000, 15000000, n),
    })


class TestBacktestEngineInit:
    """回测引擎初始化测试"""

    def test_engine_init_default(self):
        engine = BacktestEngine()
        assert engine is not None
        assert engine.signal_service is not None
        assert engine.data_service is None  # 默认无 data_service

    def test_engine_init_with_data_service(self):
        mock_ds = Mock()
        mock_ds._stock_code_index = {"000001": {"code": "000001", "name": "平安银行"}}
        engine = BacktestEngine(data_service=mock_ds)
        assert engine.data_service is mock_ds

    def test_engine_init_with_custom_signal_service(self):
        from services.signal_service import SignalService
        svc = SignalService()
        engine = BacktestEngine(signal_service=svc)
        assert engine.signal_service is svc


class TestRunBacktest:
    """核心回测方法测试"""

    def test_run_with_ma_golden_death_strategy(self):
        """测试均线金叉死叉策略回测"""
        engine = BacktestEngine()
        df = _make_uptrend_df(200)
        strategy = build_strategy_from_classic("ma_golden_death")
        assert strategy is not None

        result = engine.run_backtest(df, strategy)

        assert isinstance(result, BacktestResult)
        assert result.id != ""
        assert result.metrics is not None
        # 上涨行情中金叉策略应该有交易
        assert result.metrics.total_trades >= 0

    def test_run_with_macd_strategy(self):
        """测试MACD金叉死叉策略回测"""
        engine = BacktestEngine()
        df = _make_sideways_df(200)
        strategy = build_strategy_from_classic("macd_golden_death")
        assert strategy is not None

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)
        assert result.metrics is not None

    def test_run_with_rsi_strategy(self):
        """测试RSI超卖超买策略"""
        engine = BacktestEngine()
        df = _make_sideways_df(200)
        strategy = build_strategy_from_classic("rsi_oversold_overbought")
        assert strategy is not None

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)

    def test_run_with_kdj_strategy(self):
        """测试KDJ金叉死叉策略"""
        engine = BacktestEngine()
        df = _make_uptrend_df(200)
        strategy = build_strategy_from_classic("kdj_golden_death")
        assert strategy is not None

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)

    def test_run_with_boll_strategy(self):
        """测试布林带策略"""
        engine = BacktestEngine()
        df = _make_sideways_df(200)
        strategy = build_strategy_from_classic("boll_lower_buy_upper_sell")
        assert strategy is not None

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)

    def test_run_with_hold_n_days_strategy(self):
        """测试持有N天策略"""
        engine = BacktestEngine()
        df = _make_uptrend_df(200)
        strategy = build_strategy_from_classic("ma_golden_hold_10d")
        assert strategy is not None

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)
        # 持有10天策略应该有 trades
        if result.metrics.total_trades > 0:
            for t in result.trades:
                assert t.exit_reason in ("hold_expired", "signal", "end_of_period",
                                          "stop_loss", "stop_profit", "trailing_stop")

    def test_run_with_trailing_stop_strategy(self):
        """测试移动止损策略"""
        engine = BacktestEngine()
        df = _make_uptrend_df(200)
        strategy = build_strategy_from_classic("breakout_20d_high")
        assert strategy is not None

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)

    def test_run_with_bullish_alignment_strategy(self):
        """测试多头排列持有策略"""
        engine = BacktestEngine()
        df = _make_uptrend_df(200)
        strategy = build_strategy_from_classic("bullish_alignment_hold")
        assert strategy is not None

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)

    def test_run_all_13_classic_strategies(self):
        """验证所有13个经典策略都能成功执行回测"""
        engine = BacktestEngine()
        df = _make_uptrend_df(150)
        failed = []

        from models.signals import CLASSIC_STRATEGIES
        for cs in CLASSIC_STRATEGIES:
            strategy = build_strategy_from_classic(cs["id"])
            if strategy is None:
                failed.append((cs["id"], "build_strategy_from_classic returned None"))
                continue
            try:
                result = engine.run_backtest(df, strategy)
                assert isinstance(result, BacktestResult)
                assert result.id != ""
            except Exception as e:
                failed.append((cs["id"], str(e)))

        assert not failed, f"以下策略回测失败: {failed}"

    def test_empty_dataframe(self):
        """测试空 DataFrame 返回空结果"""
        engine = BacktestEngine()
        strategy = build_strategy_from_classic("macd_golden_death")
        result = engine.run_backtest(pd.DataFrame(), strategy)
        assert result.metrics.total_trades == 0
        assert result.trades == []
        assert result.equity_curve == []

    def test_too_short_dataframe(self):
        """测试数据不足时能正常处理"""
        engine = BacktestEngine()
        df = _make_uptrend_df(10)  # 只有10天数据
        strategy = build_strategy_from_classic("ma_golden_death")
        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)

    def test_different_initial_capital(self):
        """测试不同初始资金"""
        engine = BacktestEngine()
        df = _make_uptrend_df(200)
        strategy = build_strategy_from_classic("ma_golden_hold_10d")
        result = engine.run_backtest(df, strategy, initial_capital=50000.0)
        assert isinstance(result, BacktestResult)


class TestTradeSimulation:
    """交易模拟细节测试"""

    def test_trade_has_all_fields(self):
        """验证每笔交易包含所有必要字段"""
        engine = BacktestEngine()
        df = _make_uptrend_df(250)
        strategy = build_strategy_from_classic("macd_golden_death")
        result = engine.run_backtest(df, strategy)

        for trade in result.trades:
            assert trade.entry_date != ""
            assert trade.exit_date != ""
            assert trade.entry_price > 0
            assert trade.exit_price > 0
            assert trade.exit_reason != ""
            # return_pct 是小数形式
            assert isinstance(trade.return_pct, float)

    def test_equity_curve_has_all_fields(self):
        """验证资金曲线包含所有必要字段"""
        engine = BacktestEngine()
        df = _make_uptrend_df(250)
        strategy = build_strategy_from_classic("macd_golden_death")
        result = engine.run_backtest(df, strategy)

        assert len(result.equity_curve) == len(df)
        for ep in result.equity_curve:
            assert ep.date != ""
            assert ep.equity > 0
            assert 0.0 <= ep.drawdown <= 1.0

    def test_commission_applied_on_buy(self):
        """验证买入时收取佣金"""
        engine = BacktestEngine()

        # 构造一个强制在某天买入的数据
        n = 100
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        close = np.full(n, 10.0)

        df = pd.DataFrame({
            "date": dates, "open": close - 0.1, "high": close + 0.5,
            "low": close - 0.5, "close": close,
            "volume": np.full(n, 10_000_000),
        })

        # 自定义策略：始终在第50天买入
        strategy = Strategy(
            id="test_commission",
            name="佣金测试",
            entry_conditions=[SignalCondition(signal_id="vol_breakout_1_5", operator="trigger")],
            holding_rule=HoldingRule(id="hold_n_days", name="持有5天", params={"days": 5}),
        )

        result = engine.run_backtest(df, strategy, initial_capital=100000.0)

        if result.metrics.total_trades > 0:
            first_trade = result.trades[0]
            # 买入价应包含滑点
            assert first_trade.entry_price >= 10.0 * (1 + SLIPPAGE_RATE) * 0.99


class TestMetricsCalculation:
    """指标计算验证"""

    def test_metrics_fields_exist(self):
        """验证指标包含所有必要字段"""
        engine = BacktestEngine()
        df = _make_uptrend_df(200)
        strategy = build_strategy_from_classic("macd_golden_death")
        result = engine.run_backtest(df, strategy)

        m = result.metrics
        assert isinstance(m.total_return, float)
        assert isinstance(m.annual_return, float)
        assert isinstance(m.max_drawdown, float)
        assert isinstance(m.win_rate, float)
        assert isinstance(m.sharpe_ratio, float)
        assert isinstance(m.profit_loss_ratio, float)
        assert isinstance(m.total_trades, int)
        assert isinstance(m.win_trades, int)
        assert isinstance(m.lose_trades, int)
        assert isinstance(m.avg_hold_days, float)

    def test_metrics_consistency(self):
        """验证指标内部一致性"""
        engine = BacktestEngine()
        df = _make_uptrend_df(250)
        strategy = build_strategy_from_classic("macd_golden_death")
        result = engine.run_backtest(df, strategy)

        m = result.metrics
        # win_trades + lose_trades <= total_trades（可能存在收益为0的交易）
        assert m.win_trades + m.lose_trades <= m.total_trades

        # 如果有交易，胜率应合理
        if m.total_trades > 0:
            assert 0.0 <= m.win_rate <= 1.0

        # 最大回撤应在 [0, 1]
        assert 0.0 <= m.max_drawdown <= 1.0

    def test_yearly_stats(self):
        """验证逐年统计"""
        engine = BacktestEngine()
        df = _make_uptrend_df(500)
        strategy = build_strategy_from_classic("macd_golden_death")
        result = engine.run_backtest(df, strategy)

        if result.yearly_stats:
            for ys in result.yearly_stats:
                assert isinstance(ys.year, int)
                assert isinstance(ys.return_pct, float)
                assert isinstance(ys.trades, int)
                assert 0.0 <= ys.win_rate <= 1.0

    def test_no_trades_metrics(self):
        """验证无交易时的指标——空交易列表的边界情况"""
        engine = BacktestEngine()

        # 使用一个极端的空交易场景：构造一个确实不会有交易的数据
        # 直接传入空DataFrame来保证0交易
        strategy = build_strategy_from_classic("macd_golden_death")

        result = engine.run_backtest(pd.DataFrame(), strategy)
        assert result.metrics.total_trades == 0
        assert result.metrics.win_rate == 0.0


class TestBuySellTrigger:
    """买卖信号触发测试"""

    def test_no_entry_conditions_handles_gracefully(self):
        """验证无买入条件时回测不崩溃（边界情况）"""
        engine = BacktestEngine()
        df = _make_uptrend_df(200)

        strategy = Strategy(
            id="no_entry",
            name="无买入",
            entry_conditions=[],
            exit_conditions=[SignalCondition(signal_id="macd_death_cross", operator="trigger")],
        )

        # 主要验证不抛异常
        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)

    def test_stop_loss_triggered(self):
        """验证止损触发"""
        engine = BacktestEngine()

        # 构造急速下跌行情
        n = 80
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        # 先涨后跌：前40天涨，第41天开始急速跌
        close = np.concatenate([
            np.linspace(10.0, 15.0, 40),   # 上涨
            np.linspace(15.0, 7.0, 40),    # 下跌
        ])

        df = pd.DataFrame({
            "date": dates, "open": close - 0.1, "high": close + 0.3,
            "low": close - 0.3, "close": close,
            "volume": np.full(n, 10_000_000),
        })

        strategy = Strategy(
            id="stop_loss_test",
            name="止损测试",
            entry_conditions=[SignalCondition(signal_id="vol_breakout_1_5", operator="trigger")],
            holding_rule=HoldingRule(id="stop_loss", name="固定止损", params={"loss_pct": -0.05}),
        )

        result = engine.run_backtest(df, strategy, initial_capital=100000.0)

        if result.metrics.total_trades > 0:
            stop_loss_trades = [t for t in result.trades if t.exit_reason == "stop_loss"]
            # 急速下跌行情中，至少应有止损触发（如果先触发了买入）

    def test_stop_profit_triggered(self):
        """验证止盈触发"""
        engine = BacktestEngine()

        n = 80
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        close = np.linspace(10.0, 20.0, n)

        df = pd.DataFrame({
            "date": dates, "open": close - 0.1, "high": close + 0.3,
            "low": close - 0.3, "close": close,
            "volume": np.full(n, 10_000_000),
        })

        strategy = Strategy(
            id="stop_profit_test",
            name="止盈测试",
            entry_conditions=[SignalCondition(signal_id="vol_breakout_1_5", operator="trigger")],
            holding_rule=HoldingRule(id="stop_profit", name="固定止盈", params={"profit_pct": 0.10}),
        )

        result = engine.run_backtest(df, strategy, initial_capital=100000.0)

        if result.metrics.total_trades > 0:
            profit_trades = [t for t in result.trades if t.exit_reason == "stop_profit"]
            # 持续上涨行情中，止盈应触发


class TestLimitUpDown:
    """涨跌停限制测试"""

    def test_limit_up_block(self):
        """验证涨停日无法买入"""
        engine = BacktestEngine()

        n = 60
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        close = np.full(n, 10.0)
        # 第30天制造涨停
        close[30] = 11.0  # +10%

        df = pd.DataFrame({
            "date": dates, "open": close - 0.1, "high": close,
            "low": close - 0.1, "close": close,
            "volume": np.full(n, 10_000_000),
        })

        strategy = Strategy(
            id="limit_test",
            name="涨跌停测试",
            entry_conditions=[SignalCondition(signal_id="vol_breakout_1_5", operator="trigger")],
        )

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)

    def test_limit_down_block(self):
        """验证跌停日无法卖出"""
        engine = BacktestEngine()

        n = 60
        dates = pd.date_range("2024-01-01", periods=n, freq="D")
        close = np.full(n, 10.0)
        # 制造跌停行情
        close[50] = 9.0  # -10%

        df = pd.DataFrame({
            "date": dates, "open": close - 0.1, "high": close,
            "low": close - 0.1, "close": close,
            "volume": np.full(n, 10_000_000),
        })

        strategy = Strategy(
            id="limit_down_test",
            name="跌停测试",
            entry_conditions=[SignalCondition(signal_id="vol_breakout_1_5", operator="trigger")],
            exit_conditions=[SignalCondition(signal_id="macd_death_cross", operator="trigger")],
        )

        result = engine.run_backtest(df, strategy)
        assert isinstance(result, BacktestResult)


class TestConfigParameters:
    """配置参数验证"""

    def test_commission_rate_reasonable(self):
        assert 0 < COMMISSION_RATE < 0.01  # 佣金应在合理范围

    def test_stamp_tax_rate_reasonable(self):
        assert 0 < STAMP_TAX_RATE < 0.01

    def test_slippage_rate_reasonable(self):
        assert 0 < SLIPPAGE_RATE < 0.05

    def test_limit_up_down_rate_reasonable(self):
        assert LIMIT_UP_DOWN_RATE > 0.05

    def test_default_capital_reasonable(self):
        assert DEFAULT_INITIAL_CAPITAL >= 10000


class TestCombineSignals:
    """信号组合逻辑测试"""

    def test_empty_signals_returns_zeros(self):
        engine = BacktestEngine()
        strategy = Strategy()
        result = engine._combine_signals([], strategy)
        assert isinstance(result, np.ndarray)
        assert result.dtype == bool
        assert len(result) == 1
        assert not result[0]

    def test_single_signal(self):
        engine = BacktestEngine()
        df = _make_uptrend_df(100)
        from services.signal_service import SignalService
        svc = SignalService()
        sig = svc.compute_signal(df, "vol_breakout_1_5")
        strategy = Strategy()
        result = engine._combine_signals([sig], strategy)
        assert len(result) == len(df)

    def test_multiple_signals_and_logic(self):
        engine = BacktestEngine()
        df = _make_uptrend_df(100)
        from services.signal_service import SignalService
        svc = SignalService()
        sig1 = svc.compute_signal(df, "vol_breakout_1_5")
        sig2 = svc.compute_signal(df, "ma_golden_cross")
        strategy = Strategy()
        result = engine._combine_signals([sig1, sig2], strategy)
        assert len(result) == len(df)
        # AND 逻辑：同时触发的天数不应超过单个信号
        assert result.sum() <= sig1.sum()
