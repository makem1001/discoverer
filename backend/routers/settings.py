"""
发现者（Discoverer）— 用户设置路由

GET  /api/user/settings  — 获取用户设置
PUT  /api/user/settings  — 更新用户设置

需要 JWT 认证。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User, UserSettings
from models.schemas import SettingsResponse, SettingsUpdateRequest
from routers.auth import get_current_user

logger = logging.getLogger("discoverer.settings")
router = APIRouter()


def _get_or_create_settings(db: Session, user_id: int) -> UserSettings:
    """获取或创建用户设置记录。

    Args:
        db: 数据库会话
        user_id: 用户 ID

    Returns:
        UserSettings 对象
    """
    settings = (
        db.query(UserSettings)
        .filter(UserSettings.user_id == user_id)
        .first()
    )
    if settings is None:
        settings = UserSettings(user_id=user_id, tdx_data_dir="")
        db.add(settings)
        db.commit()
        db.refresh(settings)
        logger.info(f"为用户 {user_id} 创建默认设置")
    return settings


# ══════════════════════════════════════════════════════════
# GET /api/user/settings — 获取用户设置
# ══════════════════════════════════════════════════════════

@router.get("/user/settings")
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户设置，如果不存在则创建并返回默认值。

    Returns:
        {code: 0, data: {tdx_data_dir: "..."}, message: "success"}
    """
    try:
        settings = _get_or_create_settings(db, current_user.id)

        return {
            "code": 0,
            "data": {
                "tdx_data_dir": settings.tdx_data_dir or "",
            },
            "message": "success",
        }
    except Exception as e:
        logger.error(f"获取用户设置失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"获取失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# PUT /api/user/settings — 更新用户设置
# ══════════════════════════════════════════════════════════

@router.put("/user/settings")
async def update_settings(
    req: SettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新当前用户设置（部分更新）。

    Args:
        req: {tdx_data_dir: "..."}

    Returns:
        {code: 0, data: {tdx_data_dir: "..."}, message: "更新成功"}
    """
    try:
        settings = _get_or_create_settings(db, current_user.id)

        update_data = req.model_dump(exclude_unset=True)
        if "tdx_data_dir" in update_data:
            settings.tdx_data_dir = update_data["tdx_data_dir"]

        db.commit()
        db.refresh(settings)

        logger.info(
            f"用户 {current_user.id} 更新设置: tdx_data_dir={settings.tdx_data_dir}"
        )
        return {
            "code": 0,
            "data": {
                "tdx_data_dir": settings.tdx_data_dir or "",
            },
            "message": "更新成功",
        }
    except Exception as e:
        db.rollback()
        logger.error(f"更新用户设置失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"更新失败: {str(e)}"}
