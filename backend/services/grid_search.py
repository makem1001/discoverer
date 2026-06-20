"""
发现者（Discoverer）— 网格搜索调度引擎

对策略的两个维度参数进行笛卡尔积网格搜索，找出最优参数组合。
每个参数维度等分 5 步，共生成 5×5=25 个组合。
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd

from models.schemas import (
    ParamRange, GridSearchRequest, GridCell, GridSearchResult, GridSearchJob,
    Strategy, BacktestResult,
)
from models.signals import build_strategy_from_classic

logger = logging.getLogger("discoverer.grid_search")

# ── 内存任务存储 ──────────────────────────────────────
_jobs_store: Dict[str, GridSearchJob] = {}


def get_jobs_store() -> Dict[str, GridSearchJob]:
    return _jobs_store


# ── 参数组合生成 ──────────────────────────────────────

def generate_param_values(param: ParamRange, steps: int = 5) -> List[float]:
    """生成单个参数的等距取值列表。

    Args:
        param: 参数搜索范围
        steps: 步数（默认 5）

    Returns:
        [min_value, min_value+step, ..., max_value]
    """
    if steps <= 1:
        return [param.min_value]
    values = []
    for i in range(steps):
        val = param.min_value + i * (param.max_value - param.min_value) / (steps - 1)
        # 保留合理精度
        val = round(val, 6)
        values.append(val)
    return values


def generate_param_combinations(
    x_param: ParamRange, y_param: ParamRange, steps: int = 5
) -> List[Tuple[float, float, str, str]]:
    """生成两个参数的笛卡尔积组合。

    Returns:
        [(x_value, y_value, x_label, y_label), ...]
    """
    x_values = generate_param_values(x_param, steps)
    y_values = generate_param_values(y_param, steps)

    def _fmt_label(param: ParamRange, val: float) -> str:
        label = param.label or param.name
        # 百分比类参数显示为百分比
        if "pct" in param.name.lower() or "ratio" in param.name.lower() or "rate" in param.name.lower():
            return f"{label}={val:.1%}"
        elif abs(val) < 0.01 and val != 0.0:
            return f"{label}={val:.4f}"
        elif val == int(val):
            return f"{label}={int(val)}"
        else:
            return f"{label}={val:.2f}"

    combinations = []
    for y_val in y_values:
        for x_val in x_values:
            x_label = _fmt_label(x_param, x_val)
            y_label = _fmt_label(y_param, y_val)
            combinations.append((x_val, y_val, x_label, y_label))
    return combinations


# ── 指标优化方向 ──────────────────────────────────────

_METRIC_HIGHER_BETTER = {
    "total_return", "annual_return", "sharpe_ratio", "win_rate",
    "calmar_ratio", "profit_loss_ratio",
}
_METRIC_LOWER_BETTER = {"max_drawdown", "volatility"}


def _is_better(new_value: float, best_value: float, metric: str) -> bool:
    """判断 new_value 是否优于 best_value。"""
    if np.isnan(new_value) or np.isinf(new_value):
        return False
    if metric in _METRIC_LOWER_BETTER:
        return new_value < best_value
    return new_value > best_value


# ── 网格搜索核心 ──────────────────────────────────────

def _extract_metric(backtest_result: BacktestResult, metric: str) -> float:
    """从 BacktestResult 中提取指定指标值。"""
    m = backtest_result.metrics
    metric_map = {
        "total_return": m.total_return,
        "annual_return": m.annual_return,
        "max_drawdown": m.max_drawdown,
        "sharpe_ratio": m.sharpe_ratio,
        "win_rate": m.win_rate,
        "profit_loss_ratio": m.profit_loss_ratio,
        "calmar_ratio": (m.annual_return / abs(m.max_drawdown)) if m.max_drawdown != 0 else 0.0,
    }
    return metric_map.get(metric, m.total_return)


def _apply_params_to_strategy(
    base_strategy: Strategy,
    x_param_name: str,
    x_value: float,
    y_param_name: str,
    y_value: float,
    fixed_params: Dict[str, float],
) -> Strategy:
    """将网格搜索参数覆盖到策略上，返回新 Strategy 对象。

    参数可能位于以下位置之一：
    - strategy.params（通用参数）
    - strategy.holding_rule.params（持有规则参数如 hold_days, stop_loss_pct）
    """
    strategy = base_strategy.model_copy(deep=True)

    # 持有规则相关参数名
    holding_param_names = {
        "stop_loss_pct", "hold_days", "stop_profit_pct", "trailing_pct",
        "take_profit_pct", "atr_stop_multiplier",
    }

    for param_name, value in [(x_param_name, x_value), (y_param_name, y_value)]:
        if param_name in holding_param_names:
            if strategy.holding_rule is not None:
                strategy.holding_rule.params[param_name] = value
        else:
            strategy.params[param_name] = value

    # 应用固定参数
    for pname, pval in fixed_params.items():
        if pname in holding_param_names:
            if strategy.holding_rule is not None:
                strategy.holding_rule.params[pname] = pval
        else:
            strategy.params[pname] = pval

    return strategy


def run_grid_search_sync(
    request: GridSearchRequest,
    steps: int = 5,
) -> GridSearchResult:
    """同步执行网格搜索。

    Args:
        request: 网格搜索请求
        steps: 每个维度的步数（默认 5）

    Returns:
        GridSearchResult 完整结果
    """
    from dependencies import get_data_service
    from services.backtest_engine import BacktestEngine

    t0 = time.time()

    # 1. 获取基准策略
    base_strategy = build_strategy_from_classic(request.strategy_id)
    if base_strategy is None:
        raise ValueError(f"经典策略 '{request.strategy_id}' 不存在")

    # 2. 获取日线数据
    ds = get_data_service()
    df = ds.get_daily_data(request.stock_code, request.start_date, request.end_date)
    if df.empty:
        raise ValueError(f"未获取到股票 {request.stock_code} 的日线数据")

    # 3. 生成参数组合
    combinations = generate_param_combinations(request.x_param, request.y_param, steps)
    total_combinations = len(combinations)

    # 4. 初始化引擎
    engine = BacktestEngine(data_service=ds)

    # 5. 遍历所有组合执行回测
    cells: List[GridCell] = []
    best_cell: Optional[GridCell] = None

    for idx, (x_val, y_val, x_label, y_label) in enumerate(combinations):
        try:
            # 构建带参数的策略
            strategy = _apply_params_to_strategy(
                base_strategy,
                request.x_param.name,
                x_val,
                request.y_param.name,
                y_val,
                request.fixed_params,
            )

            # 执行回测
            result = engine.run_backtest(df, strategy, request.initial_capital)

            # 提取目标指标
            target_value = _extract_metric(result, request.target_metric)

            # 构建指标快照
            metrics_snapshot = {
                "total_return": result.metrics.total_return,
                "annual_return": result.metrics.annual_return,
                "max_drawdown": result.metrics.max_drawdown,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "win_rate": result.metrics.win_rate,
                "profit_loss_ratio": result.metrics.profit_loss_ratio,
                "total_trades": result.metrics.total_trades,
            }

            cell = GridCell(
                x_value=x_val,
                y_value=y_val,
                x_label=x_label,
                y_label=y_label,
                metrics=metrics_snapshot,
                target_value=round(target_value, 6),
            )
            cells.append(cell)

            # 更新最优
            if best_cell is None or _is_better(
                target_value, best_cell.target_value, request.target_metric
            ):
                best_cell = cell

        except Exception as e:
            logger.warning(f"网格单元 ({x_val}, {y_val}) 回测失败: {e}")
            # 填充错误单元格
            cell = GridCell(
                x_value=x_val,
                y_value=y_val,
                x_label=x_label,
                y_label=y_label,
                metrics={"error": str(e)},
                target_value=float("nan"),
            )
            cells.append(cell)

    # 6. 构建热力图数据 [[xIdx, yIdx, targetValue], ...]
    x_values = generate_param_values(request.x_param, steps)
    y_values = generate_param_values(request.y_param, steps)
    x_index_map = {v: i for i, v in enumerate(x_values)}
    y_index_map = {v: i for i, v in enumerate(y_values)}

    heatmap_data = []
    for cell in cells:
        if not (np.isnan(cell.target_value) or np.isinf(cell.target_value)):
            heatmap_data.append([
                x_index_map.get(cell.x_value, 0),
                y_index_map.get(cell.y_value, 0),
                cell.target_value,
            ])

    # 7. 生成标签列表
    x_vals_unique = generate_param_values(request.x_param, steps)
    y_vals_unique = generate_param_values(request.y_param, steps)

    def _make_label(param, val):
        if "pct" in param.name.lower() or "ratio" in param.name.lower() or "rate" in param.name.lower():
            return f"{val:.1%}"
        elif abs(val) < 0.01 and val != 0.0:
            return f"{val:.4f}"
        elif val == int(val):
            return f"{int(val)}"
        else:
            return f"{val:.2f}"

    x_labels_dedup = [_make_label(request.x_param, v) for v in x_vals_unique]
    y_labels_dedup = [_make_label(request.y_param, v) for v in y_vals_unique]

    elapsed = round(time.time() - t0, 2)

    return GridSearchResult(
        x_param=request.x_param,
        y_param=request.y_param,
        target_metric=request.target_metric,
        cells=cells,
        x_labels=x_labels_dedup,
        y_labels=y_labels_dedup,
        heatmap_data=heatmap_data,
        best_cell=best_cell,
        total_combinations=total_combinations,
        elapsed_seconds=elapsed,
    )


# ── 异步调度封装 ──────────────────────────────────────

async def _run_grid_search_async(job_id: str, request: GridSearchRequest):
    """异步执行网格搜索并更新 job 状态。"""
    job = _jobs_store.get(job_id)
    if job is None:
        return

    try:
        job.status = "running"
        job.progress = 0.0
        job.total = 25  # 5x5
        job.completed = 0

        result = run_grid_search_sync(request, steps=5)

        job.result = result
        job.status = "completed"
        job.progress = 1.0
        job.completed = result.total_combinations
        job.total = result.total_combinations

        logger.info(f"网格搜索完成: job_id={job_id}, "
                     f"elapsed={result.elapsed_seconds}s, "
                     f"best={result.best_cell.target_value if result.best_cell else 'N/A'}")

    except Exception as e:
        logger.error(f"网格搜索失败: job_id={job_id}, error={e}", exc_info=True)
        job.status = "failed"
        job.error = str(e)


def start_grid_search(job_id: str, request: GridSearchRequest):
    """启动异步网格搜索任务。"""
    job = GridSearchJob(
        job_id=job_id,
        status="pending",
        progress=0.0,
        total=25,
        completed=0,
        request=request,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
    _jobs_store[job_id] = job
    asyncio.create_task(_run_grid_search_async(job_id, request))
    return job_id
