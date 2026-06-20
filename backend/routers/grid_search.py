"""
发现者（Discoverer）— 网格搜索路由

POST /api/backtest/grid-search        — 启动网格搜索
GET  /api/backtest/grid-search/{id}   — 查询进度/结果
"""

import uuid
import logging

from fastapi import APIRouter, HTTPException

from models.schemas import GridSearchRequest, GridSearchJob
from models.signals import get_classic_strategy
from services.grid_search import start_grid_search, get_jobs_store

logger = logging.getLogger("discoverer.grid_search_router")
router = APIRouter()


@router.post("/backtest/grid-search")
async def launch_grid_search(request: GridSearchRequest):
    """启动一个网格搜索异步任务。

    返回 job_id，前端轮询 GET /backtest/grid-search/{job_id} 获取进度。
    """
    # 预校验：策略存在性
    if get_classic_strategy(request.strategy_id) is None:
        return {"code": -1, "data": None, "message": f"经典策略 '{request.strategy_id}' 不存在"}

    # 预校验：参数范围合法性
    if request.x_param.min_value >= request.x_param.max_value:
        return {"code": -1, "data": None, "message": f"X参数 '{request.x_param.name}' 最小值应小于最大值"}
    if request.y_param.min_value >= request.y_param.max_value:
        return {"code": -1, "data": None, "message": f"Y参数 '{request.y_param.name}' 最小值应小于最大值"}

    try:
        job_id = str(uuid.uuid4())[:8]
        start_grid_search(job_id, request)
        logger.info(f"网格搜索任务已启动: job_id={job_id}, "
                     f"stock={request.stock_code}, strategy={request.strategy_id}")
        return {
            "code": 0,
            "data": {"job_id": job_id},
            "message": "网格搜索已启动",
        }
    except Exception as e:
        logger.error(f"启动网格搜索失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"启动失败: {str(e)}"}


@router.get("/backtest/grid-search/{job_id}")
async def get_grid_search_status(job_id: str):
    """查询网格搜索任务的进度与结果。

    状态流转: pending → running → completed / failed
    """
    store = get_jobs_store()
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")

    return {
        "code": 0,
        "data": job.model_dump(),
        "message": "success",
    }
