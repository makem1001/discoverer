"""
发现者（Discoverer）— 信号计算服务

实现全部 69 个技术信号的计算函数。
每个信号接收 DataFrame，返回 bool Series 表示触发日期。
所有计算使用 pandas 向量化操作以确保性能。

P0-3 增强：
  - compute_signal_matrix_parallel() 使用 ThreadPoolExecutor 分批并行
  - _calc_macd_divergence_bullish/bearish 使用 @njit Numba JIT 加速
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from models.signals import ALL_SIGNALS, get_signal_by_id

# 尝试导入 numba（可选依赖）
try:
    from numba import njit
    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

    def njit(func=None, **kwargs):
        """numba 不可用时的空装饰器"""
        if func is not None:
            return func
        return lambda f: f

logger = logging.getLogger("discoverer.signal")


# ══════════════════════════════════════════════════════════════════
# Numba JIT 加速函数（仅当 numba 可用时生效）
# ══════════════════════════════════════════════════════════════════

@njit
def _macd_divergence_bullish_numba(
    close: np.ndarray, dif: np.ndarray, window: int = 20
) -> np.ndarray:
    """Numba 加速的 MACD 底背离检测。

    检测逻辑：
      在 window 窗口内，股价出现新低但 DIF 未出现新低。

    Args:
        close: 收盘价数组
        dif: MACD DIF 数组
        window: 回看窗口大小

    Returns:
        bool 数组，True 表示该位置触发底背离
    """
    n = len(close)
    result = np.zeros(n, dtype=np.bool_)
    if n < window + 1:
        return result

    for i in range(window, n):
        # 在 [i-window, i] 窗口内找 close 最小值及其位置
        close_min = close[i - window]
        close_min_idx = i - window
        for j in range(i - window + 1, i + 1):
            if close[j] < close_min:
                close_min = close[j]
                close_min_idx = j

        # close[i] 是窗口内的新低
        if close[i] <= close_min and dif[i] > dif[close_min_idx]:
            result[i] = True

    return result


@njit
def _macd_divergence_bearish_numba(
    close: np.ndarray, dif: np.ndarray, window: int = 20
) -> np.ndarray:
    """Numba 加速的 MACD 顶背离检测。

    检测逻辑：
      在 window 窗口内，股价出现新高但 DIF 未出现新高。

    Args:
        close: 收盘价数组
        dif: MACD DIF 数组
        window: 回看窗口大小

    Returns:
        bool 数组，True 表示该位置触发顶背离
    """
    n = len(close)
    result = np.zeros(n, dtype=np.bool_)
    if n < window + 1:
        return result

    for i in range(window, n):
        # 在 [i-window, i] 窗口内找 close 最大值及其位置
        close_max = close[i - window]
        close_max_idx = i - window
        for j in range(i - window + 1, i + 1):
            if close[j] > close_max:
                close_max = close[j]
                close_max_idx = j

        # close[i] 是窗口内的新高
        if close[i] >= close_max and dif[i] < dif[close_max_idx]:
            result[i] = True

    return result


class SignalService:
    """信号计算服务：计算所有69个技术指标的触发信号"""

    def compute_signal(self, df: pd.DataFrame, signal_id: str) -> pd.Series:
        """计算单个信号在给定 DataFrame 上的触发情况。

        Args:
            df: 日线数据 DataFrame，需包含 date, open, high, low, close, volume 列
            signal_id: 信号ID

        Returns:
            bool Series，index 为 df.index，True 表示该日触发信号
        """
        signal_def = get_signal_by_id(signal_id)
        if signal_def is None:
            logger.warning(f"未知信号: {signal_id}")
            return pd.Series(False, index=df.index)

        method_name = f"_calc_{signal_id}"
        if hasattr(self, method_name):
            try:
                result = getattr(self, method_name)(df, signal_def.params)
                return result.fillna(False)
            except Exception as e:
                logger.error(f"计算信号 {signal_id} 失败: {e}")
                return pd.Series(False, index=df.index)
        else:
            logger.warning(f"信号 {signal_id} 尚未实现计算逻辑")
            return pd.Series(False, index=df.index)

    def compute_signal_matrix(
        self,
        stock_codes: List[str],
        signal_id: str,
        data_service=None,
    ) -> np.ndarray:
        """计算信号在全市场股票上的触发矩阵（单线程版本，保留作为 fallback）。

        Args:
            stock_codes: 股票代码列表
            signal_id: 信号ID
            data_service: DataService 实例

        Returns:
            2D bool ndarray (n_days × n_stocks)
        """
        if data_service is None:
            from dependencies import get_data_service
            data_service = get_data_service()

        matrices = []
        for code in stock_codes:
            df = data_service.get_daily_data(code)
            if df.empty:
                matrices.append(None)
                continue
            signal_series = self.compute_signal(df, signal_id)
            # 对齐到统一日期索引
            signal_df = pd.DataFrame({
                "date": pd.to_datetime(df["date"]),
                "signal": signal_series.values,
            })
            signal_df = signal_df.set_index("date")
            matrices.append(signal_df)

        if not matrices or all(m is None for m in matrices):
            return np.zeros((1, 1), dtype=bool)

        # 找到所有股票的共同日期范围
        all_dates = pd.DatetimeIndex([])
        for m in matrices:
            if m is not None:
                all_dates = all_dates.union(m.index)

        if len(all_dates) == 0:
            return np.zeros((1, len(stock_codes)), dtype=bool)

        all_dates = all_dates.sort_values()

        # 构建矩阵
        n_days = len(all_dates)
        n_stocks = len(stock_codes)
        matrix = np.zeros((n_days, n_stocks), dtype=bool)

        for j, m in enumerate(matrices):
            if m is not None:
                common_dates = all_dates.intersection(m.index)
                for d in common_dates:
                    i = all_dates.get_loc(d)
                    matrix[i, j] = bool(m.loc[d, "signal"])

        return matrix

    # ── P0-3 新增：并行计算信号矩阵 ────────────────────

    def compute_signal_matrix_parallel(
        self,
        stock_codes: List[str],
        signal_id: str,
        data_service=None,
        batch_size: int = 50,
    ) -> np.ndarray:
        """使用 ThreadPoolExecutor 分批并行计算信号矩阵。

        Args:
            stock_codes: 股票代码列表
            signal_id: 信号ID
            data_service: DataService 实例
            batch_size: 每批处理的股票数量

        Returns:
            2D bool ndarray (n_days × n_stocks)
        """
        if data_service is None:
            from dependencies import get_data_service
            data_service = get_data_service()

        if len(stock_codes) <= batch_size:
            # 数据量小，直接用单线程版本
            return self.compute_signal_matrix(stock_codes, signal_id, data_service)

        # 分批
        batches = [
            stock_codes[i:i + batch_size]
            for i in range(0, len(stock_codes), batch_size)
        ]

        # 每批返回 (batch_matrix, batch_start_col)
        max_workers = min(os.cpu_count() or 4, len(batches))

        results_by_batch: Dict[int, np.ndarray] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: Dict = {}
            for batch_idx, batch in enumerate(batches):
                future = executor.submit(
                    self._compute_batch_matrix, batch, signal_id, data_service
                )
                futures[future] = batch_idx

            for future in as_completed(futures):
                batch_idx = futures[future]
                try:
                    batch_matrix = future.result()
                    results_by_batch[batch_idx] = batch_matrix
                except Exception as e:
                    logger.error(f"批次 {batch_idx} 信号矩阵计算失败: {e}")
                    # 返回空矩阵占位
                    results_by_batch[batch_idx] = np.zeros(
                        (1, len(batches[batch_idx])), dtype=bool
                    )

        # 合并所有批次结果
        # 先确定最大行数（n_days）
        max_rows = max(m.shape[0] for m in results_by_batch.values()) if results_by_batch else 1

        # 按批次顺序拼接
        all_matrices = [
            results_by_batch.get(i, np.zeros((max_rows, len(batches[i])), dtype=bool))
            for i in range(len(batches))
        ]

        # 对齐行数
        for i, m in enumerate(all_matrices):
            if m.shape[0] < max_rows:
                padded = np.zeros((max_rows, m.shape[1]), dtype=bool)
                padded[:m.shape[0], :] = m
                all_matrices[i] = padded

        if not all_matrices:
            return np.zeros((1, 1), dtype=bool)

        return np.hstack(all_matrices)

    def _compute_batch_matrix(
        self,
        batch: List[str],
        signal_id: str,
        data_service,
    ) -> np.ndarray:
        """计算单批股票的信号矩阵（供并行调用）。

        Args:
            batch: 一批股票代码
            signal_id: 信号ID
            data_service: DataService 实例

        Returns:
            2D bool ndarray
        """
        return self.compute_signal_matrix(batch, signal_id, data_service)

    # ═══════════════════════════════════════════════════════════
    # 均线类 (MA) — 12个信号
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _calc_ma(df: pd.DataFrame, period: int) -> pd.Series:
        """计算移动平均线"""
        return df["close"].rolling(window=period, min_periods=period).mean()

    def _calc_ma_golden_cross(self, df: pd.DataFrame, params: dict) -> pd.Series:
        fast, slow = params.get("fast", 5), params.get("slow", 20)
        ma_fast = self._calc_ma(df, fast)
        ma_slow = self._calc_ma(df, slow)
        return (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))

    def _calc_ma_death_cross(self, df: pd.DataFrame, params: dict) -> pd.Series:
        fast, slow = params.get("fast", 5), params.get("slow", 20)
        ma_fast = self._calc_ma(df, fast)
        ma_slow = self._calc_ma(df, slow)
        return (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))

    def _calc_ma_golden_cross_10_30(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_ma_golden_cross(df, {"fast": 10, "slow": 30})

    def _calc_ma_death_cross_10_30(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_ma_death_cross(df, {"fast": 10, "slow": 30})

    def _calc_ma_golden_cross_20_60(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_ma_golden_cross(df, {"fast": 20, "slow": 60})

    def _calc_ma_death_cross_20_60(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_ma_death_cross(df, {"fast": 20, "slow": 60})

    def _calc_price_above_ma5(self, df: pd.DataFrame, params: dict) -> pd.Series:
        ma = params.get("ma", 5)
        ma_val = self._calc_ma(df, ma)
        return (df["close"] > ma_val) & (df["close"].shift(1) <= ma_val.shift(1))

    def _calc_price_below_ma5(self, df: pd.DataFrame, params: dict) -> pd.Series:
        ma = params.get("ma", 5)
        ma_val = self._calc_ma(df, ma)
        return (df["close"] < ma_val) & (df["close"].shift(1) >= ma_val.shift(1))

    def _calc_price_above_ma20(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_price_above_ma5(df, {"ma": 20})

    def _calc_price_below_ma20(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_price_below_ma5(df, {"ma": 20})

    def _calc_ma_bullish_alignment(self, df: pd.DataFrame, params: dict) -> pd.Series:
        mas = params.get("mas", [5, 10, 20, 60])
        ma_vals = {p: self._calc_ma(df, p) for p in mas}
        # MA5 > MA10 > MA20 > MA60
        result = pd.Series(True, index=df.index)
        for i in range(len(mas) - 1):
            result = result & (ma_vals[mas[i]] > ma_vals[mas[i + 1]])
        return result

    def _calc_ma_bearish_alignment(self, df: pd.DataFrame, params: dict) -> pd.Series:
        mas = params.get("mas", [5, 10, 20, 60])
        ma_vals = {p: self._calc_ma(df, p) for p in mas}
        result = pd.Series(True, index=df.index)
        for i in range(len(mas) - 1):
            result = result & (ma_vals[mas[i]] < ma_vals[mas[i + 1]])
        return result

    # ═══════════════════════════════════════════════════════════
    # MACD类 — 6个信号
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _calc_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9):
        """计算 MACD 指标，返回 (DIF, DEA, MACD柱)"""
        ema_fast = df["close"].ewm(span=fast, min_periods=fast).mean()
        ema_slow = df["close"].ewm(span=slow, min_periods=slow).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, min_periods=signal).mean()
        macd_bar = 2 * (dif - dea)
        return dif, dea, macd_bar

    def _calc_macd_golden_cross(self, df: pd.DataFrame, params: dict) -> pd.Series:
        dif, dea, _ = self._calc_macd(df, **params)
        return (dif > dea) & (dif.shift(1) <= dea.shift(1))

    def _calc_macd_death_cross(self, df: pd.DataFrame, params: dict) -> pd.Series:
        dif, dea, _ = self._calc_macd(df, **params)
        return (dif < dea) & (dif.shift(1) >= dea.shift(1))

    def _calc_macd_above_zero(self, df: pd.DataFrame, params: dict) -> pd.Series:
        dif, dea, _ = self._calc_macd(df)
        return (dif > 0) & (dea > 0) & ((dif.shift(1) <= 0) | (dea.shift(1) <= 0))

    def _calc_macd_below_zero(self, df: pd.DataFrame, params: dict) -> pd.Series:
        dif, dea, _ = self._calc_macd(df)
        return (dif < 0) & (dea < 0) & ((dif.shift(1) >= 0) | (dea.shift(1) >= 0))

    def _calc_macd_divergence_bullish(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """MACD底背离：股价新低但DIF未新低（优先使用 Numba JIT 加速）"""
        dif, dea, _ = self._calc_macd(df)

        if _NUMBA_AVAILABLE:
            close_arr = df["close"].values.astype(np.float64)
            dif_arr = dif.values.astype(np.float64)
            # 填充 NaN 为 0（Numba 不处理 NaN）
            close_arr = np.nan_to_num(close_arr, nan=0.0)
            dif_arr = np.nan_to_num(dif_arr, nan=0.0)
            result_arr = _macd_divergence_bullish_numba(close_arr, dif_arr)
            return pd.Series(result_arr, index=df.index)

        # fallback: 纯 Python 循环版本
        close = df["close"]
        result = pd.Series(False, index=df.index)
        for i in range(40, len(df)):
            window = slice(i - 20, i + 1)
            close_min_idx = close.iloc[window].idxmin()
            dif_at_close_min = dif.loc[close_min_idx]
            if close.iloc[i] < close.iloc[i - 20:i].min() and dif.iloc[i] > dif_at_close_min:
                result.iloc[i] = True
        return result

    def _calc_macd_divergence_bearish(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """MACD顶背离：股价新高但DIF未新高（优先使用 Numba JIT 加速）"""
        dif, dea, _ = self._calc_macd(df)

        if _NUMBA_AVAILABLE:
            close_arr = df["close"].values.astype(np.float64)
            dif_arr = dif.values.astype(np.float64)
            close_arr = np.nan_to_num(close_arr, nan=0.0)
            dif_arr = np.nan_to_num(dif_arr, nan=0.0)
            result_arr = _macd_divergence_bearish_numba(close_arr, dif_arr)
            return pd.Series(result_arr, index=df.index)

        # fallback: 纯 Python 循环版本
        close = df["close"]
        result = pd.Series(False, index=df.index)
        for i in range(40, len(df)):
            window = slice(i - 20, i + 1)
            close_max_idx = close.iloc[window].idxmax()
            dif_at_close_max = dif.loc[close_max_idx]
            if close.iloc[i] > close.iloc[i - 20:i].max() and dif.iloc[i] < dif_at_close_max:
                result.iloc[i] = True
        return result

    # ═══════════════════════════════════════════════════════════
    # KDJ类 — 6个信号
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _calc_kdj(df: pd.DataFrame, n: int = 9):
        """计算 KDJ 指标，返回 (K, D, J)"""
        low_n = df["low"].rolling(window=n, min_periods=n).min()
        high_n = df["high"].rolling(window=n, min_periods=n).max()
        rsv = ((df["close"] - low_n) / (high_n - low_n + 1e-10)) * 100
        k = rsv.ewm(com=2, min_periods=n).mean()
        d = k.ewm(com=2, min_periods=n).mean()
        j = 3 * k - 2 * d
        return k, d, j

    def _calc_kdj_golden_cross(self, df: pd.DataFrame, params: dict) -> pd.Series:
        k, d, _ = self._calc_kdj(df, **params)
        return (k > d) & (k.shift(1) <= d.shift(1))

    def _calc_kdj_death_cross(self, df: pd.DataFrame, params: dict) -> pd.Series:
        k, d, _ = self._calc_kdj(df, **params)
        return (k < d) & (k.shift(1) >= d.shift(1))

    def _calc_kdj_oversold(self, df: pd.DataFrame, params: dict) -> pd.Series:
        threshold = params.get("threshold", 20)
        k, d, _ = self._calc_kdj(df)
        prev_k, prev_d = k.shift(1), d.shift(1)
        return (k < threshold) & (d < threshold) & ((prev_k >= threshold) | (prev_d >= threshold))

    def _calc_kdj_overbought(self, df: pd.DataFrame, params: dict) -> pd.Series:
        threshold = params.get("threshold", 80)
        k, d, _ = self._calc_kdj(df)
        prev_k, prev_d = k.shift(1), d.shift(1)
        return (k > threshold) & (d > threshold) & ((prev_k <= threshold) | (prev_d <= threshold))

    def _calc_kdj_j_oversold(self, df: pd.DataFrame, params: dict) -> pd.Series:
        _, _, j = self._calc_kdj(df)
        return (j < 0) & (j.shift(1) >= 0)

    def _calc_kdj_j_overbought(self, df: pd.DataFrame, params: dict) -> pd.Series:
        _, _, j = self._calc_kdj(df)
        return (j > 100) & (j.shift(1) <= 100)

    # ═══════════════════════════════════════════════════════════
    # RSI类 — 6个信号
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _calc_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 RSI 指标"""
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calc_rsi_oversold_6(self, df: pd.DataFrame, params: dict) -> pd.Series:
        rsi = self._calc_rsi(df, period=6)
        threshold = params.get("threshold", 30)
        return (rsi < threshold) & (rsi.shift(1) >= threshold)

    def _calc_rsi_overbought_6(self, df: pd.DataFrame, params: dict) -> pd.Series:
        rsi = self._calc_rsi(df, period=6)
        threshold = params.get("threshold", 70)
        return (rsi > threshold) & (rsi.shift(1) <= threshold)

    def _calc_rsi_oversold_14(self, df: pd.DataFrame, params: dict) -> pd.Series:
        rsi = self._calc_rsi(df, period=14)
        threshold = params.get("threshold", 30)
        return (rsi < threshold) & (rsi.shift(1) >= threshold)

    def _calc_rsi_overbought_14(self, df: pd.DataFrame, params: dict) -> pd.Series:
        rsi = self._calc_rsi(df, period=14)
        threshold = params.get("threshold", 70)
        return (rsi > threshold) & (rsi.shift(1) <= threshold)

    def _calc_rsi_golden_cross(self, df: pd.DataFrame, params: dict) -> pd.Series:
        rsi_fast = self._calc_rsi(df, period=6)
        rsi_slow = self._calc_rsi(df, period=14)
        return (rsi_fast > rsi_slow) & (rsi_fast.shift(1) <= rsi_slow.shift(1))

    def _calc_rsi_death_cross(self, df: pd.DataFrame, params: dict) -> pd.Series:
        rsi_fast = self._calc_rsi(df, period=6)
        rsi_slow = self._calc_rsi(df, period=14)
        return (rsi_fast < rsi_slow) & (rsi_fast.shift(1) >= rsi_slow.shift(1))

    # ═══════════════════════════════════════════════════════════
    # 布林带(BOLL) — 5个信号
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _calc_boll(df: pd.DataFrame, period: int = 20, std: float = 2.0):
        """计算布林带，返回 (mid, upper, lower, width)"""
        mid = df["close"].rolling(window=period, min_periods=period).mean()
        std_val = df["close"].rolling(window=period, min_periods=period).std()
        upper = mid + std * std_val
        lower = mid - std * std_val
        width = (upper - lower) / (mid + 1e-10)
        return mid, upper, lower, width

    def _calc_boll_lower_touch(self, df: pd.DataFrame, params: dict) -> pd.Series:
        _, _, lower, _ = self._calc_boll(df, **params)
        return (df["close"] <= lower) & (df["close"].shift(1) > lower.shift(1))

    def _calc_boll_upper_touch(self, df: pd.DataFrame, params: dict) -> pd.Series:
        _, upper, _, _ = self._calc_boll(df, **params)
        return (df["close"] >= upper) & (df["close"].shift(1) < upper.shift(1))

    def _calc_boll_mid_break_up(self, df: pd.DataFrame, params: dict) -> pd.Series:
        mid, _, _, _ = self._calc_boll(df, **params)
        return (df["close"] > mid) & (df["close"].shift(1) <= mid.shift(1))

    def _calc_boll_mid_break_down(self, df: pd.DataFrame, params: dict) -> pd.Series:
        mid, _, _, _ = self._calc_boll(df, **params)
        return (df["close"] < mid) & (df["close"].shift(1) >= mid.shift(1))

    def _calc_boll_squeeze(self, df: pd.DataFrame, params: dict) -> pd.Series:
        _, _, _, width = self._calc_boll(df, **params)
        # 布林带宽度处于近60日最低10%分位
        width_min_60 = width.rolling(window=60, min_periods=60).min()
        return width <= width_min_60 * 1.05

    # ═══════════════════════════════════════════════════════════
    # 成交量(Volume) — 8个信号
    # ═══════════════════════════════════════════════════════════

    def _calc_vol_breakout_1_5(self, df: pd.DataFrame, params: dict) -> pd.Series:
        multiplier = params.get("multiplier", 1.5)
        ma_period = params.get("ma_period", 20)
        vol_ma = df["volume"].rolling(window=ma_period, min_periods=ma_period).mean()
        return df["volume"] > vol_ma * multiplier

    def _calc_vol_breakout_2(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_vol_breakout_1_5(df, {"multiplier": 2.0, "ma_period": 20})

    def _calc_vol_breakout_3(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_vol_breakout_1_5(df, {"multiplier": 3.0, "ma_period": 20})

    def _calc_vol_shrink_half(self, df: pd.DataFrame, params: dict) -> pd.Series:
        multiplier = params.get("multiplier", 0.5)
        ma_period = params.get("ma_period", 20)
        vol_ma = df["volume"].rolling(window=ma_period, min_periods=ma_period).mean()
        return df["volume"] < vol_ma * multiplier

    def _calc_vol_price_rise(self, df: pd.DataFrame, params: dict) -> pd.Series:
        vol_ma = df["volume"].rolling(window=20, min_periods=20).mean()
        return (df["close"] > df["close"].shift(1)) & (df["volume"] > vol_ma * 1.2)

    def _calc_vol_price_fall(self, df: pd.DataFrame, params: dict) -> pd.Series:
        vol_ma = df["volume"].rolling(window=20, min_periods=20).mean()
        return (df["close"] < df["close"].shift(1)) & (df["volume"] > vol_ma * 1.2)

    def _calc_vol_3day_increasing(self, df: pd.DataFrame, params: dict) -> pd.Series:
        days = params.get("days", 3)
        result = pd.Series(True, index=df.index)
        for d in range(1, days):
            result = result & (df["volume"] > df["volume"].shift(d))
        return result

    def _calc_vol_5day_shrinking(self, df: pd.DataFrame, params: dict) -> pd.Series:
        vol_ma = df["volume"].rolling(window=20, min_periods=20).mean()
        result = pd.Series(True, index=df.index)
        for d in range(5):
            result = result & (df["volume"].shift(d) < vol_ma.shift(d))
        return result

    # ═══════════════════════════════════════════════════════════
    # 形态类(Pattern) — 10个信号
    # ═══════════════════════════════════════════════════════════

    def _calc_hammer(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """锤子线：下影线 > 实体2倍，实体较小"""
        body = abs(df["close"] - df["open"])
        lower_shadow = df[["open", "close"]].min(axis=1) - df["low"]
        upper_shadow = df["high"] - df[["open", "close"]].max(axis=1)
        return (lower_shadow > body * 2) & (upper_shadow < body * 0.5) & (body > 0)

    def _calc_shooting_star(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """射击之星：上影线 > 实体2倍，实体较小"""
        body = abs(df["close"] - df["open"])
        upper_shadow = df["high"] - df[["open", "close"]].max(axis=1)
        lower_shadow = df[["open", "close"]].min(axis=1) - df["low"]
        return (upper_shadow > body * 2) & (lower_shadow < body * 0.5) & (body > 0)

    def _calc_engulfing_bullish(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """看涨吞没"""
        prev_body = df["open"].shift(1) - df["close"].shift(1)  # 前日阴线
        curr_body = df["close"] - df["open"]  # 当日阳线
        return (prev_body > 0) & (curr_body > prev_body) & (df["open"] <= df["close"].shift(1)) & (df["close"] >= df["open"].shift(1))

    def _calc_engulfing_bearish(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """看跌吞没"""
        prev_body = df["close"].shift(1) - df["open"].shift(1)  # 前日阳线
        curr_body = df["open"] - df["close"]  # 当日阴线
        return (prev_body > 0) & (curr_body > prev_body) & (df["open"] >= df["close"].shift(1)) & (df["close"] <= df["open"].shift(1))

    def _calc_three_white_soldiers(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """三白兵：连续3根实体递增的阳线"""
        c1 = (df["close"] > df["open"]) & (df["close"].shift(1) > df["open"].shift(1)) & (df["close"].shift(2) > df["open"].shift(2))
        body1 = df["close"] - df["open"]
        body2 = body1.shift(1)
        body3 = body1.shift(2)
        return c1 & (body1 > body2) & (body2 > body3)

    def _calc_three_black_crows(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """三乌鸦：连续3根实体递增的阴线"""
        c1 = (df["close"] < df["open"]) & (df["close"].shift(1) < df["open"].shift(1)) & (df["close"].shift(2) < df["open"].shift(2))
        body1 = df["open"] - df["close"]
        body2 = body1.shift(1)
        body3 = body1.shift(2)
        return c1 & (body1 > body2) & (body2 > body3)

    def _calc_doji(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """十字星：实体极小"""
        body = abs(df["close"] - df["open"])
        avg_body = body.rolling(window=20, min_periods=20).mean()
        return (body < avg_body * 0.3) & (body > 0)

    def _calc_breakout_20day_high(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 20)
        high_n = df["high"].rolling(window=period, min_periods=period).max().shift(1)
        return df["close"] > high_n

    def _calc_breakdown_20day_low(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 20)
        low_n = df["low"].rolling(window=period, min_periods=period).min().shift(1)
        return df["close"] < low_n

    def _calc_gap_up(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return df["low"] > df["high"].shift(1)

    # ═══════════════════════════════════════════════════════════
    # 趋势类(Trend) — 6个信号
    # ═══════════════════════════════════════════════════════════

    def _calc_new_high_20(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 20)
        rolling_high = df["close"].rolling(window=period, min_periods=period).max().shift(1)
        return df["close"] > rolling_high

    def _calc_new_low_20(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 20)
        rolling_low = df["close"].rolling(window=period, min_periods=period).min().shift(1)
        return df["close"] < rolling_low

    def _calc_new_high_60(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_new_high_20(df, {"period": 60})

    def _calc_new_low_60(self, df: pd.DataFrame, params: dict) -> pd.Series:
        return self._calc_new_low_20(df, {"period": 60})

    def _calc_consecutive_up_3(self, df: pd.DataFrame, params: dict) -> pd.Series:
        days = params.get("days", 3)
        result = pd.Series(True, index=df.index)
        for d in range(days):
            result = result & (df["close"].shift(d) > df["close"].shift(d + 1))
        return result

    def _calc_consecutive_down_3(self, df: pd.DataFrame, params: dict) -> pd.Series:
        days = params.get("days", 3)
        result = pd.Series(True, index=df.index)
        for d in range(days):
            result = result & (df["close"].shift(d) < df["close"].shift(d + 1))
        return result

    # ═══════════════════════════════════════════════════════════
    # 动量类(Momentum) — 6个信号
    # ═══════════════════════════════════════════════════════════

    def _calc_momentum_5d_strong(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 5)
        threshold = params.get("threshold", 0.05)
        momentum = df["close"].pct_change(periods=period)
        return (momentum > threshold) & (momentum.shift(1) <= threshold)

    def _calc_momentum_5d_weak(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 5)
        threshold = params.get("threshold", -0.05)
        momentum = df["close"].pct_change(periods=period)
        return (momentum < threshold) & (momentum.shift(1) >= threshold)

    def _calc_momentum_20d_strong(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 20)
        threshold = params.get("threshold", 0.10)
        momentum = df["close"].pct_change(periods=period)
        return (momentum > threshold) & (momentum.shift(1) <= threshold)

    def _calc_momentum_20d_weak(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 20)
        threshold = params.get("threshold", -0.10)
        momentum = df["close"].pct_change(periods=period)
        return (momentum < threshold) & (momentum.shift(1) >= threshold)

    def _calc_volume_price_ratio(self, df: pd.DataFrame, params: dict) -> pd.Series:
        threshold = params.get("threshold", 1.5)
        vol_ma5 = df["volume"].rolling(window=5, min_periods=5).mean()
        vpr = df["volume"] / (vol_ma5 + 1e-10)
        return vpr > threshold

    def _calc_turnover_rate_high(self, df: pd.DataFrame, params: dict) -> pd.Series:
        """高换手率（需要换手率数据，若无则返回False）"""
        threshold = params.get("threshold", 0.10)
        if "turnover_rate" in df.columns:
            return df["turnover_rate"] > threshold
        return pd.Series(False, index=df.index)

    # ═══════════════════════════════════════════════════════════
    # 波动率(Volatility) — 4个信号
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算 ATR (Average True Range)"""
        high, low, close = df["high"], df["low"], df["close"].shift(1)
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, min_periods=period).mean()

    def _calc_atr_high(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 14)
        atr = self._calc_atr(df, period)
        atr_ma20 = atr.rolling(window=20, min_periods=20).mean()
        return atr > atr_ma20 * 1.5

    def _calc_atr_low(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 14)
        atr = self._calc_atr(df, period)
        atr_ma20 = atr.rolling(window=20, min_periods=20).mean()
        return atr < atr_ma20 * 0.5

    def _calc_volatility_breakout(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 20)
        returns = df["close"].pct_change()
        vol = returns.rolling(window=period, min_periods=period).std()
        vol_ma = vol.rolling(window=60, min_periods=60).mean()
        vol_std = vol.rolling(window=60, min_periods=60).std()
        return vol > vol_ma + 2 * vol_std

    def _calc_low_volatility(self, df: pd.DataFrame, params: dict) -> pd.Series:
        period = params.get("period", 20)
        returns = df["close"].pct_change()
        vol = returns.rolling(window=period, min_periods=period).std()
        vol_percentile = vol.rolling(window=250, min_periods=250).apply(
            lambda x: (x.iloc[-1] <= np.percentile(x, 25)), raw=False
        )
        return vol_percentile > 0
