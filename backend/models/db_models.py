"""
发现者（Discoverer）— SQLAlchemy ORM 模型

定义 4 张表：
  - User（用户）
  - UserSettings（用户设置，含通达信路径）
  - StrategyRecord（策略持久化）
  - BacktestRecord（回测历史）
"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间（含时区信息）。"""
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────
#  User — 用户表
# ─────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    agreed_risk_at = Column(DateTime(timezone=True), nullable=True)

    # 关系
    settings = relationship(
        "UserSettings", back_populates="user", uselist=False, lazy="selectin"
    )
    strategies = relationship(
        "StrategyRecord", back_populates="user", lazy="selectin"
    )
    backtests = relationship(
        "BacktestRecord", back_populates="user", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email!r})>"


# ─────────────────────────────────────────────────────
#  UserSettings — 用户设置表（含通达信路径）
# ─────────────────────────────────────────────────────
class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False,
    )
    tdx_data_dir = Column(String(512), default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # 关系
    user = relationship("User", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id}, tdx={self.tdx_data_dir!r})>"


# ─────────────────────────────────────────────────────
#  StrategyRecord — 策略持久化表
# ─────────────────────────────────────────────────────
class StrategyRecord(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    raw_text = Column(Text, default="")
    # JSON 字符串存储
    entry_conditions = Column(Text, default="[]")
    exit_conditions = Column(Text, default="[]")
    holding_rule = Column(Text, default="{}")
    params = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # 关系
    user = relationship("User", back_populates="strategies")
    backtests = relationship(
        "BacktestRecord", back_populates="strategy", lazy="selectin"
    )

    # 额外索引
    __table_args__ = (
        Index("idx_strategies_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<StrategyRecord(id={self.id}, name={self.name!r}, user_id={self.user_id})>"


# ─────────────────────────────────────────────────────
#  BacktestRecord — 回测历史表
# ─────────────────────────────────────────────────────
class BacktestRecord(Base):
    __tablename__ = "backtest_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    strategy_id = Column(
        Integer, ForeignKey("strategies.id"), nullable=True, index=True
    )
    stock_code = Column(String(20), nullable=False, index=True)
    stock_name = Column(String(50), default="")
    start_date = Column(String(10), nullable=False)  # "YYYY-MM-DD"
    end_date = Column(String(10), nullable=False)  # "YYYY-MM-DD"
    total_return = Column(Float, default=0.0)
    annual_return = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    profit_loss_ratio = Column(Float, default=0.0)
    total_trades = Column(Integer, default=0)
    result_data = Column(Text, default="{}")  # JSON: trades + equity_curve
    data_source = Column(String(20), default="mock")  # tdx / akshare / mock / parquet_cache
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    # 关系
    user = relationship("User", back_populates="backtests")
    strategy = relationship("StrategyRecord", back_populates="backtests")

    # 额外索引
    __table_args__ = (
        Index("idx_backtest_user_id", "user_id"),
        Index("idx_backtest_strategy_id", "strategy_id"),
        Index("idx_backtest_stock_code", "stock_code"),
    )

    def __repr__(self) -> str:
        return (
            f"<BacktestRecord(id={self.id}, stock={self.stock_code!r}, "
            f"total_return={self.total_return:.2%}, data_source={self.data_source!r})>"
        )


# ─────────────────────────────────────────────────────
#  PaperAccountDB — 模拟交易账户表 (P1-3)
# ─────────────────────────────────────────────────────
class PaperAccountDB(Base):
    __tablename__ = "paper_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    strategy_id = Column(String(100), nullable=False)
    stock_code = Column(String(20), nullable=False)
    initial_capital = Column(Float, nullable=False, default=100000.0)
    current_cash = Column(Float, nullable=False, default=100000.0)
    total_value = Column(Float, nullable=False, default=100000.0)
    current_date = Column(String(10), nullable=True, default="")  # 当前模拟日期 "YYYY-MM-DD"
    equity_history = Column(Text, nullable=True, default="[]")  # JSON: [{date, total_value, cash, position_value}]
    status = Column(String(20), nullable=False, default="running")  # running/paused/completed
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    # relationships
    positions = relationship("PaperPositionDB", back_populates="account", cascade="all, delete-orphan")
    trades = relationship("PaperTradeDB", back_populates="account", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index("idx_paper_accounts_user", "user_id"),
        Index("idx_paper_accounts_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaperAccountDB(id={self.id}, name={self.name!r}, "
            f"status={self.status!r}, total_value={self.total_value})>"
        )


# ─────────────────────────────────────────────────────
#  PaperPositionDB — 模拟持仓表 (P1-3)
# ─────────────────────────────────────────────────────
class PaperPositionDB(Base):
    __tablename__ = "paper_positions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False)
    stock_code = Column(String(20), nullable=False)
    shares = Column(Integer, nullable=False)
    avg_cost = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    market_value = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_pct = Column(Float, nullable=False, default=0.0)
    open_date = Column(String(20), nullable=False)  # ISO date

    account = relationship("PaperAccountDB", back_populates="positions")

    # 索引
    __table_args__ = (
        Index("idx_paper_positions_account", "account_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaperPositionDB(id={self.id}, stock={self.stock_code!r}, "
            f"shares={self.shares}, market_value={self.market_value})>"
        )


# ─────────────────────────────────────────────────────
#  PaperTradeDB — 模拟交易记录表 (P1-3)
# ─────────────────────────────────────────────────────
class PaperTradeDB(Base):
    __tablename__ = "paper_trades"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(String(36), ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False)
    stock_code = Column(String(20), nullable=False)
    trade_type = Column(String(10), nullable=False)  # buy/sell
    price = Column(Float, nullable=False)
    shares = Column(Integer, nullable=False)
    fee = Column(Float, nullable=False, default=0.0)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    reason = Column(String(500), nullable=False, default="")
    traded_at = Column(DateTime, nullable=False, default=func.now())

    account = relationship("PaperAccountDB", back_populates="trades")

    # 索引
    __table_args__ = (
        Index("idx_paper_trades_account", "account_id"),
        Index("idx_paper_trades_date", "traded_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<PaperTradeDB(id={self.id}, stock={self.stock_code!r}, "
            f"type={self.trade_type!r}, shares={self.shares}, price={self.price})>"
        )
