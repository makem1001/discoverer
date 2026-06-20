"""
测试：Pydantic 模型序列化/反序列化

验证所有 Request/Response Schema 定义正确，
与架构设计文档一致。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import json
from datetime import date

from models.schemas import (
    Stock, Signal, HoldingRule, SignalCondition, Strategy,
    ClassicBacktestRequest, CustomBacktestRequest, BacktestWithStrategyRequest,
    ParseRequest, DiscoveryRequest, CheckupRequest, InterpretRequest,
    Trade, EquityPoint, BacktestMetrics, YearlyStat,
    BacktestResult, ParseResult, InterpretResult,
    StrategyScore, DiscoveryResult, CheckupResult,
    ApiResponse,
)


class TestBaseModels:
    """基础数据模型测试"""

    def test_stock_model(self):
        s = Stock(code="000001", name="平安银行", market="SZ", industry="银行", is_active=True)
        d = s.model_dump()
        assert d["code"] == "000001"
        assert d["name"] == "平安银行"
        assert d["market"] == "SZ"
        assert d["is_active"] is True

    def test_stock_defaults(self):
        s = Stock(code="600519", name="贵州茅台")
        d = s.model_dump()
        assert d["market"] == "SZ"  # default
        assert d["industry"] == ""
        assert d["is_active"] is True

    def test_signal_model(self):
        s = Signal(id="macd_golden_cross", name="MACD金叉", category="MACD",
                    description="DIF上穿DEA", params={"fast": 12})
        d = s.model_dump()
        assert d["id"] == "macd_golden_cross"
        assert d["params"]["fast"] == 12

    def test_signal_to_dict(self):
        s = Signal(id="test", name="测试", category="测试")
        d = s.to_dict()
        assert d["id"] == "test"

    def test_holding_rule_model(self):
        hr = HoldingRule(id="hold_n_days", name="持有N天",
                          description="固定持有", params={"days": 5})
        d = hr.model_dump()
        assert d["id"] == "hold_n_days"
        assert d["params"]["days"] == 5

    def test_signal_condition_model(self):
        sc = SignalCondition(signal_id="ma_golden_cross", operator="cross_above", threshold=0.0)
        d = sc.model_dump()
        assert d["signal_id"] == "ma_golden_cross"
        assert d["operator"] == "cross_above"

    def test_strategy_model_full(self):
        strategy = Strategy(
            id="test_001",
            name="测试策略",
            raw_text="MACD金叉买入",
            entry_conditions=[
                SignalCondition(signal_id="macd_golden_cross", operator="trigger"),
            ],
            exit_conditions=[
                SignalCondition(signal_id="macd_death_cross", operator="trigger"),
            ],
            holding_rule=HoldingRule(id="hold_n_days", name="持有5天", params={"days": 5}),
            params={"stock_code": "000001"},
        )
        d = strategy.model_dump()
        assert len(d["entry_conditions"]) == 1
        assert len(d["exit_conditions"]) == 1
        assert d["holding_rule"]["id"] == "hold_n_days"

    def test_strategy_model_minimal(self):
        strategy = Strategy()
        d = strategy.model_dump()
        assert d["entry_conditions"] == []
        assert d["holding_rule"] is None


class TestRequestModels:
    """请求模型测试"""

    def test_classic_backtest_request(self):
        req = ClassicBacktestRequest(
            stock_code="000001",
            strategy_id="macd_golden_death",
        )
        d = req.model_dump()
        assert d["stock_code"] == "000001"
        assert d["initial_capital"] == 100_000.0  # default

    def test_custom_backtest_request(self):
        req = CustomBacktestRequest(
            stock_code="000001",
            natural_language="MACD金叉买入",
        )
        d = req.model_dump()
        assert d["natural_language"] == "MACD金叉买入"
        assert d["start_date"] == "2010-01-01"

    def test_backtest_with_strategy_request(self):
        strategy = Strategy(id="test", name="测试")
        req = BacktestWithStrategyRequest(
            stock_code="000001",
            strategy=strategy,
        )
        assert req.strategy.id == "test"

    def test_parse_request(self):
        req = ParseRequest(natural_language="MACD金叉买入", stock_code="000001")
        d = req.model_dump()
        assert d["natural_language"] == "MACD金叉买入"

    def test_parse_request_optional_stock(self):
        req = ParseRequest(natural_language="放量突破买入")
        d = req.model_dump()
        assert d["stock_code"] == ""

    def test_discovery_request(self):
        req = DiscoveryRequest(
            objective="max_win_rate",
            stock_pool=["000001", "000002"],
            top_n=20,
        )
        d = req.model_dump()
        assert d["objective"] == "max_win_rate"
        assert len(d["stock_pool"]) == 2

    def test_discovery_request_defaults(self):
        req = DiscoveryRequest()
        d = req.model_dump()
        assert d["objective"] == "max_win_rate"
        assert d["stock_pool"] == []
        assert d["top_n"] == 20

    def test_checkup_request(self):
        req = CheckupRequest(
            signal_ids=["macd_golden_cross", "vol_breakout_1_5"],
            stock_pool=["000001"],
        )
        d = req.model_dump()
        assert len(d["signal_ids"]) == 2

    def test_interpret_request(self):
        summary = InterpretRequest.BacktestResultSummary(
            stock_code="000001",
            stock_name="平安银行",
            strategy_name="MACD金叉死叉",
            total_return=0.5,
            annual_return=0.1,
            max_drawdown=0.2,
            win_rate=0.6,
            sharpe_ratio=1.5,
            total_trades=50,
        )
        req = InterpretRequest(result=summary)
        d = req.model_dump()
        assert d["result"]["stock_code"] == "000001"
        assert d["result"]["total_trades"] == 50


class TestResponseModels:
    """响应模型测试"""

    def test_trade_model(self):
        t = Trade(entry_date="2020-01-15", entry_price=10.0,
                   exit_date="2020-02-15", exit_price=11.0,
                   return_pct=0.10, exit_reason="signal")
        d = t.model_dump()
        assert d["entry_price"] == 10.0
        assert d["return_pct"] == 0.10

    def test_equity_point(self):
        ep = EquityPoint(date="2020-01-15", equity=105000.0, drawdown=0.02)
        d = ep.model_dump()
        assert d["equity"] == 105000.0
        assert d["drawdown"] == 0.02

    def test_backtest_metrics(self):
        m = BacktestMetrics(
            total_return=0.50, annual_return=0.10, max_drawdown=0.20,
            win_rate=0.60, sharpe_ratio=1.5, profit_loss_ratio=2.0,
            total_trades=100, win_trades=60, lose_trades=40,
            avg_hold_days=12.5,
        )
        d = m.model_dump()
        assert d["total_return"] == 0.50
        assert d["sharpe_ratio"] == 1.5
        assert d["total_trades"] == 100

    def test_yearly_stat(self):
        ys = YearlyStat(year=2020, return_pct=0.15, trades=10, win_rate=0.70)
        d = ys.model_dump()
        assert d["year"] == 2020
        assert d["return_pct"] == 0.15

    def test_backtest_result(self):
        result = BacktestResult(
            id="abc123",
            stock_code="000001",
            stock_name="平安银行",
            metrics=BacktestMetrics(total_return=0.30),
            trades=[Trade(entry_date="2020-01-01", exit_date="2020-01-10",
                          entry_price=10.0, exit_price=10.5, return_pct=0.05,
                          exit_reason="signal")],
            equity_curve=[EquityPoint(date="2020-01-01", equity=100000.0, drawdown=0.0)],
            yearly_stats=[YearlyStat(year=2020, return_pct=0.05)],
            ai_interpretation="策略表现良好",
        )
        d = result.model_dump()
        assert d["stock_code"] == "000001"
        assert len(d["trades"]) == 1
        assert len(d["equity_curve"]) == 1
        assert d["ai_interpretation"] == "策略表现良好"

    def test_parse_result_success(self):
        pr = ParseResult(
            success=True,
            parsed_strategy=Strategy(id="test", name="测试策略"),
            explanation="解析成功",
            warnings=[],
        )
        d = pr.model_dump()
        assert d["success"] is True
        assert d["parsed_strategy"]["name"] == "测试策略"

    def test_parse_result_failure(self):
        pr = ParseResult(
            success=False,
            explanation="无法解析",
            warnings=["未识别信号"],
        )
        d = pr.model_dump()
        assert d["success"] is False
        assert d["parsed_strategy"] is None
        assert len(d["warnings"]) == 1

    def test_interpret_result(self):
        ir = InterpretResult(
            summary="整体表现优异",
            risk_analysis="风险可控",
            benchmark_comparison="跑赢沪深300",
            suggestion="建议继续持有",
        )
        d = ir.model_dump()
        assert d["summary"] == "整体表现优异"
        assert "历史表现不代表未来收益" not in d["summary"]  # no forced prefix

    def test_strategy_score(self):
        ss = StrategyScore(
            signal=Signal(id="macd_golden_cross", name="MACD金叉", category="MACD"),
            score=0.85, win_rate=0.65, annual_return=0.12,
            max_drawdown=0.15, total_trades=200,
        )
        d = ss.model_dump()
        assert d["score"] == 0.85
        assert d["signal"]["name"] == "MACD金叉"

    def test_discovery_result(self):
        dr = DiscoveryResult(
            objective="max_win_rate",
            rankings=[
                StrategyScore(score=0.9, win_rate=0.7, annual_return=0.15,
                              max_drawdown=0.1, total_trades=100),
            ],
            elapsed_ms=500.0,
        )
        d = dr.model_dump()
        assert d["objective"] == "max_win_rate"
        assert len(d["rankings"]) == 1
        assert d["elapsed_ms"] == 500.0

    def test_checkup_result(self):
        cr = CheckupResult(
            signal_ids=["macd_golden_cross"],
            total_tests=10000, triggered=500,
            trigger_rate=0.05, win_rate=0.55,
            avg_return=0.02, best_return=0.30,
            worst_return=-0.15,
            yearly_distribution=[],
            ai_report="体检报告内容",
        )
        d = cr.model_dump()
        assert d["total_tests"] == 10000
        assert d["triggered"] == 500
        assert d["trigger_rate"] == 0.05

    def test_api_response(self):
        resp = ApiResponse(code=0, data={"key": "value"}, message="success")
        d = resp.model_dump()
        assert d["code"] == 0
        assert d["data"]["key"] == "value"

    def test_api_response_error(self):
        resp = ApiResponse(code=-1, data=None, message="错误信息")
        d = resp.model_dump()
        assert d["code"] == -1
        assert d["data"] is None


class TestModelRoundTrip:
    """序列化/反序列化往返测试"""

    def test_backtest_result_round_trip(self):
        """验证 BacktestResult JSON 序列化后反序列化一致"""
        original = BacktestResult(
            id="r001",
            stock_code="000001",
            stock_name="平安银行",
            metrics=BacktestMetrics(
                total_return=0.50, annual_return=0.10,
                max_drawdown=0.20, win_rate=0.60,
                sharpe_ratio=1.5, profit_loss_ratio=2.0,
                total_trades=50, win_trades=30, lose_trades=20,
                avg_hold_days=8.5,
            ),
        )
        json_str = original.model_dump_json()
        restored = BacktestResult.model_validate_json(json_str)
        assert restored.id == original.id
        assert restored.metrics.total_return == original.metrics.total_return
        assert restored.metrics.sharpe_ratio == original.metrics.sharpe_ratio

    def test_strategy_round_trip(self):
        original = Strategy(
            id="s001", name="测试",
            entry_conditions=[SignalCondition(signal_id="ma_golden_cross", operator="cross_above")],
            holding_rule=HoldingRule(id="hold_n_days", name="持有5天", params={"days": 5}),
        )
        json_str = original.model_dump_json()
        restored = Strategy.model_validate_json(json_str)
        assert restored.name == "测试"
        assert len(restored.entry_conditions) == 1
        assert restored.holding_rule.id == "hold_n_days"


class TestTypeValidation:
    """类型验证测试"""

    def test_strategy_score_signal_optional(self):
        """StrategyScore 的 signal 字段可以为 None"""
        ss = StrategyScore(score=0.5, win_rate=0.5, annual_return=0.1,
                           max_drawdown=0.2, total_trades=10)
        assert ss.signal is None

    def test_backtestresult_strategy_optional(self):
        """BacktestResult 的 strategy 字段可以为 None"""
        br = BacktestResult(id="test", stock_code="000001")
        assert br.strategy is None

    def test_parse_request_validation(self):
        """ParseRequest natural_language 必填"""
        with pytest.raises(Exception):
            ParseRequest()  # 缺少必填字段

    def test_classic_backtest_request_validation(self):
        """ClassicBacktestRequest stock_code 和 strategy_id 必填"""
        with pytest.raises(Exception):
            ClassicBacktestRequest()  # 缺少必填字段

    def test_checkup_request_validation(self):
        """CheckupRequest signal_ids 必填"""
        with pytest.raises(Exception):
            CheckupRequest()  # 缺少必填字段
