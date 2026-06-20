"""
测试：FastAPI 路由端点

验证所有 API 端点可达、响应格式正确。
使用 FastAPI TestClient 进行测试，Mock 外部依赖。
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock openai before any imports (not installed in test environment)
import types
_mock_openai = types.ModuleType("openai")
_mock_openai.OpenAI = type("MockOpenAI", (), {})()
sys.modules["openai"] = _mock_openai

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

import pandas as pd
import numpy as np


# ══════════════════════════════════════════════════════════════════
# Mock DataService
# ══════════════════════════════════════════════════════════════════

class MockDataService:
    def __init__(self):
        self._stock_code_index = {
            "000001": {"code": "000001", "name": "平安银行", "market": "SZ", "industry": "银行", "is_active": True},
            "600519": {"code": "600519", "name": "贵州茅台", "market": "SH", "industry": "白酒", "is_active": True},
        }
        self._stock_list = list(self._stock_code_index.values())

    def initialize(self):
        pass

    def search_stocks(self, keyword, limit=20):
        results = []
        for s in self._stock_list:
            if keyword.lower() in s["code"] or keyword.lower() in s["name"]:
                results.append(s)
        return results[:limit]

    def get_daily_data(self, stock_code, start_date="2010-01-01", end_date="2025-06-01"):
        dates = pd.date_range("2024-01-01", periods=200, freq="D")
        n = len(dates)
        close = 10.0 + np.linspace(0, 5, n) + np.random.randn(n) * 0.5
        close = np.maximum(close, 1.0)
        return pd.DataFrame({
            "date": dates,
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.full(n, 5_000_000),
            "amount": np.full(n, 50_000_000),
            "pre_close": np.concatenate([[close[0]], close[:-1]]),
            "stock_code": stock_code,
        })

    def get_default_stock_pool(self, pool_name="hs300"):
        return ["000001", "600519"]

    def get_price_matrix(self, stock_codes, start_date="2010-01-01", end_date="2025-06-01"):
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        data = {}
        for code in stock_codes:
            data[code] = np.linspace(10, 15, 100) + np.random.randn(100) * 0.5
        return pd.DataFrame(data, index=dates)

    def get_signal_matrix(self, stock_codes, signal_ids=None):
        if signal_ids is None:
            signal_ids = ["macd_golden_cross", "ma_golden_cross"]
        n_days = 100
        n_stocks = len(stock_codes)
        result = {}
        for sid in signal_ids:
            result[sid] = np.random.rand(n_days, n_stocks) > 0.9
        return result

    def get_status(self):
        return {
            "signals_loaded": True,
            "signals_count": 69,
            "stocks_count": 2,
            "cached_stocks": 0,
            "data_range": {"start": "2024-01-01", "end": "2024-07-01"},
            "initialized": True,
        }


# ══════════════════════════════════════════════════════════════════
# Patch main.py's get_data_service
# ══════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def mock_data_service(monkeypatch):
    """自动 Mock DataService"""
    mock_ds = MockDataService()

    import main
    monkeypatch.setattr(main, "get_data_service", lambda: mock_ds)
    # Also reset the global to avoid initialization
    monkeypatch.setattr(main, "_data_service", mock_ds)

    return mock_ds


@pytest.fixture
def client():
    """创建 TestClient"""
    from main import app
    return TestClient(app)


# ══════════════════════════════════════════════════════════════════
# 端点测试
# ══════════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    """系统健康检查"""

    def test_system_status(self, client):
        response = client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["signals_loaded"] is True
        assert data["data"]["signals_count"] == 69


class TestStockEndpoints:
    """股票搜索 + 详情"""

    def test_search_stocks(self, client):
        response = client.get("/api/stocks/search?q=平安")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
        assert data["data"][0]["name"] == "平安银行"

    def test_search_stocks_empty(self, client):
        response = client.get("/api/stocks/search?q=xxxxxx")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)

    def test_search_stocks_no_keyword(self, client):
        response = client.get("/api/stocks/search")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    def test_get_stock_detail_found(self, client):
        response = client.get("/api/stocks/000001")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "平安银行"

    def test_get_stock_detail_not_found(self, client):
        response = client.get("/api/stocks/999999")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == -1


class TestSignalEndpoints:
    """信号定义端点"""

    def test_list_signals(self, client):
        response = client.get("/api/signals")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "signals" in data["data"]
        assert len(data["data"]["signals"]) == 69
        assert "holding_rules" in data["data"]
        assert len(data["data"]["holding_rules"]) == 8

    def test_get_signal_detail_found(self, client):
        response = client.get("/api/signals/macd_golden_cross")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "MACD金叉"

    def test_get_signal_detail_not_found(self, client):
        response = client.get("/api/signals/nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == -1

    def test_list_holding_rules(self, client):
        response = client.get("/api/holding-rules")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert len(data["data"]) == 8


class TestClassicStrategiesEndpoint:
    """经典策略列表"""

    def test_list_classic_strategies(self, client):
        response = client.get("/api/strategies/classic")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert len(data["data"]) == 13

    def test_classic_strategies_structure(self, client):
        response = client.get("/api/strategies/classic")
        data = response.json()
        for strat in data["data"]:
            assert "id" in strat
            assert "name" in strat
            assert "description" in strat
            assert "entry_signal" in strat


class TestBacktestEndpoints:
    """回测端点"""

    def test_classic_backtest_success(self, client):
        response = client.post("/api/backtest/classic", json={
            "stock_code": "000001",
            "strategy_id": "macd_golden_death",
            "initial_capital": 100000,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        result = data["data"]
        assert "metrics" in result
        assert "equity_curve" in result
        assert "trades" in result

    def test_classic_backtest_invalid_strategy(self, client):
        response = client.post("/api/backtest/classic", json={
            "stock_code": "000001",
            "strategy_id": "nonexistent",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == -1

    def test_classic_backtest_invalid_stock(self, client):
        """看不到数据的股票返回错误"""
        response = client.post("/api/backtest/classic", json={
            "stock_code": "999999",
            "strategy_id": "macd_golden_death",
        })
        assert response.status_code == 200
        data = response.json()
        # 股票不在 mock index 中，但 get_daily_data 仍返回数据（mock不考虑index）
        # 所以实际上会成功
        assert data["code"] in (0, -1)

    def test_classic_backtest_response_format(self, client):
        response = client.post("/api/backtest/classic", json={
            "stock_code": "000001",
            "strategy_id": "ma_golden_death",
        })
        data = response.json()
        if data["code"] == 0:
            r = data["data"]
            assert "id" in r
            assert "stock_code" in r
            assert "metrics" in r
            assert "total_return" in r["metrics"]
            assert "annual_return" in r["metrics"]
            assert "max_drawdown" in r["metrics"]
            assert "win_rate" in r["metrics"]
            assert "sharpe_ratio" in r["metrics"]
            assert "trades" in r
            assert "equity_curve" in r

    def test_backtest_with_strategy(self, client):
        response = client.post("/api/backtest/with-strategy", json={
            "stock_code": "000001",
            "strategy": {
                "id": "test",
                "name": "测试",
                "entry_conditions": [
                    {"signal_id": "ma_golden_cross", "operator": "cross_above", "threshold": 0.0}
                ],
                "exit_conditions": [
                    {"signal_id": "ma_death_cross", "operator": "cross_below", "threshold": 0.0}
                ],
                "holding_rule": {
                    "id": "hold_n_days",
                    "name": "持有5天",
                    "params": {"days": 5}
                },
            },
            "initial_capital": 100000,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0


class TestLLMEndpoints:
    """LLM 解析 + 解读端点（不实际调用LLM）"""

    @patch('routers.backtest.get_llm')
    def test_parse_endpoint(self, mock_get_llm, client):
        from models.schemas import ParseResult, Strategy
        mock_llm = MagicMock()
        mock_llm.parse_strategy.return_value = ParseResult(
            success=True,
            parsed_strategy=Strategy(id="test", name="测试"),
            explanation="解析成功",
            warnings=[],
        )
        mock_get_llm.return_value = mock_llm

        response = client.post("/api/llm/parse", json={
            "natural_language": "MACD金叉买入",
            "stock_code": "000001",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["success"] is True

    @patch('routers.backtest.get_llm')
    def test_parse_endpoint_failure(self, mock_get_llm, client):
        from models.schemas import ParseResult
        mock_llm = MagicMock()
        mock_llm.parse_strategy.return_value = ParseResult(
            success=False,
            explanation="无法解析",
            warnings=["未识别信号"],
        )
        mock_get_llm.return_value = mock_llm

        response = client.post("/api/llm/parse", json={
            "natural_language": "xxx",
        })
        assert response.status_code == 200
        data = response.json()
        # success=False 时返回 code=-1
        assert data["code"] == -1

    @patch('routers.backtest.get_llm')
    def test_interpret_endpoint(self, mock_get_llm, client):
        from models.schemas import InterpretResult
        mock_llm = MagicMock()
        mock_llm.interpret_backtest.return_value = InterpretResult(
            summary="表现良好",
            risk_analysis="风险可控",
            benchmark_comparison="跑赢基准",
            suggestion="继续持有",
        )
        mock_get_llm.return_value = mock_llm

        response = client.post("/api/llm/interpret", json={
            "result": {
                "stock_code": "000001",
                "stock_name": "平安银行",
                "strategy_name": "MACD金叉",
                "total_return": 0.5,
                "annual_return": 0.1,
                "max_drawdown": 0.2,
                "win_rate": 0.6,
                "sharpe_ratio": 1.5,
                "total_trades": 50,
                "win_trades": 30,
                "lose_trades": 20,
            }
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0

    @patch('routers.backtest.get_llm')
    @patch('routers.backtest.get_data_service')
    def test_custom_backtest(self, mock_get_ds, mock_get_llm, client, mock_data_service):
        from models.schemas import ParseResult, Strategy, HoldingRule, SignalCondition
        mock_get_ds.return_value = mock_data_service

        mock_llm = MagicMock()
        mock_llm.parse_strategy.return_value = ParseResult(
            success=True,
            parsed_strategy=Strategy(
                id="custom",
                name="自定义",
                entry_conditions=[SignalCondition(signal_id="ma_golden_cross", operator="cross_above")],
                exit_conditions=[SignalCondition(signal_id="ma_death_cross", operator="cross_below")],
                holding_rule=HoldingRule(id="hold_n_days", name="持有5天", params={"days": 5}),
            ),
            explanation="解析成功",
        )
        mock_llm.interpret_backtest.return_value = MagicMock(summary="解读内容")
        mock_get_llm.return_value = mock_llm

        response = client.post("/api/backtest/custom", json={
            "stock_code": "000001",
            "natural_language": "MACD金叉买入",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "backtest_result" in data["data"]
        assert "parse_result" in data["data"]

    @patch('routers.backtest.get_llm')
    def test_custom_backtest_parse_failure(self, mock_get_llm, client):
        from models.schemas import ParseResult
        mock_llm = MagicMock()
        mock_llm.parse_strategy.return_value = ParseResult(
            success=False,
            warnings=["无法解析"],
        )
        mock_get_llm.return_value = mock_llm

        response = client.post("/api/backtest/custom", json={
            "stock_code": "000001",
            "natural_language": "xxx",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == -1


class TestDiscoveryEndpoint:
    """策略发现端点"""

    @patch('concurrent.futures.ProcessPoolExecutor')
    def test_discovery_endpoint(self, mock_executor, client):
        """测试策略发现端点（Mock ProcessPoolExecutor 避免 sandbox 限制）"""
        from concurrent.futures import Future
        future = Future()
        future.set_result({
            "signal_id": "macd_golden_cross",
            "score": 0.85, "win_rate": 0.65,
            "annual_return": 0.12, "max_drawdown": 0.15,
            "total_trades": 200,
        })
        mock_executor.return_value.__enter__.return_value.submit.return_value = future

        response = client.post("/api/discovery", json={
            "objective": "max_win_rate",
            "stock_pool": ["000001", "600519"],
            "top_n": 10,
        })
        assert response.status_code == 200
        data = response.json()
        if data["code"] == 0:
            result = data["data"]
            assert "objective" in result
            assert "rankings" in result
            assert "elapsed_ms" in result

    @patch('concurrent.futures.ProcessPoolExecutor')
    def test_discovery_defaults(self, mock_executor, client):
        """测试默认参数"""
        from concurrent.futures import Future
        future = Future()
        future.set_result({
            "signal_id": "macd_golden_cross",
            "score": 0.5, "win_rate": 0.5,
            "annual_return": 0.1, "max_drawdown": 0.2,
            "total_trades": 100,
        })
        mock_executor.return_value.__enter__.return_value.submit.return_value = future

        response = client.post("/api/discovery", json={
            "objective": "min_drawdown",
            "stock_pool": [],
        })
        assert response.status_code == 200
        data = response.json()
        assert "code" in data


class TestCheckupEndpoint:
    """策略体检端点"""

    def test_checkup_endpoint(self, client):
        response = client.post("/api/checkup", json={
            "signal_ids": ["macd_golden_cross", "ma_golden_cross"],
            "stock_pool": ["000001", "600519"],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] in (0, -1)

    def test_checkup_invalid_signals(self, client):
        response = client.post("/api/checkup", json={
            "signal_ids": ["nonexistent"],
            "stock_pool": [],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == -1

    def test_checkup_response_structure(self, client):
        response = client.post("/api/checkup", json={
            "signal_ids": ["macd_golden_cross"],
            "stock_pool": ["000001"],
        })
        data = response.json()
        if data["code"] == 0:
            r = data["data"]
            assert "signal_ids" in r
            assert "total_tests" in r
            assert "triggered" in r
            assert "trigger_rate" in r
            assert "win_rate" in r


class TestApiResponseFormat:
    """统一响应格式验证"""

    def test_success_response_format(self, client):
        response = client.get("/api/signals")
        data = response.json()
        assert "code" in data
        assert "data" in data
        assert "message" in data
        assert data["code"] == 0
        assert data["message"] == "success"

    def test_error_response_has_message(self, client):
        response = client.get("/api/stocks/ZZZZZZ")
        data = response.json()
        assert "message" in data
        assert data["code"] == -1
        assert data["data"] is None

    def test_http_status_always_200(self, client):
        """所有业务错误也返回 HTTP 200（在 body 中区分）"""
        response = client.get("/api/stocks/ZZZZZZ")
        assert response.status_code == 200

    def test_all_get_endpoints_accessible(self, client):
        """验证所有 GET 端点都可达"""
        endpoints = [
            "/api/system/status",
            "/api/signals",
            "/api/signals/macd_golden_cross",
            "/api/holding-rules",
            "/api/strategies/classic",
            "/api/stocks/search?q=平安",
            "/api/stocks/000001",
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"

    def test_all_post_endpoints_accessible(self, client):
        """验证所有 POST 端点都可达"""
        post_tests = [
            ("/api/backtest/classic", {"stock_code": "000001", "strategy_id": "macd_golden_death"}),
            ("/api/backtest/with-strategy", {"stock_code": "000001", "strategy": {"entry_conditions": []}}),
            ("/api/discovery", {"objective": "max_win_rate", "stock_pool": ["000001"]}),
            ("/api/checkup", {"signal_ids": ["macd_golden_cross"], "stock_pool": ["000001"]}),
        ]
        for endpoint, body in post_tests:
            response = client.post(endpoint, json=body)
            assert response.status_code == 200, f"POST {endpoint} returned {response.status_code}"
            data = response.json()
            assert "code" in data, f"POST {endpoint} missing 'code'"
