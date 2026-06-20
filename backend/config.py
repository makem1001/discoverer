"""
发现者（Discoverer）— 全局配置文件

管理数据路径、LLM密钥、性能参数、回测参数等。
通过环境变量和 .env 文件进行配置。
"""

import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ── 项目路径 ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent  # discoverer/
DATA_DIR = PROJECT_ROOT / "data"
DAILY_DATA_DIR = DATA_DIR / "daily"
SIGNALS_DATA_DIR = DATA_DIR / "signals"
STOCKS_META_FILE = DATA_DIR / "stocks_meta.json"

# 确保必要目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
DAILY_DATA_DIR.mkdir(parents=True, exist_ok=True)
SIGNALS_DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── LLM 配置 ──────────────────────────────────────────
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-your-api-key")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_PARSE_TEMPERATURE = 0.1   # 解析用低温度（确定性）
LLM_INTERPRET_TEMPERATURE = 0.7  # 解读用较高温度（多样性）

# ── 回测参数 ──────────────────────────────────────────
DEFAULT_START_DATE = "2010-01-01"
DEFAULT_END_DATE = os.getenv("DEFAULT_END_DATE", datetime.now().strftime("%Y-%m-%d"))
DEFAULT_INITIAL_CAPITAL = 100_000.0  # 初始资金 10万元
COMMISSION_RATE = 0.00025   # 万2.5 佣金
STAMP_TAX_RATE = 0.001      # 千1 印花税（仅卖出）
SLIPPAGE_RATE = 0.005       # 0.5% 滑点
LIMIT_UP_DOWN_RATE = 0.10   # 涨跌停 10%

# ── 性能参数 ──────────────────────────────────────────
MAX_PARALLEL_WORKERS = min(os.cpu_count() or 4, 8)  # 并行进程数
CACHE_ENABLED = True
DISCOVERY_TOP_N = 20

# ── 数据管理参数 ──────────────────────────────────────
DEFAULT_STOCK_POOL = "hs300"  # 默认股票池：沪深300
DATA_AUTO_REFRESH = False     # 启动时不自动刷新数据
AKSHARE_TIMEOUT = int(os.getenv("AKSHARE_TIMEOUT", "10"))  # akshare 单次请求超时（秒）
AKSHARE_MAX_RETRIES = int(os.getenv("AKSHARE_MAX_RETRIES", "2"))  # 重试次数
AKSHARE_COOLDOWN = int(os.getenv("AKSHARE_COOLDOWN", "60"))  # 连续失败后冷却时间（秒）
STOCKS_META_TTL_HOURS = int(os.getenv("STOCKS_META_TTL_HOURS", "24"))  # 股票列表缓存有效期

# ── 数据库配置 ──────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'discoverer.db'}")

# ── JWT 认证配置 ───────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "discoverer-dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))  # 2小时
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))  # 7天

# ── 通达信配置 ──────────────────────────────────────────
TDX_DEFAULT_DIR = os.getenv("TDX_DATA_DIR", str(PROJECT_ROOT / "data" / "hsjday" / "hsjday"))

# ── P0 新增配置 ────────────────────────────────────────
SIGNAL_CACHE_ENABLED = True
SIGNAL_PRECOMPUTE_TOP_N = 10
DISCOVERY_PROGRESS_POLL_INTERVAL = 500  # ms

# ── P1-3: 模拟交易配置 ────────────────────────────────
PAPER_MAX_ACCOUNTS_PER_USER = 5
PAPER_DEFAULT_CAPITAL = 100_000.0
PAPER_MIN_CAPITAL = 10_000.0
PAPER_MAX_CAPITAL = 10_000_000.0

# ── P1-1: PDF 导出配置 ─────────────────────────────────
PDF_PAGE_SIZE = "A4"
PDF_FONT_SIZE_BODY = 10
