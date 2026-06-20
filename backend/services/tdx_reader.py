"""
通达信（TDX）.day 日线文件读取器

通达信日线数据为 32 字节定长二进制记录，本模块使用 Python struct 模块进行高效解析。

文件路径规则：
  {vipdoc}/sh/lday/sh600000.day  → 上证股票（6 开头）
  {vipdoc}/sz/lday/sz000001.day  → 深证股票（0/3 开头）
"""

from __future__ import annotations

import logging
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("discoverer.tdx")


class TDXReader:
    """通达信 .day 文件读取器

    解析通达信本地日线二进制文件（32 字节定长记录），
    返回标准化的 pandas DataFrame。

    通达信 .day 文件格式（32 字节定长记录，小端序）：
    ┌────────┬──────┬──────────┬──────────────────────────┐
    │ 偏移   │ 长度 │ 类型     │ 字段                     │
    ├────────┼──────┼──────────┼──────────────────────────┤
    │ 0      │ 4    │ int32    │ 日期 (YYYYMMDD 整数)     │
    │ 4      │ 4    │ int32    │ open (单位：分，÷100)    │
    │ 8      │ 4    │ int32    │ high (单位：分)          │
    │ 12     │ 4    │ int32    │ low (单位：分)           │
    │ 16     │ 4    │ int32    │ close (单位：分)         │
    │ 20     │ 4    │ float32  │ amount (成交额，单位：元) │
    │ 24     │ 4    │ int32    │ volume (成交量，单位：手) │
    │ 28     │ 4    │ int32    │ reserved (保留)          │
    └────────┴──────┴──────────┴──────────────────────────┘
    """

    RECORD_SIZE: int = 32
    RECORD_FORMAT: str = "<IIIIfIII"  # 5 个 int32 + 1 个 float32 + 2 个 int32 = 8 字段 × 4 字节 = 32 字节

    def __init__(self, tdx_dir: str = ""):
        """初始化 TDX 读取器。

        Args:
            tdx_dir: 通达信 vipdoc 目录路径，空字符串表示未配置。
        """
        self.tdx_dir: str = tdx_dir

    # ── 状态检查 ────────────────────────────────────────

    def is_available(self) -> bool:
        """检查 TDX 数据目录是否可用。

        Returns:
            True 如果 tdx_dir 非空且目录存在。
        """
        if not self.tdx_dir:
            return False
        path = Path(self.tdx_dir)
        return path.exists() and path.is_dir()

    def get_status(self) -> dict:
        """返回 TDX 状态信息。

        Returns:
            dict 包含 available, tdx_dir, file_count 字段。
        """
        available = self.is_available()
        file_count = 0
        if available:
            try:
                tdx_path = Path(self.tdx_dir)
                sh_files = list(tdx_path.glob("sh/lday/*.day"))
                sz_files = list(tdx_path.glob("sz/lday/*.day"))
                file_count = len(sh_files) + len(sz_files)
            except Exception:
                pass

        return {
            "available": available,
            "tdx_dir": str(self.tdx_dir) if self.tdx_dir else "",
            "file_count": file_count,
        }

    # ── 文件路径推断 ────────────────────────────────────

    def _get_file_path(self, stock_code: str) -> Optional[Path]:
        """根据股票代码推断 .day 文件路径。

        规则：
          - 6 开头 → sh/lday/sh{code}.day（上证）
          - 0/3 开头 → sz/lday/sz{code}.day（深证）
          - 68 开头 → sh/lday/sh{code}.day（科创板，上证）

        Args:
            stock_code: 6 位数字股票代码。

        Returns:
            文件 Path 对象，如果目录不可用或文件不存在返回 None。
        """
        if not self.is_available():
            return None

        code = stock_code.strip()
        if not code.isdigit() or len(code) != 6:
            logger.debug(f"无效股票代码格式: {stock_code}")
            return None

        first_char = code[0]
        if first_char == "6":
            market = "sh"
        elif first_char in ("0", "3"):
            market = "sz"
        else:
            logger.debug(f"无法判断股票代码市场: {stock_code}")
            return None

        file_path = Path(self.tdx_dir) / market / "lday" / f"{market}{code}.day"
        if not file_path.exists():
            logger.debug(f".day 文件不存在: {file_path}")
            return None

        return file_path

    # ── 数据读取 ────────────────────────────────────────

    def read_daily(
        self,
        stock_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """读取单只股票的 .day 文件，返回标准化 DataFrame。

        列：date, open, high, low, close, volume, amount, pre_close。
        如果文件不存在或解析失败，返回空 DataFrame。

        Args:
            stock_code: 6 位股票代码。
            start_date: 开始日期 "YYYY-MM-DD"，可选。
            end_date: 结束日期 "YYYY-MM-DD"，可选。

        Returns:
            标准化 DataFrame，失败时为空 DataFrame。
        """
        file_path = self._get_file_path(stock_code)
        if file_path is None:
            return pd.DataFrame()

        try:
            raw_bytes = file_path.read_bytes()
            total_size = len(raw_bytes)

            if total_size < self.RECORD_SIZE:
                logger.warning(f".day 文件过小 {stock_code}: {total_size} bytes")
                return pd.DataFrame()

            if total_size % self.RECORD_SIZE != 0:
                logger.warning(
                    f".day 文件大小非 32 整数倍 {stock_code}: "
                    f"{total_size} bytes，将截断解析"
                )

            # 批量解析每条 32 字节记录
            record_count = total_size // self.RECORD_SIZE
            records: list = []
            for i in range(record_count):
                offset = i * self.RECORD_SIZE
                record = struct.unpack(
                    self.RECORD_FORMAT,
                    raw_bytes[offset : offset + self.RECORD_SIZE],
                )
                records.append(record)

            if not records:
                logger.warning(f".day 文件无有效记录: {stock_code}")
                return pd.DataFrame()

            # 构建 DataFrame
            df = pd.DataFrame(
                records,
                columns=[
                    "date_int",
                    "open_raw",
                    "high_raw",
                    "low_raw",
                    "close_raw",
                    "amount",
                    "volume",
                    "reserved",
                ],
            )

            # 价格转换：通达信存储单位为"分"，除以 100 转为"元"
            df["open"] = (df["open_raw"] / 100.0).round(2)
            df["high"] = (df["high_raw"] / 100.0).round(2)
            df["low"] = (df["low_raw"] / 100.0).round(2)
            df["close"] = (df["close_raw"] / 100.0).round(2)

            # 日期转换：YYYYMMDD 整数 → datetime
            df["date"] = pd.to_datetime(df["date_int"].astype(str), format="%Y%m%d")

            # 按日期排序并计算 pre_close
            df = df.sort_values("date").reset_index(drop=True)
            df["pre_close"] = df["close"].shift(1)

            # 日期范围过滤
            if start_date is not None:
                start_dt = pd.to_datetime(start_date)
                df = df[df["date"] >= start_dt]
            if end_date is not None:
                end_dt = pd.to_datetime(end_date)
                df = df[df["date"] <= end_dt]

            # 标准化输出列
            df = df[["date", "open", "high", "low", "close", "volume", "amount", "pre_close"]]

            logger.info(f"TDX 读取成功 {stock_code}: {len(df)} 条记录 (文件: {file_path})")
            return df

        except struct.error as e:
            logger.warning(f"TDX 二进制解析错误 {stock_code}: {e}")
            return pd.DataFrame()
        except pd.errors.OutOfBoundsDatetime as e:
            logger.warning(f"TDX 日期解析越界 {stock_code}: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.warning(f"TDX 解析失败 {stock_code}: {e}")
            return pd.DataFrame()
