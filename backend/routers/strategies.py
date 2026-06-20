"""
发现者（Discoverer）— 策略 CRUD 路由

GET    /api/strategies          — 我的策略列表
POST   /api/strategies          — 创建策略
GET    /api/strategies/{id}     — 策略详情
PUT    /api/strategies/{id}     — 更新策略
DELETE /api/strategies/{id}     — 删除策略

所有端点需要 JWT 认证。
"""

from __future__ import annotations

import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import StrategyRecord, User
from models.schemas import (
    StrategyCreateRequest,
    StrategyUpdateRequest,
    StrategyResponse,
)
from routers.auth import get_current_user

logger = logging.getLogger("discoverer.strategies")
router = APIRouter()


def _strategy_to_response(record: StrategyRecord) -> dict:
    """将 StrategyRecord ORM 对象转为字典响应，含 JSON 字段解析。

    Args:
        record: StrategyRecord ORM 对象

    Returns:
        字典，JSON 字段已解析为 Python 对象
    """
    return {
        "id": record.id,
        "user_id": record.user_id,
        "name": record.name,
        "description": record.description or "",
        "raw_text": record.raw_text or "",
        "entry_conditions": json.loads(record.entry_conditions or "[]"),
        "exit_conditions": json.loads(record.exit_conditions or "[]"),
        "holding_rule": json.loads(record.holding_rule or "{}") if record.holding_rule and record.holding_rule != "{}" else None,
        "params": json.loads(record.params or "{}"),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _verify_ownership(record: StrategyRecord, current_user: User) -> None:
    """验证策略记录是否属于当前用户，否则抛出 403。

    Args:
        record: 策略记录
        current_user: 当前登录用户

    Raises:
        HTTPException: 403 如果策略不属于当前用户
    """
    if record.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该策略")


# ══════════════════════════════════════════════════════════
# GET /api/strategies — 我的策略列表
# ══════════════════════════════════════════════════════════

@router.get("/strategies")
async def list_strategies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的所有保存策略列表。

    Returns:
        {code: 0, data: [...StrategyResponse], message: "success"}
    """
    try:
        records = (
            db.query(StrategyRecord)
            .filter(StrategyRecord.user_id == current_user.id)
            .order_by(StrategyRecord.updated_at.desc())
            .all()
        )

        result = [_strategy_to_response(r) for r in records]
        logger.info(f"用户 {current_user.id} 策略列表查询: {len(result)} 条")
        return {"code": 0, "data": result, "message": "success"}
    except Exception as e:
        logger.error(f"查询策略列表失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"查询失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# POST /api/strategies — 创建策略
# ══════════════════════════════════════════════════════════

@router.post("/strategies")
async def create_strategy(
    req: StrategyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建一条新策略。

    Args:
        req: 策略创建请求体

    Returns:
        {code: 0, data: StrategyResponse, message: "创建成功"}
    """
    try:
        record = StrategyRecord(
            user_id=current_user.id,
            name=req.name,
            description=req.description or "",
            raw_text=req.raw_text or "",
            entry_conditions=json.dumps(
                [c.model_dump() for c in req.entry_conditions],
                ensure_ascii=False,
            ),
            exit_conditions=json.dumps(
                [c.model_dump() for c in req.exit_conditions],
                ensure_ascii=False,
            ),
            holding_rule=json.dumps(
                req.holding_rule.model_dump() if req.holding_rule else {},
                ensure_ascii=False,
            ),
            params=json.dumps(req.params, ensure_ascii=False),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(f"用户 {current_user.id} 创建策略: id={record.id}, name={record.name}")
        return {
            "code": 0,
            "data": _strategy_to_response(record),
            "message": "创建成功",
        }
    except Exception as e:
        db.rollback()
        logger.error(f"创建策略失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"创建失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# GET /api/strategies/{id} — 策略详情
# ══════════════════════════════════════════════════════════

@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取指定策略详情，验证所有权。

    Args:
        strategy_id: 策略 ID

    Returns:
        {code: 0, data: StrategyResponse, message: "success"}
    """
    try:
        record = (
            db.query(StrategyRecord)
            .filter(StrategyRecord.id == strategy_id)
            .first()
        )

        if record is None:
            return {"code": -1, "data": None, "message": "策略不存在"}

        _verify_ownership(record, current_user)

        return {
            "code": 0,
            "data": _strategy_to_response(record),
            "message": "success",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询策略详情失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"查询失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# PUT /api/strategies/{id} — 更新策略
# ══════════════════════════════════════════════════════════

@router.put("/strategies/{strategy_id}")
async def update_strategy(
    strategy_id: int,
    req: StrategyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """部分更新策略，仅修改传入的字段。

    Args:
        strategy_id: 策略 ID
        req: 更新请求体（所有字段可选）

    Returns:
        {code: 0, data: StrategyResponse, message: "更新成功"}
    """
    try:
        record = (
            db.query(StrategyRecord)
            .filter(StrategyRecord.id == strategy_id)
            .first()
        )

        if record is None:
            return {"code": -1, "data": None, "message": "策略不存在"}

        _verify_ownership(record, current_user)

        # 部分更新：仅修改传入的字段
        update_data = req.model_dump(exclude_unset=True)

        if "name" in update_data:
            record.name = update_data["name"]
        if "description" in update_data:
            record.description = update_data["description"]
        if "raw_text" in update_data:
            record.raw_text = update_data["raw_text"]
        if "entry_conditions" in update_data:
            record.entry_conditions = json.dumps(
                [c if isinstance(c, dict) else c.model_dump() for c in update_data["entry_conditions"]],
                ensure_ascii=False,
            )
        if "exit_conditions" in update_data:
            record.exit_conditions = json.dumps(
                [c if isinstance(c, dict) else c.model_dump() for c in update_data["exit_conditions"]],
                ensure_ascii=False,
            )
        if "holding_rule" in update_data:
            hr = update_data["holding_rule"]
            if hr is not None:
                record.holding_rule = json.dumps(
                    hr if isinstance(hr, dict) else hr.model_dump(),
                    ensure_ascii=False,
                )
            else:
                record.holding_rule = "{}"
        if "params" in update_data:
            record.params = json.dumps(update_data["params"], ensure_ascii=False)

        db.commit()
        db.refresh(record)

        logger.info(f"用户 {current_user.id} 更新策略: id={record.id}, name={record.name}")
        return {
            "code": 0,
            "data": _strategy_to_response(record),
            "message": "更新成功",
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"更新策略失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"更新失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# DELETE /api/strategies/{id} — 删除策略
# ══════════════════════════════════════════════════════════

@router.delete("/strategies/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除指定策略，验证所有权。

    Args:
        strategy_id: 策略 ID

    Returns:
        {code: 0, data: null, message: "删除成功"}
    """
    try:
        record = (
            db.query(StrategyRecord)
            .filter(StrategyRecord.id == strategy_id)
            .first()
        )

        if record is None:
            return {"code": -1, "data": None, "message": "策略不存在"}

        _verify_ownership(record, current_user)

        db.delete(record)
        db.commit()

        logger.info(f"用户 {current_user.id} 删除策略: id={strategy_id}, name={record.name}")
        return {"code": 0, "data": None, "message": "删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除策略失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"删除失败: {str(e)}"}
