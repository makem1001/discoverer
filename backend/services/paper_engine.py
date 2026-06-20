"""
发现者（Discoverer）— 模拟交易引擎 (P1-3, T04)

PaperEngine 通过日K前向仿真模拟真实交易环境，管理虚拟账户、
持仓、交易记录，并生成权益曲线。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd
from sqlalchemy.orm import Session

from models.db_models import PaperAccountDB, PaperPositionDB, PaperTradeDB

logger = logging.getLogger("discoverer.paper_engine")

# 交易费用
COMMISSION_RATE = 0.00025   # 万2.5 佣金
STAMP_TAX_RATE = 0.001      # 千1 印花税（仅卖出）
MIN_COMMISSION = 5.0        # 最低佣金 5 元
DEFAULT_POSITION_PCT = 0.3  # 默认单次买入使用 30% 可用资金
LOT_SIZE = 100              # A 股每手 100 股


class PaperEngine:
    """模拟交易引擎。

    以日K线前向仿真（forward simulation）为基础，在每个交易日收盘后
    计算信号并执行模拟买卖。

    Attributes:
        _data_service: 数据服务实例
        _signal_service: 信号服务实例
    """

    def __init__(self, data_service=None, signal_service=None):
        """初始化模拟交易引擎。

        Args:
            data_service: DataService 实例，用于获取行情数据
            signal_service: SignalService 实例，用于计算买卖信号
        """
        self._data_service = data_service
        self._signal_service = signal_service

    # ── 日K前向推进 ─────────────────────────────────────

    def advance(
        self,
        account_id: str,
        stock_code: str,
        db: Session,
    ) -> Dict[str, Any]:
        """日K前向推进一天。

        读取当日行情数据，计算买卖信号，执行模拟交易，更新账户状态。

        Args:
            account_id: 账户ID
            stock_code: 股票代码
            db: 数据库会话

        Returns:
            更新后的账户状态字典
        """
        # 1. 读取账户
        account = db.query(PaperAccountDB).filter(PaperAccountDB.id == account_id).first()
        if account is None:
            raise ValueError(f"账户不存在: {account_id}")

        current_date = account.current_date or ""
        initial_capital = account.initial_capital

        # 2. 获取全量日线数据，定位当前日期的下一日
        if self._data_service is None:
            logger.warning("DataService 未注入，无法推进模拟")
            account.status = "paused"
            db.commit()
            return self._account_summary(account)

        df = self._data_service.get_daily_data(
            stock_code,
            start_date="2010-01-01",
            end_date="2099-12-31",
        )

        if df.empty:
            logger.warning("股票 %s 无数据可用", stock_code)
            account.status = "completed"
            db.commit()
            return self._account_summary(account)

        # 确保日期列是字符串格式
        if "date" not in df.columns:
            # date 可能是 index
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
            else:
                logger.warning("数据不包含日期列")
                account.status = "completed"
                db.commit()
                return self._account_summary(account)

        df["date_str"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

        # 3. 确定当前日期和下一日
        if not current_date:
            # 初始状态：取数据第一条
            next_idx = 1  # 第一天不交易，从第二天开始
            current_date = df["date_str"].iloc[0]
            account.current_date = current_date
        else:
            # 找到当前日期在数据中的位置
            matching = df[df["date_str"] == current_date]
            if matching.empty:
                # 当前日期不在数据中，尝试找最近的
                all_dates = df["date_str"].tolist()
                logger.warning("当前日期 %s 不在数据中，自动定位", current_date)
                # 找最近一个 <= current_date 的位置
                try:
                    idx = max(i for i, d in enumerate(all_dates) if d <= current_date)
                    next_idx = idx + 1
                except ValueError:
                    next_idx = 0
            else:
                idx = df[df["date_str"] == current_date].index[0]
                next_idx = df.index.get_loc(idx) + 1

        # 检查是否数据耗尽
        if next_idx >= len(df):
            logger.info("账户 %s 数据耗尽，状态设为 completed", account_id)
            account.status = "completed"
            db.commit()
            return self._account_summary(account)

        # 获取下一日数据
        next_day = df.iloc[next_idx]
        next_date = str(next_day["date_str"])
        next_close = float(next_day["close"])
        next_open = float(next_day["open"])
        next_high = float(next_day["high"])
        next_low = float(next_day["low"])
        next_volume = float(next_day["volume"])

        logger.info(
            "账户 %s 推进: %s → %s, close=%.2f",
            account_id, current_date, next_date, next_close,
        )

        # 4. 计算信号（需要截至 next_date 的所有数据）
        df_up_to = df[df["date_str"] <= next_date].copy()
        buy_signal = False
        sell_signal = False

        if self._signal_service is not None:
            try:
                # 根据策略ID确定信号计算
                strategy_id = account.strategy_id or "macd_golden_death"
                # 经典策略通常由买入/卖出信号组成
                if strategy_id == "macd_golden_death":
                    macd = self._signal_service.compute_signal(df_up_to, "macd")
                    buy_signal = bool(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else False
                    # MACD 死叉 = 卖出信号（取反）
                    sell_signal = not buy_signal and not pd.isna(macd.iloc[-1])
                elif strategy_id == "ma_cross":
                    ma = self._signal_service.compute_signal(df_up_to, "ma_golden_cross")
                    buy_signal = bool(ma.iloc[-1]) if not pd.isna(ma.iloc[-1]) else False
                    sell_signal = not buy_signal and not pd.isna(ma.iloc[-1])
                elif strategy_id == "rsi_oversold":
                    rsi = self._signal_service.compute_signal(df_up_to, "rsi")
                    buy_signal = bool(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else False
                    sell_signal = False
                else:
                    # 通用：尝试作为信号ID直接计算
                    try:
                        sig = self._signal_service.compute_signal(df_up_to, strategy_id)
                        buy_signal = bool(sig.iloc[-1]) if not pd.isna(sig.iloc[-1]) else False
                        sell_signal = False
                    except Exception:
                        logger.debug("信号 %s 计算失败，跳过", strategy_id)
            except Exception as e:
                logger.warning("信号计算异常: %s", e)

        # 5. 执行交易（先卖后买，模拟T+1规则简化）
        current_cash = account.current_cash
        total_fee = 0.0
        trade_records: List[PaperTradeDB] = []

        # 5a. 卖出：遍历持仓，检查卖出信号
        positions = (
            db.query(PaperPositionDB)
            .filter(PaperPositionDB.account_id == account_id)
            .all()
        )

        for pos in positions:
            if sell_signal:
                shares = pos.shares
                sell_price = next_close
                sell_amount = sell_price * shares
                fee = max(COMMISSION_RATE * sell_amount, MIN_COMMISSION) + STAMP_TAX_RATE * sell_amount
                net_amount = sell_amount - fee
                pnl = net_amount - (pos.avg_cost * shares)
                pnl_pct = pnl / (pos.avg_cost * shares) if pos.avg_cost > 0 else 0.0

                # 记录交易
                trade = PaperTradeDB(
                    id=str(uuid4()),
                    account_id=account_id,
                    stock_code=stock_code,
                    trade_type="sell",
                    price=sell_price,
                    shares=shares,
                    fee=fee,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    reason="信号卖出",
                    traded_at=datetime.strptime(next_date, "%Y-%m-%d"),
                )
                db.add(trade)
                trade_records.append(trade)

                current_cash += net_amount
                total_fee += fee
                db.delete(pos)

                logger.info(
                    "卖出: %s, %d股 @ %.2f, 盈亏=%.2f, 手续费=%.2f",
                    stock_code, shares, sell_price, pnl, fee,
                )

        # 5b. 买入：检查买入信号
        if buy_signal and current_cash > MIN_COMMISSION:
            buy_amount = current_cash * DEFAULT_POSITION_PCT
            buy_price = next_close
            shares = int(buy_amount / buy_price / LOT_SIZE) * LOT_SIZE

            if shares >= LOT_SIZE:
                cost = buy_price * shares
                fee = max(COMMISSION_RATE * cost, MIN_COMMISSION)
                total_cost = cost + fee

                if total_cost <= current_cash:
                    # 创建/更新持仓
                    existing_pos = (
                        db.query(PaperPositionDB)
                        .filter(
                            PaperPositionDB.account_id == account_id,
                            PaperPositionDB.stock_code == stock_code,
                        )
                        .first()
                    )

                    if existing_pos:
                        # 加仓：更新平均成本和股数
                        total_shares = existing_pos.shares + shares
                        total_cost_basis = existing_pos.avg_cost * existing_pos.shares + cost
                        existing_pos.shares = total_shares
                        existing_pos.avg_cost = total_cost_basis / total_shares
                        existing_pos.current_price = buy_price
                        existing_pos.market_value = total_shares * buy_price
                        existing_pos.unrealized_pnl = existing_pos.market_value - total_cost_basis
                        existing_pos.unrealized_pnl_pct = existing_pos.unrealized_pnl / total_cost_basis if total_cost_basis > 0 else 0.0
                    else:
                        pos = PaperPositionDB(
                            id=str(uuid4()),
                            account_id=account_id,
                            stock_code=stock_code,
                            shares=shares,
                            avg_cost=buy_price,
                            current_price=buy_price,
                            market_value=shares * buy_price,
                            unrealized_pnl=0.0,
                            unrealized_pnl_pct=0.0,
                            open_date=next_date,
                        )
                        db.add(pos)

                    # 记录交易
                    trade = PaperTradeDB(
                        id=str(uuid4()),
                        account_id=account_id,
                        stock_code=stock_code,
                        trade_type="buy",
                        price=buy_price,
                        shares=shares,
                        fee=fee,
                        pnl=None,
                        pnl_pct=None,
                        reason="信号买入",
                        traded_at=datetime.strptime(next_date, "%Y-%m-%d"),
                    )
                    db.add(trade)
                    trade_records.append(trade)

                    current_cash -= total_cost
                    total_fee += fee

                    logger.info(
                        "买入: %s, %d股 @ %.2f, 手续费=%.2f",
                        stock_code, shares, buy_price, fee,
                    )

        # 6. 更新持仓市值（未平仓持仓按当日收盘价估值）
        position_value = 0.0
        updated_positions = (
            db.query(PaperPositionDB)
            .filter(PaperPositionDB.account_id == account_id)
            .all()
        )
        for pos in updated_positions:
            pos.current_price = next_close
            pos.market_value = pos.shares * next_close
            pos.unrealized_pnl = pos.market_value - (pos.avg_cost * pos.shares)
            pos.unrealized_pnl_pct = pos.unrealized_pnl / (pos.avg_cost * pos.shares) if pos.avg_cost > 0 else 0.0
            position_value += pos.market_value

        # 7. 更新账户
        account.current_cash = current_cash
        account.total_value = current_cash + position_value
        account.current_date = next_date

        # 追加权益历史
        equity_record = {
            "date": next_date,
            "total_value": round(account.total_value, 2),
            "cash": round(current_cash, 2),
            "position_value": round(position_value, 2),
            "cumulative_pnl": round(account.total_value - initial_capital, 2),
            "cumulative_pnl_pct": round((account.total_value - initial_capital) / initial_capital, 4) if initial_capital > 0 else 0.0,
        }

        try:
            history = json.loads(account.equity_history) if account.equity_history else []
        except (json.JSONDecodeError, TypeError):
            history = []
        history.append(equity_record)
        account.equity_history = json.dumps(history, ensure_ascii=False)

        db.commit()

        logger.info(
            "账户 %s 推进完成: date=%s, cash=%.2f, position_value=%.2f, total=%.2f, trades=%d",
            account_id, next_date, current_cash, position_value, account.total_value, len(trade_records),
        )

        return self._account_summary(account)

    # ── 辅助 ────────────────────────────────────────────

    def _account_summary(self, account: PaperAccountDB) -> Dict[str, Any]:
        """生成账户摘要字典。"""
        return {
            "id": account.id,
            "name": account.name,
            "status": account.status,
            "current_date": account.current_date,
            "initial_capital": account.initial_capital,
            "current_cash": account.current_cash,
            "total_value": account.total_value,
            "stock_code": account.stock_code,
            "strategy_id": account.strategy_id,
        }
