"""
发现者（Discoverer）— 数据管理服务

负责：
  1. 股票基础信息管理（搜索、查询）
  2. akshare 日线数据拉取
  3. Parquet 缓存读写
  4. 信号预计算矩阵构建

P0-3 增强：
  - get_signal_matrix() 使用 ProcessPoolExecutor 并行（每信号一个worker）
  - 缓存文件命名 {signal_id}_{pool_hash}.npy + metadata 校验
  - get_price_matrix() 预分配 np.zeros + 直接填充
  - initialize() 后台线程预计算 TOP 10 信号
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict

import pandas as pd
import numpy as np

# 强制 akshare 直连，绕过不可用的系统代理
for _key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    os.environ.pop(_key, None)

from config import (
    DATA_DIR, DAILY_DATA_DIR, SIGNALS_DATA_DIR, STOCKS_META_FILE,
    DEFAULT_STOCK_POOL, DATA_AUTO_REFRESH, DEFAULT_END_DATE,
    SIGNAL_CACHE_ENABLED, SIGNAL_PRECOMPUTE_TOP_N, MAX_PARALLEL_WORKERS,
    AKSHARE_TIMEOUT, AKSHARE_MAX_RETRIES, AKSHARE_COOLDOWN, STOCKS_META_TTL_HOURS,
)

logger = logging.getLogger("discoverer.data")

# ── akshare 健康追踪 ─────────────────────────────────

_akshare_consecutive_failures = 0
_akshare_cooldown_until = 0.0  # Unix timestamp


def _akshare_is_cooling_down() -> bool:
    """检查 akshare 是否处于冷却期"""
    if _akshare_cooldown_until == 0:
        return False
    if time.time() < _akshare_cooldown_until:
        return True
    return False


def _akshare_record_failure() -> None:
    """记录一次 akshare 失败，达到阈值后触发冷却"""
    global _akshare_consecutive_failures, _akshare_cooldown_until
    _akshare_consecutive_failures += 1
    if _akshare_consecutive_failures >= 3:
        _akshare_cooldown_until = time.time() + AKSHARE_COOLDOWN
        logger.warning(f"akshare 连续失败 {_akshare_consecutive_failures} 次，进入冷却 {AKSHARE_COOLDOWN}s")


def _akshare_record_success() -> None:
    """记录一次 akshare 成功，重置失败计数"""
    global _akshare_consecutive_failures, _akshare_cooldown_until
    _akshare_consecutive_failures = 0
    _akshare_cooldown_until = 0


def _akshare_retry(func, *args, max_retries: int = AKSHARE_MAX_RETRIES, **kwargs):
    """带指数退避的 akshare 重试装饰逻辑"""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = func(*args, **kwargs)
            _akshare_record_success()
            return result
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.debug(f"akshare 调用失败 (尝试 {attempt+1}/{max_retries+1}): {e}, {wait}s 后重试")
                time.sleep(wait)
    _akshare_record_failure()
    raise last_error


class DataService:
    """数据管理服务（单例模式，由 main.py 生命周期管理）"""

    def __init__(self, tdx_dir: str = "", skip_precompute: bool = False):
        self._stock_list: List[dict] = []
        self._stock_code_index: Dict[str, dict] = {}
        self._initialized = False
        self._tdx_dir = tdx_dir
        self._skip_precompute = skip_precompute
        self._precompute_done = threading.Event()
        if skip_precompute:
            self._precompute_done.set()  # 标记为已完成（跳过）

    # ── 初始化 ──────────────────────────────────────────

    def initialize(self) -> None:
        """初始化：加载股票元数据，确保数据目录就绪"""
        logger.info("初始化 DataService...")
        self._load_stocks_meta()

        # 如果 stock_list 仍然为空（无缓存 + akshare 不可用），直接使用回退
        if not self._stock_list:
            logger.warning("股票列表为空，使用硬编码回退池")
            self._stock_list = self._get_hs300_fallback()
            self._build_index()

        if DATA_AUTO_REFRESH:
            self._ensure_basic_data()

        self._initialized = True
        logger.info(f"DataService 初始化完成，已加载 {len(self._stock_list)} 只股票")

        # P0-3: 后台线程预计算 TOP N 信号矩阵（仅在主进程中）
        if SIGNAL_CACHE_ENABLED and not self._skip_precompute:
            precompute_thread = threading.Thread(
                target=self._precompute_top_signals,
                daemon=True,
                name="signal-precompute",
            )
            precompute_thread.start()
            logger.info(f"后台预计算线程已启动（TOP {SIGNAL_PRECOMPUTE_TOP_N} 信号）")

    def _precompute_top_signals(self) -> None:
        """后台预计算 TOP N 信号矩阵。

        在后台线程中运行，不阻塞主启动流程。
        """
        try:
            import time
            from models.signals import ALL_SIGNALS

            # 等待初始化完成
            while not self._initialized:
                time.sleep(1)

            stock_pool = self.get_default_stock_pool()
            if not stock_pool:
                logger.warning("预计算：股票池为空，跳过")
                self._precompute_done.set()
                return

            top_signals = [s.id for s in ALL_SIGNALS[:SIGNAL_PRECOMPUTE_TOP_N]]
            logger.info(f"后台预计算开始: {len(top_signals)} 个信号 × {len(stock_pool)} 只股票")

            t0 = time.time()
            self.get_signal_matrix(stock_pool, signal_ids=top_signals, use_cache=True)
            elapsed = time.time() - t0

            logger.info(f"后台预计算完成，耗时 {elapsed:.1f}s")
        except Exception as e:
            logger.warning(f"后台预计算失败（不影响主功能）: {e}")
        finally:
            self._precompute_done.set()

    def wait_precompute(self, timeout: float = 30.0) -> bool:
        """等待预计算完成（用于测试）。

        Returns:
            True 如果预计算在超时前完成
        """
        return self._precompute_done.wait(timeout=timeout)

    def _load_stocks_meta(self) -> None:
        """从缓存加载股票基础信息；无缓存时立即用回退池，后台尝试刷新"""
        if STOCKS_META_FILE.exists():
            try:
                with open(STOCKS_META_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                updated_at = data.get("updated_at", "")
                ttl_hours = data.get("ttl_hours", STOCKS_META_TTL_HOURS)
                if updated_at:
                    age = (datetime.now() - datetime.fromisoformat(updated_at)).total_seconds() / 3600
                    if age < ttl_hours:
                        self._stock_list = data.get("stocks", [])
                        self._build_index()
                        if self._stock_list:
                            logger.info(f"从缓存加载了 {len(self._stock_list)} 只股票元数据 (缓存 {age:.1f}h)")
                            return
                    else:
                        logger.info(f"股票元数据缓存已过期 ({age:.1f}h)，将后台刷新")
            except Exception as e:
                logger.warning(f"股票元数据缓存读取失败: {e}")

        # 无有效缓存：用回退池保证立即可用
        if not self._stock_list:
            self._stock_list = self._get_hs300_fallback()
            self._build_index()
            logger.info(f"使用回退股票池 ({len(self._stock_list)} 只)，后台尝试刷新")

        # 后台线程尝试 akshare 刷新（不阻塞启动）
        if not _akshare_is_cooling_down():
            refresh_thread = threading.Thread(
                target=self._fetch_stocks_from_akshare,
                daemon=True,
                name="stock-refresh",
            )
            refresh_thread.start()

    def _fetch_stocks_from_akshare(self) -> None:
        """从 akshare 获取A股股票列表（后台线程调用，成功后更新 self._stock_list）"""
        if _akshare_is_cooling_down():
            remaining = int(_akshare_cooldown_until - time.time())
            logger.debug(f"akshare 冷却中 (剩余 {remaining}s)，跳过刷新")
            return

        import signal

        class TimeoutError(Exception):
            pass

        def _handler(signum, frame):
            raise TimeoutError(f"akshare 拉取超时 ({AKSHARE_TIMEOUT}s)")

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            import akshare as ak

            def _fetch():
                df = ak.stock_info_a_code_name()
                stocks = []
                for _, row in df.iterrows():
                    code = str(row.get("code", "")).strip()
                    name = str(row.get("name", "")).strip()
                    if not code or not name:
                        continue
                    market = "SH" if code.startswith("6") else "SZ"
                    stocks.append({
                        "code": code, "name": name, "market": market,
                        "industry": "", "is_active": True,
                    })
                return stocks

            stocks = _akshare_retry(_fetch)
            self._stock_list = stocks
            self._build_index()
            STOCKS_META_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STOCKS_META_FILE, "w", encoding="utf-8") as f:
                json.dump({"stocks": stocks, "updated_at": datetime.now().isoformat(),
                           "ttl_hours": STOCKS_META_TTL_HOURS},
                          f, ensure_ascii=False, indent=2)
            logger.info(f"后台刷新成功: 从 akshare 获取了 {len(stocks)} 只股票")
        except TimeoutError:
            logger.warning(f"akshare 股票列表超时 ({AKSHARE_TIMEOUT}s)，保留当前回退池")
            _akshare_record_failure()
        except Exception as e:
            logger.warning(f"后台股票列表刷新失败: {e}")
            _akshare_record_failure()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def _build_index(self) -> None:
        """构建股票代码查找索引"""
        self._stock_code_index = {}
        for s in self._stock_list:
            self._stock_code_index[s["code"]] = s
            # 也支持纯数字索引（去掉SH/SZ前缀）
            if s["code"].isdigit():
                self._stock_code_index[s["code"]] = s

    def _get_hs300_fallback(self) -> List[dict]:
        """回退：使用硬编码的代表股票 + 用户持仓/关注"""
        sample = [
            # 用户持仓与关注
            ("001270", "铖昌科技"), ("300342", "天银机电"), ("000021", "深科技"),
            ("301313", "凡拓数创"), ("300058", "蓝色光标"), ("600487", "亨通光电"),
            ("300308", "中际旭创"), ("600584", "长电科技"),
            # 沪深300代表
            ("000001", "平安银行"), ("000002", "万科A"), ("000858", "五粮液"),
            ("002415", "海康威视"), ("300750", "宁德时代"), ("600000", "浦发银行"),
            ("600009", "上海机场"), ("600016", "民生银行"), ("600028", "中国石化"),
            ("600030", "中信证券"), ("600036", "招商银行"), ("600048", "保利发展"),
            ("600050", "中国联通"), ("600104", "上汽集团"), ("600276", "恒瑞医药"),
            ("600309", "万华化学"), ("600519", "贵州茅台"), ("600585", "海螺水泥"),
            ("600809", "山西汾酒"), ("600887", "伊利股份"), ("601012", "隆基绿能"),
            ("601088", "中国神华"), ("601166", "兴业银行"), ("601288", "农业银行"),
            ("601318", "中国平安"), ("601398", "工商银行"), ("601668", "中国建筑"),
            ("601857", "中国石油"), ("603259", "药明康德"), ("603288", "海天味业"),
        ]
        return [
            {"code": code, "name": name, "market": "SH" if code.startswith("6") else "SZ",
             "industry": "", "is_active": True}
            for code, name in sample
        ]

    # ── 股票搜索 ────────────────────────────────────────

    def search_stocks(self, keyword: str, limit: int = 20) -> List[dict]:
        """搜索股票：支持代码、名称、拼音首字母匹配"""
        if not keyword:
            return self._stock_list[:limit]

        keyword_lower = keyword.lower().strip()
        results = []

        for s in self._stock_list:
            code = s["code"]
            name = s["name"]
            # 代码匹配
            if keyword_lower in code:
                results.append((0, s))
                continue
            # 名称完全匹配
            if keyword_lower == name:
                results.append((1, s))
                continue
            # 名称包含
            if keyword_lower in name:
                results.append((2, s))
                continue
            # 拼音首字母匹配
            try:
                import pypinyin
                pinyin_initials = "".join([x[0] for x in pypinyin.pinyin(name, style=pypinyin.NORMAL)])
                if keyword_lower in pinyin_initials.lower():
                    results.append((3, s))
                    continue
            except ImportError:
                pass

        results.sort(key=lambda x: x[0])
        return [r[1] for r in results[:limit]]

    # ── 日线数据 ────────────────────────────────────────

    def get_daily_data(
        self,
        stock_code: str,
        start_date: str = "2010-01-01",
        end_date: str = DEFAULT_END_DATE,
        tdx_dir: str = "",
    ) -> pd.DataFrame:
        """获取单只股票的日线数据（三级降级链）。

        降级顺序：TDX 本地文件 → Parquet 缓存 → akshare 拉取 → Mock 回退。
        每个数据源在 DataFrame.attrs["_data_source"] 中标记来源。
        """
        # 1. 尝试 TDX 本地文件（最高优先级，绕过缓存）
        effective_tdx = tdx_dir or self._tdx_dir
        if effective_tdx:
            df = self._try_tdx(stock_code, start_date, end_date, effective_tdx)
            if not df.empty:
                df.attrs["_data_source"] = "tdx"
                return df

        parquet_file = DAILY_DATA_DIR / f"{stock_code}.parquet"

        # 2. 尝试 Parquet 缓存
        if parquet_file.exists():
            try:
                df = pd.read_parquet(parquet_file)
                df["date"] = pd.to_datetime(df["date"])
                mask = (df["date"] >= start_date) & (df["date"] <= end_date)
                df = df[mask].copy()
                if not df.empty:
                    df = df.sort_values("date").reset_index(drop=True)
                    df.attrs["_data_source"] = "parquet_cache"
                    return df
            except Exception as e:
                logger.warning(f"缓存读取失败 {stock_code}: {e}")

        # 3. 从 akshare 拉取
        df = self._fetch_daily_from_akshare(stock_code, start_date, end_date)
        if not df.empty:
            df.attrs["_data_source"] = "akshare"

        # 4. 回退到 Mock 数据
        if df.empty:
            logger.warning(f"网络数据不可用，使用 Mock 数据: {stock_code}")
            df = self._generate_mock_daily(stock_code, start_date, end_date)
            df.attrs["_data_source"] = "mock"

        # 缓存到 Parquet（所有数据源都缓存，包括 mock，保证一致性）
        if not df.empty:
            try:
                # 合并已有缓存
                if parquet_file.exists():
                    existing = pd.read_parquet(parquet_file)
                    existing["date"] = pd.to_datetime(existing["date"])
                    combined = pd.concat([existing, df], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["date"]).sort_values("date")
                    combined.to_parquet(parquet_file, index=False)
                else:
                    df.to_parquet(parquet_file, index=False)
            except Exception as e:
                logger.warning(f"缓存写入失败 {stock_code}: {e}")

        return df

    def _try_tdx(
        self,
        stock_code: str,
        start_date: str,
        end_date: str,
        tdx_dir: str,
    ) -> pd.DataFrame:
        """从通达信本地读取数据（延迟导入 TDXReader）。

        Args:
            stock_code: 股票代码。
            start_date: 开始日期。
            end_date: 结束日期。
            tdx_dir: 通达信 vipdoc 目录路径。

        Returns:
            标准化 DataFrame，失败时为空 DataFrame。
        """
        try:
            from services.tdx_reader import TDXReader

            reader = TDXReader(tdx_dir)
            if not reader.is_available():
                logger.debug(f"TDX 目录不可用: {tdx_dir}")
                return pd.DataFrame()

            df = reader.read_daily(stock_code, start_date, end_date)
            if not df.empty:
                logger.info(f"TDX 数据源命中: {stock_code}, {len(df)} 条")
            return df
        except Exception as e:
            logger.warning(f"TDX 读取异常 {stock_code}: {e}")
            return pd.DataFrame()

    def _fetch_daily_from_akshare(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """从 akshare 拉取日线数据并标准化（带超时保护 + 冷却检测）"""
        # 冷却期快速返回
        if _akshare_is_cooling_down():
            logger.debug(f"akshare 冷却中，跳过日线拉取: {stock_code}")
            return pd.DataFrame()

        import signal

        class TimeoutError(Exception):
            pass

        def _handler(signum, frame):
            raise TimeoutError(f"akshare 数据拉取超时 {stock_code}")

        # 设置超时
        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(AKSHARE_TIMEOUT)
        try:
            import akshare as ak

            def _fetch():
                # 确定市场
                symbol = f"sh{stock_code}" if stock_code.startswith("6") else f"sz{stock_code}"

                # 拉取日线（不复权）
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust="",
                )

                if df.empty:
                    return pd.DataFrame()

                # 标准化列名
                df = df.rename(columns={
                    "日期": "date",
                    "开盘": "open",
                    "最高": "high",
                    "最低": "low",
                    "收盘": "close",
                    "成交量": "volume",
                    "成交额": "amount",
                })

                df["date"] = pd.to_datetime(df["date"])
                df["stock_code"] = stock_code
                df["pre_close"] = df["close"].shift(1)

                # 保留需要的列
                cols = ["stock_code", "date", "open", "high", "low", "close", "volume", "amount", "pre_close"]
                df = df[[c for c in cols if c in df.columns]]

                return df.sort_values("date").reset_index(drop=True)

            df = _akshare_retry(_fetch)
            return df

        except TimeoutError as e:
            logger.error(f"获取日线数据超时 {stock_code}: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"获取日线数据失败 {stock_code}: {e}")
            return pd.DataFrame()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    # ── 交易日历辅助 ──────────────────────────────────

    # A 股固定节假日（每年更新一次即可）
    _CN_HOLIDAYS = {
        # 2025
        "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30",
        "2025-01-31", "2025-02-03", "2025-02-04",
        "2025-04-04", "2025-04-07",
        "2025-05-01", "2025-05-02", "2025-05-05",
        "2025-06-02",
        "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-06", "2025-10-07", "2025-10-08",
        # 2024
        "2024-01-01", "2024-02-12", "2024-02-13", "2024-02-14",
        "2024-02-15", "2024-02-16",
        "2024-04-04", "2024-04-05",
        "2024-05-01", "2024-05-02", "2024-05-03",
        "2024-06-10",
        "2024-09-17",
        "2024-10-01", "2024-10-02", "2024-10-03", "2024-10-04", "2024-10-07",
        # 2023
        "2023-01-02", "2023-01-23", "2023-01-24", "2023-01-25",
        "2023-01-26", "2023-01-27",
        "2023-04-05",
        "2023-05-01", "2023-05-02", "2023-05-03",
        "2023-06-22", "2023-06-23",
        "2023-09-29",
        "2023-10-02", "2023-10-03", "2023-10-04", "2023-10-05", "2023-10-06",
        # 2022
        "2022-01-03", "2022-01-31", "2022-02-01", "2022-02-02",
        "2022-02-03", "2022-02-04",
        "2022-04-04", "2022-04-05",
        "2022-05-02", "2022-05-03", "2022-05-04",
        "2022-06-03",
        "2022-09-12",
        "2022-10-03", "2022-10-04", "2022-10-05", "2022-10-06", "2022-10-07",
        # 2021
        "2021-01-01", "2021-02-11", "2021-02-12", "2021-02-15",
        "2021-02-16", "2021-02-17",
        "2021-04-05",
        "2021-05-03", "2021-05-04", "2021-05-05",
        "2021-06-14",
        "2021-09-20", "2021-09-21",
        "2021-10-01", "2021-10-04", "2021-10-05", "2021-10-06", "2021-10-07",
        # 2020
        "2020-01-01", "2020-01-24", "2020-01-27", "2020-01-28",
        "2020-01-29", "2020-01-30", "2020-01-31",
        "2020-04-06",
        "2020-05-01", "2020-05-04", "2020-05-05",
        "2020-06-25", "2020-06-26",
        "2020-10-01", "2020-10-02", "2020-10-05", "2020-10-06", "2020-10-07", "2020-10-08",
    }

    @staticmethod
    def _get_trading_calendar(start: datetime, end: datetime):
        """获取 A 股交易日历（排除周末 + 中国节假日）。

        优先使用 akshare 获取真实交易日历，失败时用 pandas B + 固定节假日回退。
        """
        try:
            import importlib
            if importlib.util.find_spec("akshare") is not None:
                import akshare as ak
                cal_df = ak.tool_trade_date_hist_sina()
                cal_df["trade_date"] = pd.to_datetime(cal_df["trade_date"])
                trade_dates = set(cal_df["trade_date"].dt.strftime("%Y-%m-%d"))
                all_biz = pd.date_range(start, end, freq="B")
                result = [d for d in all_biz if d.strftime("%Y-%m-%d") in trade_dates]
                return pd.DatetimeIndex(result)
        except Exception:
            pass

        # 回退：周末 + 已知节假日
        all_biz = pd.date_range(start, end, freq="B")
        holidays = DataService._CN_HOLIDAYS
        result = [d for d in all_biz if d.strftime("%Y-%m-%d") not in holidays]
        return pd.DatetimeIndex(result)

    def _generate_mock_daily(
        self, stock_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """生成 Mock 日线数据：随机游走 + 真实 A 股交易日历，供演示使用"""
        seed = hash(stock_code) % (2 ** 31)
        rng = np.random.RandomState(seed)
        np.random.seed(seed)

        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        # 使用 A 股真实交易日历而非 pandas "B"（避免含节假日）
        dates = self._get_trading_calendar(start, end)
        if dates is None or len(dates) < 20:
            return pd.DataFrame()
        n = len(dates)

        trend = rng.choice([-1, 1]) * rng.uniform(0.03, 0.15) / 252
        volatility = rng.uniform(0.15, 0.40)
        base_price = rng.uniform(3, 200)

        daily_returns = rng.randn(n) * (volatility / np.sqrt(252)) + trend
        prices = base_price * np.exp(np.cumsum(daily_returns))
        prices = np.maximum(prices, 0.5)

        df = pd.DataFrame()
        df["date"] = dates
        df["close"] = np.round(prices, 2)
        daily_range = np.abs(prices * rng.uniform(0.005, 0.04, n))
        df["open"] = np.round(prices - daily_range * rng.uniform(-0.5, 0.5, n), 2)
        df["high"] = np.round(np.maximum(df["close"], df["open"]) + daily_range * rng.uniform(0, 0.5, n), 2)
        df["low"] = np.round(np.minimum(df["close"], df["open"]) - daily_range * rng.uniform(0, 0.5, n), 2)
        df["low"] = df["low"].clip(lower=0.1)
        df["volume"] = (rng.randint(1000, 500000, n)).astype(np.int64)
        df["amount"] = (df["volume"] * df["close"] * rng.uniform(0.8, 1.2, n)).round(0).astype(np.int64)
        df["stock_code"] = stock_code
        df["pre_close"] = df["close"].shift(1)

        logger.info(f"生成 Mock 数据 {stock_code}: {n} 个交易日, 起始价 {df['close'].iloc[0]:.2f}")
        return df.sort_values("date").reset_index(drop=True)

    def get_multi_stock_data(
        self,
        stock_codes: List[str],
        start_date: str = "2010-01-01",
        end_date: str = DEFAULT_END_DATE,
        tdx_dir: str = "",
    ) -> Dict[str, pd.DataFrame]:
        """批量获取多只股票日线数据"""
        result = {}
        for code in stock_codes:
            df = self.get_daily_data(code, start_date, end_date, tdx_dir=tdx_dir)
            if not df.empty:
                result[code] = df
        return result

    # ── 默认股票池 ──────────────────────────────────────

    def get_stock_pool_by_financials(self, pool_type: str = "high_roe", top_n: int = 50) -> List[str]:
        """基于财务指标筛选股票池。

        Args:
            pool_type: 筛选类型
                - "high_roe": ROE > 15%，按 ROE 降序取 top_n
                - "low_pe": PE > 0 且 PE < 20，按 PE 升序取 top_n
            top_n: 返回前 N 只股票

        Returns:
            股票代码列表
        """
        try:
            import akshare as ak
            import signal

            class TimeoutError(Exception):
                pass

            def _handler(signum, frame):
                raise TimeoutError("akshare 财务数据拉取超时")

            old_handler = signal.signal(signal.SIGALRM, _handler)
            signal.alarm(20)
            try:
                if pool_type == "high_roe":
                    # 获取 ROE 数据：使用 akshare 财务指标接口
                    try:
                        df = ak.stock_financial_analysis_indicator(symbol="000001")
                        # 改用全市场接口
                        df = ak.stock_yjbb_em(date="")  # 最新业绩报表
                        if df is None or df.empty:
                            raise ValueError("业绩报数据为空")
                    except Exception:
                        # 降级：使用 stock_a_lg_indicator 获取最新财务指标
                        df = ak.stock_a_lg_indicator(symbol="000001")
                        logger.warning("使用降级财务数据接口")

                    # 从 stock_yjbb_em 提取 ROE
                    if "roe" in df.columns or "净资产收益率" in df.columns:
                        roe_col = "roe" if "roe" in df.columns else "净资产收益率"
                        code_col = "股票代码" if "股票代码" in df.columns else "code"
                        name_col = "股票简称" if "股票简称" in df.columns else "name"

                        df = df[df[roe_col].astype(float) > 15].copy()
                        df = df.sort_values(roe_col, ascending=False)
                        result = df[code_col].astype(str).str.zfill(6).head(top_n).tolist()
                    else:
                        raise ValueError("ROE 列不存在")

                elif pool_type == "low_pe":
                    # 使用 akshare 实时行情获取 PE
                    df = ak.stock_zh_a_spot_em()
                    if "市盈率-动态" in df.columns:
                        pe_col = "市盈率-动态"
                    elif "pe" in df.columns:
                        pe_col = "pe"
                    else:
                        raise ValueError("PE 列不存在")

                    code_col = "代码" if "代码" in df.columns else "code"
                    name_col = "名称" if "名称" in df.columns else "name"

                    df[pe_col] = pd.to_numeric(df[pe_col], errors="coerce")
                    df = df[(df[pe_col] > 0) & (df[pe_col] < 20)].copy()
                    df = df.sort_values(pe_col, ascending=True)
                    result = df[code_col].astype(str).str.zfill(6).head(top_n).tolist()
                else:
                    logger.warning(f"未知筛选类型: {pool_type}")
                    return []

                logger.info(
                    f"财务筛选完成: {pool_type}, 返回 {len(result)} 只股票"
                )
                return result

            except TimeoutError:
                logger.warning(f"财务数据拉取超时 (20s): {pool_type}")
                return []
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        except ImportError:
            logger.warning("akshare 未安装，使用默认股票池代替财务筛选")
            return [s["code"] for s in self._stock_list[:top_n]]
        except Exception as e:
            logger.error(f"财务筛选失败 ({pool_type}): {e}")
            return [s["code"] for s in self._stock_list[:top_n]]

    def get_default_stock_pool(self, pool_name: str = "hs300") -> List[str]:
        """获取默认股票池的股票代码列表。

        支持:
        - hs300: 沪深300指数成分股（从 data/indices/hs300.json 加载）
        - zz500: 中证500指数成分股（从 data/indices/zz500.json 加载）
        - high_roe: 高ROE筛选（ROE > 15%）
        - low_pe: 低PE筛选（0 < PE < 20）
        - top50: 默认前50只
        """
        if pool_name == "hs300":
            codes = self._load_index_codes("hs300")
            if codes:
                return codes
            # fallback: 返回 self._stock_list 的前300只
            return [s["code"] for s in self._stock_list[:300]]
        elif pool_name == "zz500":
            codes = self._load_index_codes("zz500")
            if codes:
                return codes
            # fallback: 返回 self._stock_list 的 300~800
            return [s["code"] for s in self._stock_list[300:800]]
        elif pool_name == "high_roe":
            return self.get_stock_pool_by_financials("high_roe")
        elif pool_name == "low_pe":
            return self.get_stock_pool_by_financials("low_pe")
        else:
            # top50 或未知类型，返回前50只
            return [s["code"] for s in self._stock_list[:50]]

    def _load_index_codes(self, index_name: str) -> List[str]:
        """从本地 JSON 文件加载指数成分股代码。

        Args:
            index_name: 指数名称 (hs300 或 zz500)

        Returns:
            股票代码列表，文件不存在或解析失败时返回空列表
        """
        index_file = DATA_DIR / "indices" / f"{index_name}.json"
        if not index_file.exists():
            logger.warning(f"指数文件不存在: {index_file}，使用 fallback")
            return []
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            codes = [item["code"] for item in data if isinstance(item, dict) and "code" in item]
            logger.info(f"从 {index_file.name} 加载了 {len(codes)} 只成分股")
            return codes
        except Exception as e:
            logger.warning(f"加载指数文件失败 {index_file}: {e}")
            return []

    # ── 信号预计算矩阵（P0-3 增强：并行 + 缓存 + metadata）──

    @staticmethod
    def _get_pool_hash(stock_codes: List[str]) -> str:
        """计算股票池的 MD5 哈希（前8位）。

        用于缓存文件命名和校验。
        """
        return hashlib.md5(",".join(sorted(stock_codes)).encode()).hexdigest()[:8]

    @staticmethod
    def _get_cache_path(signal_id: str, pool_hash: str) -> str:
        """获取信号缓存文件路径。

        命名格式: {signal_id}_{pool_hash}.npy

        Args:
            signal_id: 信号ID
            pool_hash: 股票池哈希

        Returns:
            缓存文件的完整路径
        """
        return str(SIGNALS_DATA_DIR / f"{signal_id}_{pool_hash}.npy")

    @staticmethod
    def _get_cache_meta_path(cache_path: str) -> str:
        """获取缓存 metadata 文件路径"""
        return cache_path + ".meta.json"

    def _is_cache_valid(
        self,
        cache_path: str,
        stock_codes: List[str],
        pool_hash: str,
    ) -> bool:
        """校验缓存有效性（日期范围 + 股票池哈希匹配）。

        Args:
            cache_path: 缓存 .npy 文件路径
            stock_codes: 当前请求的股票池
            pool_hash: 当前请求的股票池哈希

        Returns:
            True 如果缓存有效可用
        """
        meta_path = self._get_cache_meta_path(cache_path)

        if not os.path.exists(cache_path):
            return False
        if not os.path.exists(meta_path):
            return False

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            # 校验股票池哈希
            cached_hash = meta.get("pool_hash", "")
            if cached_hash != pool_hash:
                return False

            # 校验股票数量
            cached_count = meta.get("stock_count", 0)
            if cached_count != len(stock_codes):
                return False

            return True
        except Exception as e:
            logger.debug(f"缓存元数据读取失败: {e}")
            return False

    def _write_cache_meta(
        self,
        cache_path: str,
        pool_hash: str,
        stock_count: int,
        start_date: str,
        end_date: str,
    ) -> None:
        """写入缓存 metadata 文件。

        Args:
            cache_path: 缓存 .npy 文件路径
            pool_hash: 股票池哈希
            stock_count: 股票数量
            start_date: 起始日期
            end_date: 结束日期
        """
        meta_path = self._get_cache_meta_path(cache_path)
        meta = {
            "pool_hash": pool_hash,
            "stock_count": stock_count,
            "start_date": start_date,
            "end_date": end_date,
            "created_at": datetime.now().isoformat(),
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"缓存元数据写入失败: {e}")

    def get_signal_matrix(
        self,
        stock_codes: List[str],
        signal_ids: Optional[List[str]] = None,
        use_cache: bool = True,
        start_date: str = "2010-01-01",
        end_date: str = DEFAULT_END_DATE,
    ) -> Dict[str, np.ndarray]:
        """获取预计算的信号触发矩阵（P0-3 增强版：并行 + 缓存 + metadata）。

        当信号数量 > 1 时使用 ProcessPoolExecutor 并行计算每个信号。

        Args:
            stock_codes: 股票代码列表
            signal_ids: 信号ID列表（默认全部69个）
            use_cache: 是否使用缓存
            start_date: 起始日期（用于缓存校验）
            end_date: 结束日期（用于缓存校验）

        Returns:
            {signal_id: 2D bool ndarray (n_days × n_stocks)}
        """
        from models.signals import ALL_SIGNALS

        if signal_ids is None:
            signal_ids = [s.id for s in ALL_SIGNALS]

        pool_hash = self._get_pool_hash(stock_codes)
        result: Dict[str, np.ndarray] = {}
        to_compute: List[str] = []

        # 第一遍：检查缓存
        for sid in signal_ids:
            cache_path = self._get_cache_path(sid, pool_hash)

            if use_cache and self._is_cache_valid(cache_path, stock_codes, pool_hash):
                try:
                    matrix = np.load(cache_path)
                    result[sid] = matrix
                    continue
                except Exception as e:
                    logger.debug(f"缓存加载失败 {sid}: {e}")

            # 也检查旧格式缓存（无 pool_hash）
            old_cache_file = SIGNALS_DATA_DIR / f"{sid}.npy"
            if use_cache and old_cache_file.exists():
                try:
                    matrix = np.load(old_cache_file)
                    result[sid] = matrix
                    # 迁移到新格式
                    np.save(cache_path, matrix)
                    self._write_cache_meta(
                        cache_path, pool_hash, len(stock_codes), start_date, end_date
                    )
                    continue
                except Exception as e:
                    logger.debug(f"旧缓存加载失败 {sid}: {e}")

            to_compute.append(sid)

        if not to_compute:
            return result

        # 第二遍：并行计算未缓存的信号
        if len(to_compute) > 1:
            result.update(self._compute_signals_parallel(
                stock_codes, to_compute, pool_hash, start_date, end_date
            ))
        else:
            # 单信号直接计算
            sid = to_compute[0]
            matrix = self._compute_single_signal_matrix(stock_codes, sid)
            result[sid] = matrix
            # 写缓存
            cache_path = self._get_cache_path(sid, pool_hash)
            try:
                np.save(cache_path, matrix)
                self._write_cache_meta(
                    cache_path, pool_hash, len(stock_codes), start_date, end_date
                )
            except Exception as e:
                logger.debug(f"缓存写入失败 {sid}: {e}")

        return result

    def _compute_signals_parallel(
        self,
        stock_codes: List[str],
        signal_ids: List[str],
        pool_hash: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, np.ndarray]:
        """使用 ProcessPoolExecutor 并行计算多个信号矩阵。

        每个信号分配一个独立 worker 进程。

        Args:
            stock_codes: 股票代码列表
            signal_ids: 待计算的信号ID列表
            pool_hash: 股票池哈希
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            {signal_id: 2D bool ndarray}
        """
        from services.signal_service import SignalService

        results: Dict[str, np.ndarray] = {}
        max_workers = min(MAX_PARALLEL_WORKERS, len(signal_ids))

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for sid in signal_ids:
                future = executor.submit(
                    _compute_signal_matrix_worker, stock_codes, sid
                )
                futures[future] = sid

            for future in as_completed(futures):
                sid = futures[future]
                try:
                    matrix = future.result()
                    results[sid] = matrix

                    # 写缓存
                    cache_path = self._get_cache_path(sid, pool_hash)
                    np.save(cache_path, matrix)
                    self._write_cache_meta(
                        cache_path, pool_hash, len(stock_codes), start_date, end_date
                    )
                except Exception as e:
                    logger.error(f"并行计算信号 {sid} 失败: {e}")
                    results[sid] = np.zeros((1, len(stock_codes)), dtype=bool)

        return results

    def _compute_single_signal_matrix(
        self, stock_codes: List[str], signal_id: str
    ) -> np.ndarray:
        """计算单个信号矩阵（供并行调用和单信号调用）。

        Args:
            stock_codes: 股票代码列表
            signal_id: 信号ID

        Returns:
            2D bool ndarray
        """
        from services.signal_service import SignalService

        signal_service = SignalService()
        return signal_service.compute_signal_matrix(stock_codes, signal_id, self)

    # ── 价格矩阵（P0-3 增强：预分配 + 直接填充）───────

    def get_price_matrix(
        self,
        stock_codes: List[str],
        start_date: str = "2010-01-01",
        end_date: str = DEFAULT_END_DATE,
        tdx_dir: str = "",
    ) -> pd.DataFrame:
        """构建价格矩阵（n_days × n_stocks） — 预分配优化版。

        返回: DataFrame，index为日期，columns为股票代码，值为收盘价
        """
        if not stock_codes:
            return pd.DataFrame()

        # 第一遍：加载所有数据并收集日期
        all_dfs: List[pd.DataFrame] = []
        code_map: Dict[int, str] = {}
        col_idx = 0

        for code in stock_codes:
            df = self.get_daily_data(code, start_date, end_date, tdx_dir=tdx_dir)
            if not df.empty:
                df = df.set_index("date")[["close"]].rename(columns={"close": code})
                all_dfs.append(df)
                code_map[col_idx] = code
                col_idx += 1

        if not all_dfs:
            return pd.DataFrame()

        # 收集所有日期
        all_dates = pd.DatetimeIndex([])
        for df in all_dfs:
            all_dates = all_dates.union(df.index)
        all_dates = all_dates.sort_values()

        n_days = len(all_dates)
        n_stocks = len(all_dfs)

        # 预分配 ndarray
        price_arr = np.full((n_days, n_stocks), np.nan, dtype=np.float64)

        # 直接按列填充
        for j, df in enumerate(all_dfs):
            common_dates = all_dates.intersection(df.index)
            for d in common_dates:
                i = all_dates.get_loc(d)
                code = code_map.get(j, "")
                if code in df.columns:
                    price_arr[i, j] = float(df.loc[d, code])

        # 构建 DataFrame
        # 提取有数据的列
        codes_in_order = [code_map.get(j, f"col_{j}") for j in range(n_stocks)]
        price_matrix = pd.DataFrame(
            price_arr,
            index=all_dates,
            columns=codes_in_order,
        )

        return price_matrix.sort_index()

    # ── 系统状态 ────────────────────────────────────────

    def get_status(self) -> dict:
        """获取系统状态信息（含数据源层级状态）"""
        cached_files = list(DAILY_DATA_DIR.glob("*.parquet"))
        date_range = {"start": None, "end": None}

        if cached_files:
            try:
                sample = pd.read_parquet(cached_files[0])
                if "date" in sample.columns:
                    dates = pd.to_datetime(sample["date"])
                    date_range["start"] = dates.min().strftime("%Y-%m-%d")
                    date_range["end"] = dates.max().strftime("%Y-%m-%d")
            except Exception:
                pass

        # 检查 akshare 可用性（按需检测，避免每次调用都 import）
        akshare_available = False
        try:
            import importlib.util
            if importlib.util.find_spec("akshare") is not None:
                akshare_available = True
        except Exception:
            pass

        # 检查 TDX 可用性
        tdx_available = False
        tdx_file_count = 0
        tdx_dir = self._tdx_dir
        if tdx_dir:
            try:
                tdx_path = Path(tdx_dir)
                sh_files = list(tdx_path.glob("sh/lday/*.day")) if (tdx_path / "sh/lday").exists() else []
                sz_files = list(tdx_path.glob("sz/lday/*.day")) if (tdx_path / "sz/lday").exists() else []
                tdx_file_count = len(sh_files) + len(sz_files)
                tdx_available = tdx_file_count > 0
            except Exception:
                pass

        return {
            "signals_loaded": True,
            "signals_count": 69,
            "stocks_count": len(self._stock_list),
            "cached_stocks": len(cached_files),
            "data_range": date_range,
            "initialized": self._initialized,
            "data_source": {
                "tdx_available": tdx_available,
                "tdx_dir": tdx_dir,
                "tdx_file_count": tdx_file_count,
                "akshare_available": akshare_available,
            },
            "precompute_done": self._precompute_done.is_set(),
        }

    def get_status_with_tdx(self, tdx_dir: str = "") -> dict:
        """获取系统状态信息（含 TDX 数据源检测）。

        与 get_status() 的区别：当 tdx_dir 非空时主动探测 TDX 状态。
        """
        status = self.get_status()
        if tdx_dir:
            try:
                from services.tdx_reader import TDXReader

                reader = TDXReader(tdx_dir)
                tdx_status = reader.get_status()
                status["data_source"]["tdx_available"] = tdx_status["available"]
                status["data_source"]["tdx_dir"] = tdx_status["tdx_dir"]
                status["data_source"]["tdx_file_count"] = tdx_status["file_count"]
            except Exception:
                pass
        return status

    def _ensure_basic_data(self) -> None:
        """确保基础数据已缓存（启动时调用）"""
        if not list(DAILY_DATA_DIR.glob("*.parquet")):
            logger.info("未检测到缓存数据，将按需从 akshare 获取")


# ══════════════════════════════════════════════════════════════════
# 模块级辅助函数：供 ProcessPoolExecutor 并行计算使用
# ══════════════════════════════════════════════════════════════════

def _compute_signal_matrix_worker(
    stock_codes: List[str], signal_id: str
) -> np.ndarray:
    """Worker 函数：在独立进程中计算单个信号矩阵。

    必须定义为模块级函数才能被 pickle 序列化（ProcessPoolExecutor 要求）。

    Args:
        stock_codes: 股票代码列表
        signal_id: 信号ID

    Returns:
        2D bool ndarray
    """
    from services.signal_service import SignalService

    signal_service = SignalService()
    # 在子进程中创建独立的 DataService（不共享状态，跳过预计算）
    data_service = DataService(skip_precompute=True)
    data_service.initialize()
    return signal_service.compute_signal_matrix(stock_codes, signal_id, data_service)
