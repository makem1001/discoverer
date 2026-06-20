"""
发现者（Discoverer）— 模拟交易路由 (P1-3)

POST   /api/paper/accounts              — 创建模拟账户
GET    /api/paper/accounts              — 列出用户的模拟账户
GET    /api/paper/accounts/{id}         — 获取账户摘要（含持仓、权益曲线）
GET    /api/paper/accounts/{id}/trades  — 获取账户交易记录（分页）
POST   /api/paper/accounts/{id}/advance — 日K前向推进一天
DELETE /api/paper/accounts/{id}         — 删除模拟账户

所有端点需要 JWT 认证。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from config import PAPER_MAX_ACCOUNTS_PER_USER, PAPER_DEFAULT_CAPITAL
from database import get_db
from dependencies import get_paper_engine
from models.db_models import PaperAccountDB, PaperPositionDB, PaperTradeDB, User
from models.schemas import (
    PaperAccountCreate,
    PaperAccountOut,
    PaperAccountSummary,
    PaperPositionOut,
    PaperTradeOut,
    PaperTradeListResponse,
    PaperEquityPoint,
)
from routers.auth import get_current_user
from services.paper_engine import PaperEngine

logger = logging.getLogger("discoverer.paper")
router = APIRouter()


# ── 辅助：ORM → 输出字典 ──────────────────────────────

def _account_to_out(acc: PaperAccountDB) -> PaperAccountOut:
    """将 PaperAccountDB ORM 对象转为 PaperAccountOut Pydantic 模型。"""
    return PaperAccountOut(
        id=acc.id,
        user_id=acc.user_id,
        name=acc.name,
        strategy_id=acc.strategy_id,
        stock_code=acc.stock_code,
        initial_capital=acc.initial_capital,
        current_cash=acc.current_cash,
        total_value=acc.total_value,
        status=acc.status,
        created_at=acc.created_at.isoformat() if acc.created_at else "",
        updated_at=acc.updated_at.isoformat() if acc.updated_at else "",
    )


def _position_to_out(pos: PaperPositionDB) -> PaperPositionOut:
    """将 PaperPositionDB ORM 对象转为 PaperPositionOut Pydantic 模型。"""
    return PaperPositionOut(
        id=pos.id,
        account_id=pos.account_id,
        stock_code=pos.stock_code,
        shares=pos.shares,
        avg_cost=pos.avg_cost,
        current_price=pos.current_price,
        market_value=pos.market_value,
        unrealized_pnl=pos.unrealized_pnl,
        unrealized_pnl_pct=pos.unrealized_pnl_pct,
        open_date=pos.open_date,
    )


def _trade_to_out(trade: PaperTradeDB) -> PaperTradeOut:
    """将 PaperTradeDB ORM 对象转为 PaperTradeOut Pydantic 模型。"""
    return PaperTradeOut(
        id=trade.id,
        account_id=trade.account_id,
        stock_code=trade.stock_code,
        trade_type=trade.trade_type,
        price=trade.price,
        shares=trade.shares,
        fee=trade.fee,
        pnl=trade.pnl,
        pnl_pct=trade.pnl_pct,
        reason=trade.reason,
        traded_at=trade.traded_at.isoformat() if trade.traded_at else "",
    )


def _verify_account_ownership(acc: PaperAccountDB, current_user: User) -> None:
    """验证模拟账户是否属于当前用户，否则抛出 403。"""
    if acc.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该模拟账户")


# ══════════════════════════════════════════════════════════
# POST /api/paper/accounts — 创建模拟账户
# ══════════════════════════════════════════════════════════

@router.post("/paper/accounts")
async def create_paper_account(
    req: PaperAccountCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新的模拟交易账户。

    每个用户最多 PAPER_MAX_ACCOUNTS_PER_USER 个模拟账户。

    Args:
        req: 账户创建请求体

    Returns:
        {code: 0, data: PaperAccountOut, message: "创建成功"}
    """
    try:
        # 检查账户数量上限
        existing_count = (
            db.query(PaperAccountDB)
            .filter(PaperAccountDB.user_id == current_user.id)
            .count()
        )
        if existing_count >= PAPER_MAX_ACCOUNTS_PER_USER:
            return {
                "code": -1, "data": None,
                "message": f"模拟账户数量已达上限（{PAPER_MAX_ACCOUNTS_PER_USER}个）",
            }

        capital = req.initial_capital if req.initial_capital is not None else PAPER_DEFAULT_CAPITAL

        account = PaperAccountDB(
            user_id=current_user.id,
            name=req.name,
            strategy_id=req.strategy_id,
            stock_code=req.stock_code,
            initial_capital=capital,
            current_cash=capital,
            total_value=capital,
            status="running",
        )
        db.add(account)
        db.commit()
        db.refresh(account)

        logger.info(
            "模拟账户创建: id=%s, user=%d, name=%s, capital=%.2f",
            account.id, current_user.id, req.name, capital,
        )

        return {
            "code": 0,
            "data": _account_to_out(account).model_dump(),
            "message": "创建成功",
        }

    except Exception as e:
        db.rollback()
        logger.error("创建模拟账户失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"创建失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# GET /api/paper/accounts — 列出用户的模拟账户
# ══════════════════════════════════════════════════════════

@router.get("/paper/accounts")
async def list_paper_accounts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的所有模拟账户列表。

    Returns:
        {code: 0, data: [PaperAccountOut], message: "success"}
    """
    try:
        accounts = (
            db.query(PaperAccountDB)
            .filter(PaperAccountDB.user_id == current_user.id)
            .order_by(PaperAccountDB.created_at.desc())
            .all()
        )

        result = [_account_to_out(a).model_dump() for a in accounts]
        logger.info("用户 %d 模拟账户列表: %d 个", current_user.id, len(result))
        return {"code": 0, "data": result, "message": "success"}

    except Exception as e:
        logger.error("查询模拟账户列表失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"查询失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# GET /api/paper/accounts/{id} — 获取账户摘要
# ══════════════════════════════════════════════════════════

@router.get("/paper/accounts/{account_id}")
async def get_paper_account_summary(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取模拟账户摘要，含持仓列表、权益曲线。

    Args:
        account_id: 模拟账户 ID

    Returns:
        {code: 0, data: PaperAccountSummary, message: "success"}
    """
    try:
        account = (
            db.query(PaperAccountDB)
            .filter(PaperAccountDB.id == account_id)
            .first()
        )

        if account is None:
            return {"code": -1, "data": None, "message": "模拟账户不存在"}

        _verify_account_ownership(account, current_user)

        # 持仓
        positions = (
            db.query(PaperPositionDB)
            .filter(PaperPositionDB.account_id == account_id)
            .all()
        )
        positions_out = [_position_to_out(p) for p in positions]

        # 计算汇总
        position_value = sum(p.market_value for p in positions)
        total_pnl = account.total_value - account.initial_capital
        total_pnl_pct = total_pnl / account.initial_capital if account.initial_capital > 0 else 0.0

        summary = PaperAccountSummary(
            account_id=account.id,
            total_value=account.total_value,
            current_cash=account.current_cash,
            position_value=position_value,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            position_count=len(positions),
            positions=[p.model_dump() for p in positions_out],
        )

        logger.info(
            "模拟账户摘要: id=%s, total_value=%.2f, positions=%d",
            account_id, account.total_value, len(positions),
        )

        return {
            "code": 0,
            "data": summary.model_dump(),
            "message": "success",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取模拟账户摘要失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"查询失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# GET /api/paper/accounts/{id}/trades — 获取交易记录
# ══════════════════════════════════════════════════════════

@router.get("/paper/accounts/{account_id}/trades")
async def get_paper_account_trades(
    account_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取模拟账户的交易记录，支持分页。

    Args:
        account_id: 模拟账户 ID
        page: 页码（从 1 开始）
        page_size: 每页条数

    Returns:
        {code: 0, data: PaperTradeListResponse, message: "success"}
    """
    try:
        account = (
            db.query(PaperAccountDB)
            .filter(PaperAccountDB.id == account_id)
            .first()
        )

        if account is None:
            return {"code": -1, "data": None, "message": "模拟账户不存在"}

        _verify_account_ownership(account, current_user)

        # 总数
        total = (
            db.query(PaperTradeDB)
            .filter(PaperTradeDB.account_id == account_id)
            .count()
        )

        # 分页查询
        offset = (page - 1) * page_size
        trades = (
            db.query(PaperTradeDB)
            .filter(PaperTradeDB.account_id == account_id)
            .order_by(PaperTradeDB.traded_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        trades_out = [_trade_to_out(t) for t in trades]

        response = PaperTradeListResponse(
            trades=[t.model_dump() for t in trades_out],
            total=total,
            page=page,
            page_size=page_size,
        )

        return {
            "code": 0,
            "data": response.model_dump(),
            "message": "success",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("查询交易记录失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"查询失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# POST /api/paper/accounts/{id}/advance — 日K前向推进一天
# ══════════════════════════════════════════════════════════

@router.post("/paper/accounts/{account_id}/advance")
async def advance_paper_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """对指定模拟账户执行一次日K前向推进。

    调用 PaperEngine 读取当日行情数据，计算信号并执行模拟交易。

    Args:
        account_id: 模拟账户 ID

    Returns:
        {code: 0, data: PaperAccountOut, message: "推进成功"}
    """
    try:
        account = (
            db.query(PaperAccountDB)
            .filter(PaperAccountDB.id == account_id)
            .first()
        )

        if account is None:
            return {"code": -1, "data": None, "message": "模拟账户不存在"}

        _verify_account_ownership(account, current_user)

        if account.status != "running":
            return {"code": -1, "data": None, "message": "账户状态非运行中，无法推进"}

        # 调用 PaperEngine 推进
        engine = get_paper_engine()
        result = engine.advance(
            account_id=account.id,
            stock_code=account.stock_code,
            db=db,
        )

        # 刷新账户状态
        db.refresh(account)

        logger.info(
            "模拟账户推进: id=%s, total_value=%.2f, result=%s",
            account_id, account.total_value, result.get("status", "?"),
        )

        return {
            "code": 0,
            "data": _account_to_out(account).model_dump(),
            "message": "推进成功",
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("模拟账户推进失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"推进失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# DELETE /api/paper/accounts/{id} — 删除模拟账户
# ══════════════════════════════════════════════════════════

@router.delete("/paper/accounts/{account_id}")
async def delete_paper_account(
    account_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除指定模拟账户及其关联的持仓和交易记录（CASCADE）。

    Args:
        account_id: 模拟账户 ID

    Returns:
        {code: 0, data: None, message: "删除成功"}
    """
    try:
        account = (
            db.query(PaperAccountDB)
            .filter(PaperAccountDB.id == account_id)
            .first()
        )

        if account is None:
            return {"code": -1, "data": None, "message": "模拟账户不存在"}

        _verify_account_ownership(account, current_user)

        db.delete(account)
        db.commit()

        logger.info(
            "模拟账户已删除: id=%s, user=%d, name=%s",
            account_id, current_user.id, account.name,
        )

        return {"code": 0, "data": None, "message": "删除成功"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error("删除模拟账户失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"删除失败: {str(e)}"}
