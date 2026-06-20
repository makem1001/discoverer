"""
发现者（Discoverer）— 数据库初始化模块

SQLAlchemy engine + Session + Base + get_db 依赖注入生成器。
使用 SQLite 作为默认数据库，路径从 config.DATABASE_URL 读取。
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import DATABASE_URL, DATA_DIR

logger = logging.getLogger("discoverer.database")

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── 引擎 ──────────────────────────────────────────────
# connect_args 仅对 SQLite 有效，避免多线程共享连接问题
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

# ── 会话工厂 ──────────────────────────────────────────
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── 声明式基类 ────────────────────────────────────────
class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


# ── FastAPI 依赖注入 ─────────────────────────────────
def get_db():
    """
    为每个请求生成一个数据库会话，请求结束后自动关闭。

    Yields:
        Session: SQLAlchemy 会话对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """根据所有已导入的 ORM 模型自动建表。"""
    # 延迟导入，确保所有模型类已注册到 Base.metadata
    import models.db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建/检查完成。")


# ── 模块加载时自动建表 ─────────────────────────────────
create_tables()
