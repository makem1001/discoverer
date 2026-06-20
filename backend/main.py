"""
发现者（Discoverer）— FastAPI 应用入口

启动事件：初始化数据服务
中间件：CORS、日志
路由注册：股票、回测、发现、体检、信号
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from config import DATA_AUTO_REFRESH, PROJECT_ROOT

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("discoverer")

# ── 生命周期管理 ──────────────────────────────────────
from dependencies import get_data_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 生命周期：启动时初始化，关闭时清理"""
    logger.info("🚀 发现者（Discoverer）系统启动中...")

    # 初始化数据库表
    try:
        from database import create_tables
        create_tables()
        logger.info("✅ 数据库表初始化完成")
    except Exception as e:
        logger.warning(f"⚠️ 数据库初始化异常: {e}")

    # 启动时初始化数据服务
    try:
        ds = get_data_service()
        ds.initialize()
        logger.info("✅ 数据服务初始化完成")
    except Exception as e:
        logger.warning(f"⚠️ 数据服务初始化异常（将按需加载）: {e}")

    yield

    logger.info("👋 发现者（Discoverer）系统关闭")


# ── 创建应用 ──────────────────────────────────────────
app = FastAPI(
    title="发现者 (Discoverer) — A股大白话量化回测系统",
    description="零门槛A股量化回测平台，支持自然语言描述策略，全市场秒级回测，AI实时解读",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件（本地开发，放通所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──────────────────────────────────────────
from routers.auth import router as auth_router
from routers.stock import router as stock_router
from routers.backtest import router as backtest_router
from routers.discovery import router as discovery_router
from routers.checkup import router as checkup_router
from routers.strategies import router as strategies_router
from routers.backtest_history import router as backtest_history_router
from routers.settings import router as settings_router
from routers.report import router as report_router
from routers.paper import router as paper_router
from routers.compare import router as compare_router
from routers.grid_search import router as grid_search_router

# ── 公共端点（需在 include_router 之前注册，避免被 {id} 参数路由拦截）──
@app.get("/api/strategies/classic")
async def list_classic_strategies():
    """获取内置经典策略列表"""
    from models.signals import CLASSIC_STRATEGIES
    return {
        "code": 0,
        "data": [s for s in CLASSIC_STRATEGIES],
        "message": "success",
    }

app.include_router(auth_router, prefix="/api", tags=["认证"])
app.include_router(stock_router, prefix="/api", tags=["股票数据"])
app.include_router(backtest_router, prefix="/api", tags=["策略回测"])
app.include_router(discovery_router, prefix="/api", tags=["策略发现"])
app.include_router(checkup_router, prefix="/api", tags=["策略体检"])
app.include_router(strategies_router, prefix="/api", tags=["策略管理"])
app.include_router(backtest_history_router, prefix="/api", tags=["回测历史"])
app.include_router(settings_router, prefix="/api", tags=["用户设置"])
app.include_router(report_router, prefix="/api", tags=["报告导出"])
app.include_router(paper_router, prefix="/api", tags=["模拟交易"])
app.include_router(compare_router, prefix="/api", tags=["策略对比"])
app.include_router(grid_search_router, prefix="/api", tags=["网格搜索"])


# ── 数据查询页面 ──────────────────────────────────────
@app.get("/query", response_class=HTMLResponse)
async def data_query_page():
    """独立的股票价格查询页面"""
    query_html = PROJECT_ROOT / "data_query.html"
    if query_html.exists():
        return query_html.read_text(encoding="utf-8")
    return HTMLResponse("<h1>查询页面未找到</h1>", status_code=404)


# ── 系统状态端点 ──────────────────────────────────────
@app.get("/api/system/status")
async def system_status():
    """返回系统状态：数据加载情况、覆盖范围等"""
    try:
        ds = get_data_service()
        status = ds.get_status()
        return {"code": 0, "data": status, "message": "success"}
    except Exception as e:
        return {
            "code": -1,
            "data": None,
            "message": f"系统状态获取失败: {str(e)}",
        }


# ── 信号定义端点 ──────────────────────────────────────
@app.get("/api/signals")
async def list_signals():
    """获取全部69个信号定义"""
    from models.signals import ALL_SIGNALS, ALL_HOLDING_RULES
    return {
        "code": 0,
        "data": {
            "signals": [s.to_dict() for s in ALL_SIGNALS],
            "holding_rules": [r.to_dict() for r in ALL_HOLDING_RULES],
        },
        "message": "success",
    }


@app.get("/api/signals/{signal_id}")
async def get_signal(signal_id: str):
    """获取单个信号详情"""
    from models.signals import ALL_SIGNALS
    for s in ALL_SIGNALS:
        if s.id == signal_id:
            return {"code": 0, "data": s.to_dict(), "message": "success"}
    return {"code": -1, "data": None, "message": f"信号 '{signal_id}' 不存在"}


@app.get("/api/holding-rules")
async def list_holding_rules():
    """获取全部8个持有规则"""
    from models.signals import ALL_HOLDING_RULES
    return {
        "code": 0,
        "data": [r.to_dict() for r in ALL_HOLDING_RULES],
        "message": "success",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
