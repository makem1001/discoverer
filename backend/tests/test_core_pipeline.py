"""
核心回测链路集成测试

覆盖：数据获取 → 策略构建 → 回测执行 → 指标计算 → API 端点
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from main import app
from models.schemas import ParamRange, GridSearchRequest
from models.signals import CLASSIC_STRATEGIES, build_strategy_from_classic
from services.grid_search import (
    generate_param_values, generate_param_combinations,
    run_grid_search_sync, _is_better,
)


@pytest.fixture
def client():
    """创建测试客户端"""
    with TestClient(app) as c:
        yield c


class TestCoreBacktestPipeline:
    """核心回测管道"""

    def test_app_starts(self, client):
        """应用启动正常"""
        r = client.get('/api/system/status')
        assert r.status_code == 200
        data = r.json()
        assert data['code'] == 0
        assert data['data']['signals_count'] == 69
        assert data['data']['initialized'] is True

    def test_classic_strategies_available(self, client):
        """经典策略列表可访问"""
        r = client.get('/api/strategies/classic')
        assert r.status_code == 200
        data = r.json()
        assert len(data['data']) >= 13
        ids = [s['id'] for s in data['data']]
        assert 'macd_golden_death' in ids

    def test_stock_search(self, client):
        """股票搜索可用"""
        r = client.get('/api/stocks/search?keyword=平安')
        assert r.status_code == 200
        data = r.json()
        assert data['code'] == 0
        assert len(data['data']) > 0

    def test_strategy_build(self):
        """策略构建：经典策略 → Strategy 对象"""
        strategy = build_strategy_from_classic('macd_golden_death')
        assert strategy is not None
        assert strategy.name == 'MACD金叉死叉'
        assert strategy.entry_conditions is not None
        assert len(strategy.entry_conditions) > 0

    def test_backtest_engine_with_mock_data(self):
        """回测引擎：Mock 数据 + 经典策略"""
        from services.backtest_engine import BacktestEngine
        from dependencies import get_data_service

        ds = get_data_service()
        df = ds.get_daily_data('000001')
        assert not df.empty, "数据获取失败"

        strategy = build_strategy_from_classic('macd_golden_death')
        assert strategy is not None

        engine = BacktestEngine()
        result = engine.run_backtest(df, strategy, 100_000)

        assert result.metrics is not None
        assert result.metrics.total_trades > 0 or result.metrics.total_return == 0
        # 回测产出权益曲线
        assert len(result.equity_curve) > 0


class TestGridSearchPipeline:
    """网格搜索管道"""

    def test_param_values_generation(self):
        """参数值等距生成"""
        param = ParamRange(name='stop_loss_pct', min_value=0.05, max_value=0.15, step=0.02, label='止损')
        vals = generate_param_values(param, 5)
        assert len(vals) == 5
        assert abs(vals[0] - 0.05) < 0.001
        assert abs(vals[-1] - 0.15) < 0.001

    def test_param_combinations(self):
        """参数笛卡尔积"""
        x = ParamRange(name='hold_days', min_value=3, max_value=15, step=2, label='持有天数')
        y = ParamRange(name='stop_loss_pct', min_value=0.03, max_value=0.12, step=2, label='止损')
        combs = generate_param_combinations(x, y, 5)
        assert len(combs) == 25

    def test_is_better_metric_direction(self):
        """指标优化方向正确"""
        # max_drawdown 越小越好
        assert _is_better(0.05, 0.10, 'max_drawdown') is True
        assert _is_better(0.15, 0.10, 'max_drawdown') is False
        # sharpe_ratio 越大越好
        assert _is_better(2.0, 1.5, 'sharpe_ratio') is True
        assert _is_better(1.0, 1.5, 'sharpe_ratio') is False
        # NaN 处理
        assert _is_better(float('nan'), 1.0, 'sharpe_ratio') is False

    def test_grid_search_api(self, client):
        """网格搜索 API 端点可用"""
        req = {
            'stock_code': '000001',
            'strategy_id': 'macd_golden_death',
            'x_param': {'name': 'stop_loss_pct', 'min_value': 0.03, 'max_value': 0.12,
                        'step': 0.02, 'label': '止损'},
            'y_param': {'name': 'take_profit_pct', 'min_value': 0.15, 'max_value': 0.40,
                        'step': 0.05, 'label': '止盈'},
            'target_metric': 'sharpe_ratio',
            'fixed_params': {},
        }
        r = client.post('/api/backtest/grid-search', json=req)
        assert r.status_code == 200
        data = r.json()
        assert data['code'] == 0
        assert 'job_id' in data['data']

        # 轮询直到完成
        job_id = data['data']['job_id']
        import time
        for _ in range(10):
            time.sleep(1)
            r2 = client.get(f'/api/backtest/grid-search/{job_id}')
            job = r2.json()
            if job['data']['status'] in ('completed', 'failed'):
                break

        assert job['data']['status'] in ('completed', 'failed')
        if job['data']['status'] == 'completed':
            result = job['data']['result']
            assert len(result['cells']) == 25
            assert 'heatmap_data' in result


class TestDataService:
    """数据服务"""

    def test_fallback_stock_pool(self):
        """回退股票池可用"""
        from dependencies import get_data_service
        ds = get_data_service()
        assert len(ds._stock_list) > 0

    def test_daily_data_fallback(self):
        """日线数据降级链：TDX → Parquet → akshare → Mock"""
        from dependencies import get_data_service
        ds = get_data_service()
        df = ds.get_daily_data('000001')
        assert not df.empty
        assert 'close' in df.columns
        assert 'date' in df.columns
        # 数据应有来源标记
        assert '_data_source' in df.attrs
