"""
发现者（Discoverer）— 回测引擎核心

实现向量化回测循环，模拟真实交易条件（佣金、印花税、滑点、涨跌停），
支持 numba JIT 加速，集成 P0-2 风控模块（ATR止损/比例止盈/凯利仓位/回撤熔断）。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, date
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from models.schemas import (
    Trade, EquityPoint, BacktestMetrics, BacktestResult, YearlyStat,
    Strategy, SignalCondition, StrategyScore, RiskControlParams,
)
from models.signals import Signal, get_signal_by_id
from services.signal_service import SignalService
from config import (
    COMMISSION_RATE, STAMP_TAX_RATE, SLIPPAGE_RATE, LIMIT_UP_DOWN_RATE,
    DEFAULT_INITIAL_CAPITAL,
)

logger = logging.getLogger("discoverer.engine")

# 尝试导入 numba
try:
    from numba import njit, prange
    HAS_NUMBA = True
    logger.info("numba JIT 加速已启用")
except ImportError:
    HAS_NUMBA = False
    logger.warning("numba 未安装，使用纯 Python 回测循环")

    def njit(*args, **kwargs):
        """numba 不可用时的空装饰器"""
        def decorator(func):
            return func
        return decorator

    def prange(x):
        return range(x)


class BacktestEngine:
    """回测引擎：执行策略回测并生成结果"""

    def __init__(self, data_service=None, signal_service: Optional[SignalService] = None):
        self.data_service = data_service
        self.signal_service = signal_service or SignalService()

    # ── 核心回测方法 ───────────────────────────────────

    def run_backtest(
        self,
        df: pd.DataFrame,
        strategy: Strategy,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
        risk_control: Optional[RiskControlParams] = None,
    ) -> BacktestResult:
        """
        执行单只股票的单策略回测。

        Args:
            df: 日线数据 DataFrame
            strategy: 策略定义
            initial_capital: 初始资金
            risk_control: 风控参数（可选）

        Returns:
            BacktestResult 包含完整回测结果
        """
        if df.empty:
            return self._empty_result(strategy)

        df = df.sort_values("date").reset_index(drop=True).copy()
        n = len(df)

        # 1. 计算所有需要的信号
        entry_signals = self._compute_condition_signals(df, strategy.entry_conditions)
        exit_signals = self._compute_condition_signals(df, strategy.exit_conditions)

        # 2. 构建买入/卖出触发数组
        buy_trigger = self._combine_signals(entry_signals, strategy)
        sell_trigger = self._combine_signals(exit_signals, strategy)

        # 3. 执行回测循环
        trades, equity_curve = self._simulate_trades(
            df, buy_trigger, sell_trigger, strategy, initial_capital,
            risk_control=risk_control,
        )

        # 4. 计算指标
        metrics = self._calculate_metrics(trades, equity_curve, initial_capital, df)

        # 5. 逐年统计
        yearly_stats = self._calculate_yearly_stats(trades, df)

        # 6. 构建结果
        stock_name = ""
        stock_code = strategy.params.get("stock_code", "")
        # 尝试从 DataService 获取名称
        if self.data_service:
            stock_info = self.data_service._stock_code_index.get(stock_code)
            if stock_info:
                stock_name = stock_info.get("name", "")

        result = BacktestResult(
            id=str(uuid.uuid4())[:8],
            stock_code=stock_code,
            stock_name=stock_name,
            strategy=strategy,
            trades=[Trade(**t) for t in trades],
            equity_curve=[EquityPoint(**ep) for ep in equity_curve],
            metrics=metrics,
            yearly_stats=[YearlyStat(**ys) for ys in yearly_stats],
        )
        return result

    def _compute_condition_signals(
        self, df: pd.DataFrame, conditions: List[SignalCondition]
    ) -> List[pd.Series]:
        """计算每个条件的信号"""
        signals = []
        for cond in conditions:
            sig = self.signal_service.compute_signal(df, cond.signal_id)
            # 根据操作符过滤
            if cond.operator == "trigger":
                signals.append(sig)
            elif cond.operator == "cross_above":
                signals.append(sig)  # cross_above 已在计算中包含
            elif cond.operator == "cross_below":
                signals.append(sig)
            elif cond.operator == "gt":
                signals.append(sig)
            elif cond.operator == "lt":
                signals.append(sig)
            else:
                signals.append(sig)
        return signals

    def _combine_signals(
        self, signal_list: List[pd.Series], strategy: Strategy
    ) -> np.ndarray:
        """将多个信号条件组合（AND 逻辑）"""
        if not signal_list:
            return np.zeros(len(signal_list[0]) if signal_list else 1, dtype=bool)

        combined = signal_list[0].copy()
        for s in signal_list[1:]:
            combined = combined & s
        return combined.fillna(False).values

    def _simulate_trades(
        self,
        df: pd.DataFrame,
        buy_trigger: np.ndarray,
        sell_trigger: np.ndarray,
        strategy: Strategy,
        initial_capital: float,
        risk_control: Optional[RiskControlParams] = None,
    ) -> Tuple[List[dict], List[dict]]:
        """
        模拟买卖交易。

        使用 numba 加速的回测循环（如果可用）。
        支持 P0-2 风控模块：ATR止损、比例止盈、凯利仓位、回撤熔断。
        """
        n = len(df)
        close_prices = df["close"].values.astype(np.float64)
        dates = df["date"].values
        holding_rule = strategy.holding_rule

        # 持有规则参数
        hold_days = 99999
        stop_loss_pct = -999.0
        stop_profit_pct = 999.0
        trailing_pct = 999.0

        if holding_rule:
            hold_days = holding_rule.params.get("days", 99999)
            stop_loss_pct = holding_rule.params.get("loss_pct", -999.0)
            stop_profit_pct = holding_rule.params.get("profit_pct", 999.0)
            trailing_pct = holding_rule.params.get("trailing_pct", 999.0)

        # ── 风控参数 ────────────────────────────────────
        atr_stop_multiplier = 0.0
        take_profit_pct = 0.0
        position_sizing = POSITION_FULL
        fixed_position_pct = 0.3
        max_position_pct = 1.0
        max_drawdown_limit = 0.0

        if risk_control is not None:
            atr_stop_multiplier = float(risk_control.atr_stop_multiplier)
            take_profit_pct = float(risk_control.take_profit_pct)
            fixed_position_pct = float(risk_control.fixed_position_pct)
            max_position_pct = float(risk_control.max_position_pct)
            max_drawdown_limit = float(risk_control.max_drawdown_limit)

            # 映射仓位模式字符串 → int 编码
            sizing_map = {
                "full": POSITION_FULL,
                "kelly": POSITION_KELLY,
                "half_kelly": POSITION_HALF_KELLY,
                "fixed_pct": POSITION_FIXED_PCT,
            }
            position_sizing = sizing_map.get(
                risk_control.position_sizing, POSITION_FULL
            )

        # 获取 high/low 数组（ATR 计算需要）
        if "high" in df.columns and "low" in df.columns:
            high_prices = df["high"].values.astype(np.float64)
            low_prices = df["low"].values.astype(np.float64)
        else:
            high_prices = close_prices.copy()
            low_prices = close_prices.copy()

        # 使用 numba 加速的核心循环
        if HAS_NUMBA:
            trades_raw, equity_raw, dd_breached, dd_breach_idx = _simulate_trades_numba(
                close_prices, high_prices, low_prices,
                buy_trigger, sell_trigger,
                hold_days, stop_loss_pct, stop_profit_pct, trailing_pct,
                initial_capital, COMMISSION_RATE, STAMP_TAX_RATE, SLIPPAGE_RATE,
                LIMIT_UP_DOWN_RATE,
                atr_stop_multiplier, take_profit_pct, position_sizing,
                fixed_position_pct, max_position_pct, max_drawdown_limit,
            )
        else:
            trades_raw, equity_raw, dd_breached, dd_breach_idx = _simulate_trades_python(
                close_prices, high_prices, low_prices,
                buy_trigger, sell_trigger,
                hold_days, stop_loss_pct, stop_profit_pct, trailing_pct,
                initial_capital, COMMISSION_RATE, STAMP_TAX_RATE, SLIPPAGE_RATE,
                LIMIT_UP_DOWN_RATE,
                atr_stop_multiplier, take_profit_pct, position_sizing,
                fixed_position_pct, max_position_pct, max_drawdown_limit,
            )

        # 格式化交易记录
        trades = []
        for t in trades_raw:
            if len(t) >= 6:
                entry_idx, exit_idx, entry_price, exit_price, ret_pct, reason_val = t
                reason_str = _REASON_MAP.get(int(reason_val), "unknown")
                trades.append({
                    "entry_date": str(dates[int(entry_idx)])[:10] if int(entry_idx) < n else "",
                    "entry_price": float(entry_price),
                    "exit_date": str(dates[int(exit_idx)])[:10] if int(exit_idx) < n else "",
                    "exit_price": float(exit_price),
                    "return_pct": float(ret_pct),
                    "exit_reason": reason_str,
                })

        # 格式化资金曲线
        equity_curve = []
        peak = initial_capital
        dd_breach_date = ""
        for i, eq in enumerate(equity_raw):
            peak = max(peak, eq)
            dd = (peak - eq) / peak if peak > 0 else 0.0
            date_str = str(dates[i])[:10] if i < n else ""
            equity_curve.append({
                "date": date_str,
                "equity": float(eq),
                "drawdown": float(dd),
            })
            # 记录回撤熔断日期
            if dd_breached and int(dd_breach_idx) == i:
                dd_breach_date = date_str

        # 注入 dd_breached 标记到 trade/summary
        # 将 dd_breached 和 dd_breach_date 保存在最后一个 equity point 的元数据中（通过额外字段）
        # 我们通过返回额外的标记来回传
        self._last_dd_breached = bool(dd_breached)
        self._last_dd_breach_date = dd_breach_date

        return trades, equity_curve

    # ── 指标计算 ────────────────────────────────────────

    def _calculate_metrics(
        self,
        trades: List[dict],
        equity_curve: List[dict],
        initial_capital: float,
        df: pd.DataFrame,
    ) -> BacktestMetrics:
        """计算回测核心指标"""
        total_trades = len(trades)
        dd_breached = getattr(self, '_last_dd_breached', False)

        if total_trades == 0:
            # 买入持有基准
            if len(df) > 0:
                bh_return = (float(df["close"].iloc[-1]) / float(df["close"].iloc[0])) - 1
                n_years = max((df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25, 0.1)
                return BacktestMetrics(
                    total_return=round(bh_return, 4),
                    annual_return=round((1 + bh_return) ** (1 / n_years) - 1, 4),
                    max_drawdown=0.0,
                    win_rate=0.0,
                    sharpe_ratio=0.0,
                    profit_loss_ratio=0.0,
                    total_trades=0,
                    win_trades=0,
                    lose_trades=0,
                    avg_hold_days=0.0,
                    dd_breached=dd_breached,
                )
            return BacktestMetrics(dd_breached=dd_breached)

        # 计算各项指标
        returns = [t.get("return_pct", 0) for t in trades]
        win_trades = sum(1 for r in returns if r > 0)
        lose_trades = sum(1 for r in returns if r < 0)
        win_rate = win_trades / total_trades if total_trades > 0 else 0.0

        total_return = equity_curve[-1]["equity"] / initial_capital - 1 if equity_curve else 0.0

        # 年化收益
        start_date = pd.to_datetime(equity_curve[0]["date"]) if equity_curve else None
        end_date = pd.to_datetime(equity_curve[-1]["date"]) if equity_curve else None
        n_years = max((end_date - start_date).days / 365.25 if start_date and end_date else 0.1, 0.1)
        annual_return = (1 + total_return) ** (1 / n_years) - 1 if total_return > -1 else -1.0

        # 最大回撤
        max_dd = max((ep["drawdown"] for ep in equity_curve), default=0.0)

        # 盈亏比
        avg_win = np.mean([r for r in returns if r > 0]) if win_trades > 0 else 0
        avg_loss = abs(np.mean([r for r in returns if r < 0])) if lose_trades > 0 else 1
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

        # 夏普比率
        if len(equity_curve) > 1:
            daily_returns = []
            for i in range(1, len(equity_curve)):
                prev_eq = equity_curve[i - 1]["equity"]
                curr_eq = equity_curve[i]["equity"]
                if prev_eq > 0:
                    daily_returns.append(curr_eq / prev_eq - 1)
            if daily_returns:
                mean_ret = np.mean(daily_returns)
                std_ret = np.std(daily_returns) + 1e-10
                sharpe = (mean_ret / std_ret) * np.sqrt(252)
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        # 平均持有天数
        hold_days_list = []
        for t in trades:
            try:
                entry_d = pd.to_datetime(t["entry_date"])
                exit_d = pd.to_datetime(t["exit_date"])
                hold_days_list.append((exit_d - entry_d).days)
            except Exception:
                pass
        avg_hold_days = np.mean(hold_days_list) if hold_days_list else 0.0

        return BacktestMetrics(
            total_return=round(total_return, 4),
            annual_return=round(annual_return, 4),
            max_drawdown=round(max_dd, 4),
            win_rate=round(win_rate, 4),
            sharpe_ratio=round(sharpe, 4),
            profit_loss_ratio=round(profit_loss_ratio, 4),
            total_trades=total_trades,
            win_trades=win_trades,
            lose_trades=lose_trades,
            avg_hold_days=round(avg_hold_days, 1),
            dd_breached=dd_breached,
        )

    def _calculate_yearly_stats(
        self, trades: List[dict], df: pd.DataFrame
    ) -> List[dict]:
        """计算逐年交易统计"""
        if not trades:
            return []

        yearly = {}
        for t in trades:
            try:
                year = pd.to_datetime(t["entry_date"]).year
            except Exception:
                continue
            if year not in yearly:
                yearly[year] = {"trades": 0, "wins": 0, "return_sum": 0.0}
            yearly[year]["trades"] += 1
            ret = t.get("return_pct", 0)
            if ret > 0:
                yearly[year]["wins"] += 1
            yearly[year]["return_sum"] += ret

        result = []
        for year in sorted(yearly.keys()):
            y = yearly[year]
            result.append({
                "year": int(year),
                "return_pct": round(y["return_sum"], 4),
                "trades": y["trades"],
                "win_rate": round(y["wins"] / y["trades"], 4) if y["trades"] > 0 else 0.0,
            })

        return result

    def _empty_result(self, strategy: Strategy) -> BacktestResult:
        """返回空回测结果"""
        return BacktestResult(
            id=str(uuid.uuid4())[:8],
            strategy=strategy,
        )

    # ── 策略发现 ────────────────────────────────────────

    def discover(
        self,
        objective: str,
        signal_matrix: dict,
        price_matrix: pd.DataFrame,
        top_n: int = 20,
    ) -> List[StrategyScore]:
        """
        策略发现：遍历所有信号，按目标排序返回 Top-N。

        Args:
            objective: 优化目标
            signal_matrix: {signal_id: ndarray (n_days × n_stocks)}
            price_matrix: DataFrame (n_days × n_stocks) 收盘价
            top_n: 返回前N名

        Returns:
            排名列表
        """
        from concurrent.futures import ProcessPoolExecutor, as_completed
        from config import MAX_PARALLEL_WORKERS

        signal_ids = list(signal_matrix.keys())
        n_signals = len(signal_ids)
        results = []

        # 多进程并行评分
        with ProcessPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as executor:
            futures = {}
            for sid in signal_ids:
                matrix = signal_matrix[sid]
                future = executor.submit(
                    _score_single_signal, sid, matrix, price_matrix.values, objective
                )
                futures[future] = sid

            for future in as_completed(futures):
                sid = futures[future]
                try:
                    score_result = future.result()
                    if score_result:
                        results.append(score_result)
                except Exception as e:
                    logger.error(f"信号 {sid} 评分失败: {e}")

        # 排序
        reverse = objective != "min_drawdown"
        results.sort(key=lambda x: x["score"], reverse=reverse)

        # 格式化
        output = []
        for r in results[:top_n]:
            sig = get_signal_by_id(r["signal_id"])
            output.append(StrategyScore(
                signal=sig,
                score=round(r["score"], 4),
                win_rate=round(r["win_rate"], 4),
                annual_return=round(r["annual_return"], 4),
                max_drawdown=round(r["max_drawdown"], 4),
                total_trades=int(r["total_trades"]),
            ))

        return output

    # ── 策略体检 ────────────────────────────────────────

    def checkup(
        self,
        signal_ids: List[str],
        signal_matrix: dict,
        price_matrix: pd.DataFrame,
    ) -> dict:
        """
        策略体检：验证信号组合在全市场的表现。

        Args:
            signal_ids: 待验证的信号ID列表
            signal_matrix: {signal_id: ndarray}
            price_matrix: DataFrame

        Returns:
            体检结果字典
        """
        # 组合信号：AND 逻辑
        combined = None
        for sid in signal_ids:
            if sid in signal_matrix:
                mat = signal_matrix[sid]
                if combined is None:
                    combined = mat.copy()
                else:
                    # 对齐维度
                    min_days = min(combined.shape[0], mat.shape[0])
                    min_stocks = min(combined.shape[1], mat.shape[1])
                    combined = combined[:min_days, :min_stocks] & mat[:min_days, :min_stocks]

        if combined is None:
            return {
                "total_tests": 0, "triggered": 0, "trigger_rate": 0.0,
                "win_rate": 0.0, "avg_return": 0.0, "best_return": 0.0,
                "worst_return": 0.0, "yearly_distribution": [],
            }

        prices = price_matrix.values
        min_days = min(combined.shape[0], prices.shape[0] - 1)
        min_stocks = min(combined.shape[1], prices.shape[1])

        combined = combined[:min_days, :min_stocks]
        prices = prices[:min_days + 1, :min_stocks]

        # 统计触发位置
        trigger_mask = combined
        total_tests = combined.size
        triggered = int(trigger_mask.sum())

        if triggered == 0:
            return {
                "total_tests": total_tests, "triggered": 0, "trigger_rate": 0.0,
                "win_rate": 0.0, "avg_return": 0.0, "best_return": 0.0,
                "worst_return": 0.0, "yearly_distribution": [],
            }

        trigger_rate = triggered / total_tests if total_tests > 0 else 0.0

        # 计算触发后1/5/10/20日收益
        all_returns = []
        for forward in [1, 5, 10, 20]:
            if combined.shape[0] > forward:
                future_prices = prices[forward:, :]
                trigger_future = combined[:combined.shape[0] - forward, :]
                for i in range(trigger_future.shape[0]):
                    for j in range(trigger_future.shape[1]):
                        if trigger_future[i, j]:
                            entry_price = prices[i, j]
                            exit_price = future_prices[i, j]
                            if entry_price > 0:
                                ret = (exit_price / entry_price) - 1
                                all_returns.append(ret)

        if not all_returns:
            return {
                "total_tests": total_tests, "triggered": triggered,
                "trigger_rate": round(trigger_rate, 4),
                "win_rate": 0.0, "avg_return": 0.0, "best_return": 0.0,
                "worst_return": 0.0, "yearly_distribution": [],
            }

        all_returns = np.array(all_returns)
        win_rate = float((all_returns > 0).mean())
        avg_return = float(all_returns.mean())
        best_return = float(all_returns.max())
        worst_return = float(all_returns.min())

        return {
            "total_tests": total_tests,
            "triggered": triggered,
            "trigger_rate": round(trigger_rate, 4),
            "win_rate": round(win_rate, 4),
            "avg_return": round(avg_return, 4),
            "best_return": round(best_return, 4),
            "worst_return": round(worst_return, 4),
            "yearly_distribution": [],
        }


# ══════════════════════════════════════════════════════════════════
# Numba / Python 加速的底层回测函数
# ══════════════════════════════════════════════════════════════════


# Reason code constants (cannot use hash() in numba)
_REASON_SIGNAL = 1
_REASON_HOLD_EXPIRED = 2
_REASON_STOP_LOSS = 3
_REASON_STOP_PROFIT = 4
_REASON_TRAILING_STOP = 5
_REASON_END_OF_PERIOD = 6
_REASON_ATR_STOP = 7
_REASON_DD_BREACHED = 8

_REASON_MAP = {
    _REASON_SIGNAL: "signal",
    _REASON_HOLD_EXPIRED: "hold_expired",
    _REASON_STOP_LOSS: "stop_loss",
    _REASON_STOP_PROFIT: "stop_profit",
    _REASON_TRAILING_STOP: "trailing_stop",
    _REASON_END_OF_PERIOD: "end_of_period",
    _REASON_ATR_STOP: "atr_stop",
    _REASON_DD_BREACHED: "dd_breached",
}

# 仓位模式编码常量
POSITION_FULL = 0
POSITION_KELLY = 1
POSITION_HALF_KELLY = 2
POSITION_FIXED_PCT = 3


@njit(cache=True)
def _simulate_trades_numba(
    close_prices: np.ndarray,
    high_prices: np.ndarray,
    low_prices: np.ndarray,
    buy_trigger: np.ndarray,
    sell_trigger: np.ndarray,
    hold_days: int,
    stop_loss_pct: float,
    stop_profit_pct: float,
    trailing_pct: float,
    initial_capital: float,
    commission_rate: float,
    stamp_tax_rate: float,
    slippage_rate: float,
    limit_up_down_rate: float,
    atr_stop_multiplier: float,
    take_profit_pct: float,
    position_sizing: int,
    fixed_position_pct: float,
    max_position_pct: float,
    max_drawdown_limit: float,
):
    """
    numba JIT 编译的回测循环（P0-2 风控增强版）。

    状态机：
      0 = 空仓
      1 = 持仓

    风控特性：
      - ATR 14 日滑动窗口动态止损
      - 独立比例止盈（与 stop_profit_pct 并存）
      - 凯利公式 / 半凯利 / 固定比例仓位管理
      - 回撤熔断（peak_equity 跟踪）

    Returns:
        trades: list of (entry_idx, exit_idx, entry_price, exit_price, return_pct, reason_code)
        equity_curve: array of daily equity
        dd_breached: bool (回撤熔断是否触发)
        dd_breach_idx: int (熔断触发索引, -1 表示未触发)
    """
    n = len(close_prices)
    equity = np.full(n, initial_capital, dtype=np.float64)

    max_trades = n // 2
    trades_arr = np.zeros((max_trades, 6), dtype=np.float64)
    trade_count = 0

    position = 0
    entry_idx = -1
    entry_price = 0.0
    shares = 0.0
    cash = initial_capital
    highest_since_entry = 0.0

    # ── ATR 滑动窗口 ───────────────────────────────────
    atr_period = 14
    atr_buffer = np.zeros(atr_period, dtype=np.float64)
    atr_val = 0.0
    atr_filled = 0
    atr_stop_price = 0.0
    prev_close = close_prices[0]

    # ── 凯利公式辅助变量 ───────────────────────────────
    kelly_f = 0.25  # 默认初次交易
    kelly_window = 20
    recent_trades = np.zeros(kelly_window, dtype=np.float64)
    recent_trade_count = 0
    kelly_wins = 0.0
    kelly_total = 0.0

    # ── 回撤熔断变量 ───────────────────────────────────
    peak_equity = initial_capital
    dd_breached = False
    dd_breach_idx = -1

    for i in range(n):
        price = close_prices[i]

        # ── 每日更新 ATR ────────────────────────────────
        if i > 0:
            tr = max(
                high_prices[i] - low_prices[i],
                abs(high_prices[i] - prev_close),
                abs(low_prices[i] - prev_close),
            )
        else:
            tr = high_prices[i] - low_prices[i]
        prev_close = price

        atr_buffer[i % atr_period] = tr
        atr_filled += 1
        if atr_filled >= atr_period:
            atr_val = np.mean(atr_buffer[:atr_period])
        else:
            atr_val = np.mean(atr_buffer[:max(1, i + 1)])

        if position == 0:
            if buy_trigger[i] and price > 0:
                prev_close_for_limit = close_prices[i - 1] if i > 0 else price
                if prev_close_for_limit > 0:
                    limit_up = prev_close_for_limit * (1.0 + limit_up_down_rate)
                    if price >= limit_up * 0.999:
                        equity[i] = cash
                        continue

                # ── 凯利仓位计算 ─────────────────────────
                if position_sizing == POSITION_KELLY:
                    if recent_trade_count >= kelly_window:
                        # 统计最近 kelly_window 笔交易
                        kw = 0.0
                        aw = 0.0
                        al = 0.0
                        for k in range(kelly_window):
                            rt = recent_trades[k]
                            if rt > 0.0:
                                kw += 1.0
                                aw += rt
                            elif rt < 0.0:
                                al += -rt
                        win_pct = kw / kelly_window
                        avg_win = aw / kw if kw > 0 else 0.0
                        avg_loss = al / (kelly_window - kw) if (kelly_window - kw) > 0 else 1.0
                        if avg_loss > 0.0:
                            b = avg_win / avg_loss
                            kelly_f = (b * win_pct - (1.0 - win_pct)) / b
                            kelly_f = max(0.01, min(kelly_f, max_position_pct))
                    position_pct = kelly_f
                elif position_sizing == POSITION_HALF_KELLY:
                    position_pct = kelly_f * 0.5
                elif position_sizing == POSITION_FIXED_PCT:
                    position_pct = fixed_position_pct
                else:  # POSITION_FULL
                    position_pct = 1.0

                position_pct = min(position_pct, max_position_pct)
                # 用仓位比例调整可投资金
                available_cash = cash * position_pct

                buy_price = price * (1.0 + slippage_rate)
                fee = buy_price * commission_rate
                shares = max((available_cash - fee) / buy_price, 0.0)
                shares = np.floor(shares / 100.0) * 100.0
                if shares < 100.0:
                    equity[i] = cash
                    continue

                cost = shares * buy_price + shares * buy_price * commission_rate
                cash -= cost
                position = 1
                entry_idx = i
                entry_price = buy_price
                highest_since_entry = price
                equity[i] = cash + shares * price
            else:
                equity[i] = cash

        else:
            exit_reason_code = 0
            should_exit = False

            if sell_trigger[i]:
                should_exit = True
                exit_reason_code = _REASON_SIGNAL
            elif hold_days < 99999 and (i - entry_idx) >= hold_days:
                should_exit = True
                exit_reason_code = _REASON_HOLD_EXPIRED
            elif stop_loss_pct > -999.0:
                ret_since_entry = (price / entry_price) - 1.0
                if ret_since_entry <= stop_loss_pct:
                    should_exit = True
                    exit_reason_code = _REASON_STOP_LOSS
            elif stop_profit_pct < 999.0:
                ret_since_entry = (price / entry_price) - 1.0
                if ret_since_entry >= stop_profit_pct:
                    should_exit = True
                    exit_reason_code = _REASON_STOP_PROFIT

            # ── 独立比例止盈（与 stop_profit_pct 同层级） ───
            if not should_exit and take_profit_pct > 0.0 and position == 1:
                pnl_pct = (price - entry_price) / entry_price
                if pnl_pct >= take_profit_pct:
                    should_exit = True
                    exit_reason_code = _REASON_STOP_PROFIT  # 复用止盈 reason

            # ── ATR 动态止损（trailing_pct 互斥检查前） ──
            if not should_exit and atr_stop_multiplier > 0.0 and atr_val > 0.0 and position == 1:
                if price > highest_since_entry:
                    highest_since_entry = price
                atr_stop_price = highest_since_entry - atr_stop_multiplier * atr_val
                if price <= atr_stop_price:
                    should_exit = True
                    exit_reason_code = _REASON_ATR_STOP

            # trailing_pct 与 ATR 止损互斥
            if not should_exit and atr_stop_multiplier <= 0.0 and trailing_pct < 999.0:
                highest_since_entry = max(highest_since_entry, price)
                dd_from_high = (highest_since_entry - price) / highest_since_entry
                if dd_from_high >= trailing_pct:
                    should_exit = True
                    exit_reason_code = _REASON_TRAILING_STOP

            # ── 回撤熔断检查 ────────────────────────────
            if not should_exit and max_drawdown_limit > 0.0 and not dd_breached:
                current_total = cash + shares * price
                if current_total > peak_equity:
                    peak_equity = current_total
                dd_ratio = (peak_equity - current_total) / peak_equity
                if dd_ratio >= max_drawdown_limit:
                    dd_breached = True
                    dd_breach_idx = i
                    should_exit = True
                    exit_reason_code = _REASON_DD_BREACHED

            # 跌停无法卖出
            prev_close_for_limit = close_prices[i - 1] if i > 0 else price
            if prev_close_for_limit > 0:
                limit_down = prev_close_for_limit * (1.0 - limit_up_down_rate)
                if price <= limit_down * 1.001:
                    should_exit = False

            if should_exit:
                sell_price = price * (1.0 - slippage_rate)
                sell_amount = shares * sell_price
                fee = sell_amount * (commission_rate + stamp_tax_rate)
                cash += sell_amount - fee
                ret_pct = (sell_price / entry_price) - 1.0
                if trade_count < max_trades:
                    trades_arr[trade_count, 0] = entry_idx
                    trades_arr[trade_count, 1] = i
                    trades_arr[trade_count, 2] = entry_price
                    trades_arr[trade_count, 3] = sell_price
                    trades_arr[trade_count, 4] = ret_pct
                    trades_arr[trade_count, 5] = exit_reason_code
                    trade_count += 1

                # ── 记录交易回报到凯利窗口 ───────────────
                trade_return = (sell_price - entry_price) / entry_price
                recent_trades[recent_trade_count % kelly_window] = trade_return
                recent_trade_count += 1

                position = 0
                shares = 0.0
                equity[i] = cash
            else:
                # 更新回撤熔断峰值（平仓不在这里但也更新）
                current_total = cash + shares * price
                equity[i] = current_total

    # 期末强制平仓
    if position == 1 and n > 0:
        last_price = close_prices[-1]
        sell_price = last_price * (1.0 - slippage_rate)
        sell_amount = shares * sell_price
        fee = sell_amount * (commission_rate + stamp_tax_rate)
        cash += sell_amount - fee
        ret_pct = (sell_price / entry_price) - 1.0
        if trade_count < max_trades:
            trades_arr[trade_count, 0] = entry_idx
            trades_arr[trade_count, 1] = n - 1
            trades_arr[trade_count, 2] = entry_price
            trades_arr[trade_count, 3] = sell_price
            trades_arr[trade_count, 4] = ret_pct
            trades_arr[trade_count, 5] = _REASON_END_OF_PERIOD
            trade_count += 1
        equity[-1] = cash

    # 提取有效交易
    trades_out = []
    for k in range(trade_count):
        reason_code = int(trades_arr[k, 5])
        trades_out.append((
            int(trades_arr[k, 0]),
            int(trades_arr[k, 1]),
            trades_arr[k, 2],
            trades_arr[k, 3],
            trades_arr[k, 4],
            reason_code,
        ))

    return trades_out, equity, dd_breached, dd_breach_idx


def _simulate_trades_python(
    close_prices, high_prices, low_prices,
    buy_trigger, sell_trigger,
    hold_days, stop_loss_pct, stop_profit_pct, trailing_pct,
    initial_capital, commission_rate, stamp_tax_rate, slippage_rate,
    limit_up_down_rate,
    atr_stop_multiplier, take_profit_pct, position_sizing,
    fixed_position_pct, max_position_pct, max_drawdown_limit,
):
    """纯 Python 回测循环（numba 不可用时的回退）"""
    return _simulate_trades_numba(
        close_prices, high_prices, low_prices,
        buy_trigger, sell_trigger,
        hold_days, stop_loss_pct, stop_profit_pct, trailing_pct,
        initial_capital, commission_rate, stamp_tax_rate, slippage_rate,
        limit_up_down_rate,
        atr_stop_multiplier, take_profit_pct, position_sizing,
        fixed_position_pct, max_position_pct, max_drawdown_limit,
    )


def _score_single_signal(
    signal_id: str,
    signal_matrix: np.ndarray,
    price_matrix: np.ndarray,
    objective: str,
) -> dict | None:
    """
    对单个信号在全部股票上评分（用于策略发现的多进程并行）。

    Args:
        signal_id: 信号ID
        signal_matrix: (n_days × n_stocks) bool
        price_matrix: (n_days × n_stocks) float
        objective: 优化目标

    Returns:
        评分字典
    """
    try:
        n_days, n_stocks = signal_matrix.shape
        # 确保维度匹配
        n_days = min(n_days, price_matrix.shape[0] - 1)
        n_stocks = min(n_stocks, price_matrix.shape[1])

        signal_mat = signal_matrix[:n_days, :n_stocks]
        price_mat = price_matrix[:n_days + 1, :n_stocks]

        returns_5d = []
        returns_10d = []
        returns_20d = []

        for forward in [5, 10, 20]:
            if n_days <= forward:
                continue
            future_prices = price_mat[forward:, :]
            trigger_part = signal_mat[:n_days - forward, :]
            for i in range(trigger_part.shape[0]):
                for j in range(trigger_part.shape[1]):
                    if trigger_part[i, j] and price_mat[i, j] > 0:
                        ret = future_prices[i, j] / price_mat[i, j] - 1.0
                        if forward == 5:
                            returns_5d.append(ret)
                        elif forward == 10:
                            returns_10d.append(ret)
                        else:
                            returns_20d.append(ret)

        all_returns = np.array(returns_5d + returns_10d + returns_20d)
        # 过滤 NaN/Inf（极端价格跳动、数据损坏等可能导致）
        all_returns = all_returns[np.isfinite(all_returns)]
        if len(all_returns) == 0:
            return None

        win_rate = float((all_returns > 0).mean())
        avg_return = float(all_returns.mean())
        max_dd = float(abs(all_returns.min())) if all_returns.min() < 0 else 0.0
        annual_return = avg_return * (252 / 15)  # 粗略年化
        total_trades = len(all_returns)

        # 根据目标计算得分
        if objective == "max_win_rate":
            score = win_rate
        elif objective == "min_drawdown":
            score = -max_dd if max_dd > 0 else 0.0
        elif objective == "max_sharpe":
            std_ret = float(all_returns.std()) + 1e-10
            score = avg_return / std_ret
        elif objective == "max_profit_loss_ratio":
            wins = all_returns[all_returns > 0]
            losses = abs(all_returns[all_returns < 0])
            avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
            avg_loss = float(losses.mean()) if len(losses) > 0 else 1.0
            score = avg_win / (avg_loss + 1e-10)
        else:
            score = win_rate * 0.5 + annual_return * 0.5

        # 清理 NaN/Inf（JSON 无法序列化，出现原因：极端价格跳动、除零等）
        import math

        def _safe(v: float, default: float = 0.0) -> float:
            if math.isnan(v) or math.isinf(v):
                return default
            return v

        return {
            "signal_id": signal_id,
            "score": _safe(score),
            "win_rate": _safe(win_rate),
            "annual_return": _safe(annual_return),
            "max_drawdown": _safe(max_dd),
            "total_trades": total_trades,
        }
    except Exception as e:
        return None
