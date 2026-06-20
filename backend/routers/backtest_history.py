"""
发现者（Discoverer）— 回测历史路由

GET /api/backtest/history       — 回测历史列表
GET /api/backtest/history/{id}  — 回测详情

需要 JWT 认证。
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import get_db
from models.db_models import BacktestRecord, StrategyRecord, User
from routers.auth import get_current_user

logger = logging.getLogger("discoverer.backtest_history")
router = APIRouter()


def _record_to_response(record: BacktestRecord, include_result_data: bool = False) -> dict:
    """将 BacktestRecord ORM 对象转为字典响应。

    Args:
        record: BacktestRecord ORM 对象
        include_result_data: 是否包含 result_data 字段（详情用）

    Returns:
        字典
    """
    resp = {
        "id": record.id,
        "user_id": record.user_id,
        "strategy_id": record.strategy_id,
        "stock_code": record.stock_code,
        "stock_name": record.stock_name or "",
        "start_date": record.start_date,
        "end_date": record.end_date,
        "total_return": record.total_return or 0.0,
        "annual_return": record.annual_return or 0.0,
        "max_drawdown": record.max_drawdown or 0.0,
        "win_rate": record.win_rate or 0.0,
        "sharpe_ratio": record.sharpe_ratio or 0.0,
        "profit_loss_ratio": record.profit_loss_ratio or 0.0,
        "total_trades": record.total_trades or 0,
        "data_source": record.data_source or "mock",
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }

    if include_result_data:
        resp["result_data"] = (
            json.loads(record.result_data or "{}")
            if record.result_data
            else {"trades": [], "equity_curve": []}
        )

    return resp


def _build_strategy_name_map(db: Session, records: list) -> dict:
    """为一批回测记录构建 strategy_id → strategy_name 的映射。

    Args:
        db: 数据库会话
        records: 回测记录列表

    Returns:
        {strategy_id: strategy_name} 字典
    """
    strategy_ids = {r.strategy_id for r in records if r.strategy_id is not None}
    if not strategy_ids:
        return {}
    strategies = (
        db.query(StrategyRecord)
        .filter(StrategyRecord.id.in_(strategy_ids))
        .all()
    )
    return {s.id: s.name for s in strategies}


# ══════════════════════════════════════════════════════════
# GET /api/backtest/history — 回测历史列表
# ══════════════════════════════════════════════════════════

@router.get("/backtest/history")
async def list_backtest_history(
    strategy_id: Optional[int] = Query(default=None, description="筛选策略ID"),
    stock_code: Optional[str] = Query(default=None, description="筛选股票代码"),
    start_date: Optional[str] = Query(default=None, description="回测起始日期"),
    end_date: Optional[str] = Query(default=None, description="回测结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的回测历史列表（最近 50 条），支持筛选。

    Returns:
        {code: 0, data: [...], message: "success"}
    """
    try:
        query = (
            db.query(BacktestRecord)
            .filter(BacktestRecord.user_id == current_user.id)
        )

        # 可选筛选条件
        if strategy_id is not None:
            query = query.filter(BacktestRecord.strategy_id == strategy_id)
        if stock_code:
            query = query.filter(BacktestRecord.stock_code.like(f"%{stock_code}%"))
        if start_date:
            query = query.filter(BacktestRecord.start_date >= start_date)
        if end_date:
            query = query.filter(BacktestRecord.end_date <= end_date)

        query = query.order_by(desc(BacktestRecord.created_at)).limit(50)
        records = query.all()

        # 构建策略名称映射
        strategy_name_map = _build_strategy_name_map(db, records)

        result = [
            {
                **_record_to_response(r, include_result_data=False),
                "strategy_name": strategy_name_map.get(r.strategy_id, ""),
            }
            for r in records
        ]

        logger.info(
            f"用户 {current_user.id} 回测历史查询: {len(result)} 条"
        )
        return {"code": 0, "data": result, "message": "success"}
    except Exception as e:
        logger.error(f"查询回测历史失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"查询失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# GET /api/backtest/history/{id} — 回测详情
# ══════════════════════════════════════════════════════════

@router.get("/backtest/history/{record_id}")
async def get_backtest_detail(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取回测详情，验证记录属于当前用户，包含 result_data。

    Args:
        record_id: 回测记录 ID

    Returns:
        {code: 0, data: BacktestHistoryDetail, message: "success"}
    """
    try:
        record = (
            db.query(BacktestRecord)
            .filter(BacktestRecord.id == record_id)
            .first()
        )

        if record is None:
            return {"code": -1, "data": None, "message": "回测记录不存在"}

        if record.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权限访问该记录")

        # 获取策略名称
        strategy_name = ""
        if record.strategy_id:
            strategy = (
                db.query(StrategyRecord)
                .filter(StrategyRecord.id == record.strategy_id)
                .first()
            )
            if strategy:
                strategy_name = strategy.name

        result = {
            **_record_to_response(record, include_result_data=True),
            "strategy_name": strategy_name,
        }

        logger.info(
            f"用户 {current_user.id} 查看回测详情: id={record.id}"
        )
        return {"code": 0, "data": result, "message": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询回测详情失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"查询失败: {str(e)}"}
