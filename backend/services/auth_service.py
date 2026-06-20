"""
认证服务 — JWT + bcrypt 密码管理
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import bcrypt
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from models.db_models import User, UserSettings

logger = logging.getLogger("discoverer.auth")

# bcrypt 盐轮数（12 = ~250ms，生产环境推荐值）
BCRYPT_ROUNDS = 12


class AuthService:
    """认证服务 — 提供密码哈希、JWT 令牌创建/验证、注册/登录业务逻辑。"""

    @staticmethod
    def hash_password(password: str) -> str:
        """使用 bcrypt 哈希密码，直接调用 bcrypt 库（避开 passlib 兼容性问题）。

        bcrypt 最大输入 72 字节，超过自动截断。

        Args:
            password: 明文密码

        Returns:
            bcrypt 哈希字符串
        """
        password_bytes = password.encode("utf-8")[:72]
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        return bcrypt.hashpw(password_bytes, salt).decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证明文密码与哈希是否匹配。

        bcrypt 最大输入 72 字节，超过自动截断（与 hash_password 一致）。

        Args:
            plain_password: 明文密码
            hashed_password: bcrypt 哈希

        Returns:
            True 如果匹配
        """
        password_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))

    @staticmethod
    def create_access_token(user_id: int) -> str:
        """创建 access token（2 小时过期）。

        Payload: {sub: user_id, exp: unix_timestamp, type: 'access'}

        Args:
            user_id: 用户 ID

        Returns:
            JWT 字符串
        """
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),  # python-jose 要求 sub 必须为字符串
            "exp": expire,
            "type": "access",
        }
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token

    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        """创建 refresh token（7 天过期）。

        Payload: {sub: user_id, exp: unix_timestamp, type: 'refresh'}

        Args:
            user_id: 用户 ID

        Returns:
            JWT 字符串
        """
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(user_id),  # python-jose 要求 sub 必须为字符串
            "exp": expire,
            "type": "refresh",
        }
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token

    @staticmethod
    def verify_token(token: str, expected_type: str = "access") -> Optional[int]:
        """验证 JWT token 并返回 user_id。

        Args:
            token: JWT 字符串
            expected_type: 期望的 token 类型 ("access" 或 "refresh")

        Returns:
            user_id (int) 如果验证成功，否则 None
        """
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            user_id_str = payload.get("sub")
            token_type: str = payload.get("type", "")
            if user_id_str is None or token_type != expected_type:
                logger.warning("Token payload 无效: sub=%s, type=%s", user_id_str, token_type)
                return None
            return int(user_id_str)
        except JWTError as e:
            logger.warning("JWT 验证失败: %s", e)
            return None

    @staticmethod
    def register(db: Session, email: str, password: str, agreed_risk_at: Optional[datetime] = None) -> dict:
        """注册新用户。

        检查邮箱唯一性和密码长度，创建 User + UserSettings 记录。

        Args:
            db: 数据库会话
            email: 注册邮箱
            password: 明文密码
            agreed_risk_at: 风险告知书同意时间（合规要求）

        Returns:
            {"success": True/False, "message": str, "user_id": int|null}
        """
        # 密码长度校验
        if len(password) < 6:
            return {"success": False, "message": "密码至少需要 6 位", "user_id": None}

        # 邮箱唯一性检查
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user is not None:
            logger.warning("注册失败：邮箱 %s 已存在", email)
            return {"success": False, "message": "邮箱已注册", "user_id": None}

        try:
            # 创建用户
            hashed = AuthService.hash_password(password)
            new_user = User(
                email=email,
                password_hash=hashed,
                agreed_risk_at=agreed_risk_at,
            )
            db.add(new_user)
            db.flush()  # 获取 user_id

            # 创建默认用户设置
            new_settings = UserSettings(user_id=new_user.id, tdx_data_dir="")
            db.add(new_settings)
            db.commit()
            db.refresh(new_user)

            logger.info("用户注册成功: id=%d, email=%s", new_user.id, email)
            return {"success": True, "message": "注册成功", "user_id": new_user.id}
        except Exception as e:
            db.rollback()
            logger.error("注册异常: %s", e)
            return {"success": False, "message": f"注册失败: {str(e)}", "user_id": None}

    @staticmethod
    def authenticate(db: Session, email: str, password: str) -> Optional[User]:
        """验证登录凭据。

        Args:
            db: 数据库会话
            email: 登录邮箱
            password: 明文密码

        Returns:
            User 对象如果验证通过，否则 None
        """
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            logger.warning("登录失败：邮箱 %s 不存在", email)
            return None
        if not AuthService.verify_password(password, user.password_hash):
            logger.warning("登录失败：邮箱 %s 密码错误", email)
            return None
        logger.info("用户登录成功: id=%d, email=%s", user.id, email)
        return user
