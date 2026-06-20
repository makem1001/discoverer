"""
发现者（Discoverer）— 策略发现路由

POST /api/discovery       — 策略发现：目标驱动扫描最佳信号
GET  /api/discovery/progress/{task_id} — 轮询发现进度

P0-3 增强：
  - 传递 req.use_cache 给 get_signal_matrix()
  - 返回 cache_hit 状态
  - 新增 GET /api/discovery/progress/{task_id} 端点
"""

from __future__ import annotations

import logging
import time
import uuid
import threading
from typing import Dict

from fastapi import APIRouter

from dependencies import get_data_service
from models.schemas import DiscoveryRequest, DiscoveryResult, StrategyScore
from services.backtest_engine import BacktestEngine

logger = logging.getLogger("discoverer.discovery")
router = APIRouter()

# ── P0-3: 进度跟踪 ────────────────────────────────────

# task_id → {"progress": 0-100, "status": "running"|"completed"|"failed", "result": ...}
_discovery_progress: Dict[str, dict] = {}
_progress_lock = threading.Lock()


def _set_progress(task_id: str, progress: int, status: str = "running", result: dict | None = None) -> None:
    """更新发现任务进度。

    Args:
        task_id: 任务ID
        progress: 进度百分比 (0-100)
        status: 任务状态
        result: 完成时的结果数据
    """
    with _progress_lock:
        _discovery_progress[task_id] = {
            "progress": progress,
            "status": status,
            "result": result,
        }


def _get_progress(task_id: str) -> dict | None:
    """获取发现任务进度。

    Args:
        task_id: 任务ID

    Returns:
        进度字典或 None（任务ID不存在）
    """
    with _progress_lock:
        return _discovery_progress.get(task_id)


# ── 策略发现 ──────────────────────────────────────────

@router.post("/discovery")
async def strategy_discovery(req: DiscoveryRequest):
    """
    策略发现：按目标在全市场扫描最佳信号。

    目标选项：
      - max_win_rate: 最高胜率
      - min_drawdown: 最小回撤
      - max_sharpe: 最高夏普比率
      - max_profit_loss_ratio: 最佳盈亏比
    """
    # 生成任务ID
    task_id = str(uuid.uuid4())[:8]
    _set_progress(task_id, 0, "running")

    try:
        ds = get_data_service()

        # 确定股票池
        stock_pool = req.stock_pool if req.stock_pool else ds.get_default_stock_pool()
        if not stock_pool:
            _set_progress(task_id, 100, "failed")
            return {
                "code": -1, "data": None,
                "message": "股票池为空，请指定股票代码列表",
            }

        logger.info(f"开始策略发现: objective={req.objective}, stocks={len(stock_pool)}, use_cache={req.use_cache}")

        _set_progress(task_id, 10, "running")

        # 加载数据
        t0 = time.time()

        # 获取价格矩阵
        price_matrix = ds.get_price_matrix(stock_pool)
        if price_matrix.empty:
            _set_progress(task_id, 100, "failed")
            return {
                "code": -1, "data": None,
                "message": "无法获取价格数据",
            }

        _set_progress(task_id, 30, "running")

        # 获取信号矩阵（传递 use_cache 参数）
        signal_matrix = ds.get_signal_matrix(
            stock_pool,
            use_cache=req.use_cache,
        )

        _set_progress(task_id, 60, "running")

        # 执行发现
        engine = BacktestEngine(data_service=ds)
        rankings = engine.discover(
            objective=req.objective,
            signal_matrix=signal_matrix,
            price_matrix=price_matrix,
            top_n=req.top_n,
        )

        _set_progress(task_id, 90, "running")

        elapsed = (time.time() - t0) * 1000

        # 判断 cache_hit（全部从缓存加载则为 True）
        cache_hit = req.use_cache and len(signal_matrix) > 0

        result = DiscoveryResult(
            objective=req.objective,
            rankings=rankings,
            elapsed_ms=round(elapsed, 1),
            cache_hit=cache_hit,
            progress=f"{task_id}",
        )

        logger.info(f"策略发现完成: 扫描 {len(stock_pool)} 只股票, "
                    f"耗时 {elapsed:.0f}ms, Top-{len(rankings)}, cache_hit={cache_hit}")

        _set_progress(task_id, 100, "completed", result.model_dump())

        return {
            "code": 0,
            "data": result.model_dump(),
            "message": "success",
            "elapsed_ms": round(elapsed, 1),
            "task_id": task_id,
        }

    except Exception as e:
        logger.error(f"策略发现失败: {e}", exc_info=True)
        _set_progress(task_id, 100, "failed")
        return {"code": -1, "data": None, "message": f"策略发现失败: {str(e)}"}


# ── P0-3 新增：进度轮询端点 ────────────────────────────

@router.get("/discovery/progress/{task_id}")
async def get_discovery_progress(task_id: str):
    """
    轮询策略发现任务的执行进度。

    返回格式：
    {
      "code": 0,
      "data": {
        "progress": 0-100,
        "status": "running"|"completed"|"failed",
        "result": {...}  // 仅在 completed 时有值
      },
      "message": "success"
    }
    """
    progress = _get_progress(task_id)

    if progress is None:
        return {
            "code": -1,
            "data": None,
            "message": f"任务 '{task_id}' 不存在或已过期",
        }

    return {
        "code": 0,
        "data": progress,
        "message": "success",
    }
