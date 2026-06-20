"""
认证路由 — 注册/登录/刷新/获取当前用户
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from database import get_db
from models.db_models import User
from models.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from services.auth_service import AuthService

logger = logging.getLogger("discoverer.auth")

router = APIRouter()

# ── JWT 安全方案 ───────────────────────────────────────
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """JWT 依赖注入：验证 access token 并返回 User 对象。

    Raises:
        HTTPException: 401 如果 token 无效或用户不存在
    """
    token = credentials.credentials
    user_id = AuthService.verify_token(token, "access")
    if user_id is None:
        raise HTTPException(status_code=401, detail="未授权访问")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


# ══════════════════════════════════════════════════════════
# POST /api/auth/register — 邮箱注册
# ══════════════════════════════════════════════════════════

@router.post("/auth/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """注册新用户。"""
    # 合规校验：必须同意风险告知书
    if not req.agreed_risk_disclosure:
        return {"code": -1, "data": None, "message": "请阅读并同意《风险告知书》"}

    logger.info("收到注册请求: email=%s", req.email)
    result = AuthService.register(
        db, req.email, req.password,
        agreed_risk_at=datetime.now(timezone.utc),
    )
    if result["success"]:
        return {"code": 0, "data": {"user_id": result["user_id"], "email": req.email}, "message": result["message"]}
    return {"code": -1, "data": None, "message": result["message"]}


# ══════════════════════════════════════════════════════════
# POST /api/auth/login — 登录
# ══════════════════════════════════════════════════════════

@router.post("/auth/login")
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """邮箱登录，返回 access + refresh token。"""
    logger.info("收到登录请求: email=%s", req.email)
    user = AuthService.authenticate(db, req.email, req.password)
    if user is None:
        return {"code": -1, "data": None, "message": "邮箱或密码错误"}

    access_token = AuthService.create_access_token(user.id)
    refresh_token = AuthService.create_refresh_token(user.id)

    return {
        "code": 0,
        "data": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
        },
        "message": "登录成功",
    }


# ══════════════════════════════════════════════════════════
# POST /api/auth/refresh — 刷新 token
# ══════════════════════════════════════════════════════════

@router.post("/auth/refresh")
async def refresh(req: RefreshRequest):
    """使用 refresh token 获取新的 access token + refresh token。"""
    logger.info("收到 token 刷新请求")
    user_id = AuthService.verify_token(req.refresh_token, "refresh")
    if user_id is None:
        return {"code": -1, "data": None, "message": "refresh token 无效或已过期"}

    new_access_token = AuthService.create_access_token(user_id)
    new_refresh_token = AuthService.create_refresh_token(user_id)

    return {
        "code": 0,
        "data": {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        },
        "message": "success",
    }


# ══════════════════════════════════════════════════════════
# GET /api/auth/me — 获取当前用户信息
# ══════════════════════════════════════════════════════════

@router.get("/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息（需要 JWT）。"""
    return {
        "code": 0,
        "data": {
            "id": current_user.id,
            "email": current_user.email,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
        "message": "success",
    }
