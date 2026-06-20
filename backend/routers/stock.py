"""
发现者（Discoverer）— 股票数据路由

GET  /api/stocks/search?q={keyword}  — 股票搜索
GET  /api/stocks/{code}              — 股票详情
"""

import logging
from fastapi import APIRouter, Query, HTTPException

from dependencies import get_data_service

logger = logging.getLogger("discoverer.stock")
router = APIRouter()


@router.get("/stock-pools")
async def list_stock_pools():
    """返回可用股票池列表"""
    try:
        ds = get_data_service()
        pools = [
            {"id": "hs300", "name": "沪深300", "count": len(ds.get_default_stock_pool("hs300")), "description": "沪深300指数成分股"},
            {"id": "zz500", "name": "中证500", "count": len(ds.get_default_stock_pool("zz500")), "description": "中证500指数成分股"},
            {"id": "top50", "name": "Top 50", "count": len(ds.get_default_stock_pool("top50")), "description": "默认前50只股票"},
            {"id": "high_roe", "name": "高ROE", "count": len(ds.get_default_stock_pool("high_roe")), "description": "ROE > 15% 精选"},
            {"id": "low_pe", "name": "低PE", "count": len(ds.get_default_stock_pool("low_pe")), "description": "PE < 20 精选"},
        ]
        return {"code": 0, "data": pools, "message": "success"}
    except Exception as e:
        logger.error(f"获取股票池列表失败: {e}")
        return {"code": -1, "data": None, "message": f"获取失败: {str(e)}"}


@router.get("/stocks/search")
async def search_stocks(q: str = Query(default="", description="搜索关键词：代码/名称/拼音"), limit: int = Query(default=20, le=50)):
    """搜索股票：支持代码、名称、拼音首字母"""
    try:
        ds = get_data_service()
        results = ds.search_stocks(q, limit=limit)
        return {
            "code": 0,
            "data": results,
            "message": "success",
        }
    except Exception as e:
        logger.error(f"股票搜索失败: {e}")
        return {"code": -1, "data": None, "message": f"搜索失败: {str(e)}"}


@router.get("/stocks/{code}")
async def get_stock_detail(code: str):
    """获取单只股票详细信息"""
    try:
        ds = get_data_service()
        # 尝试通过代码直接查找
        stock = ds._stock_code_index.get(code)
        if stock:
            return {"code": 0, "data": stock, "message": "success"}
        else:
            # 尝试搜索
            results = ds.search_stocks(code, limit=1)
            if results:
                return {"code": 0, "data": results[0], "message": "success"}
            return {"code": -1, "data": None, "message": f"未找到股票: {code}"}
    except Exception as e:
        logger.error(f"获取股票详情失败: {e}")
        return {"code": -1, "data": None, "message": f"获取失败: {str(e)}"}


@router.get("/stocks/{code}/prices")
async def get_stock_prices(
    code: str,
    start: str = Query(default="2025-01-01", description="起始日期 YYYY-MM-DD"),
    end: str = Query(default="2025-06-30", description="结束日期 YYYY-MM-DD"),
):
    """获取股票日线价格数据，返回 OHLCV 数组"""
    try:
        ds = get_data_service()
        df = ds.get_daily_data(code, start, end)
        if df.empty:
            return {"code": -1, "data": None, "message": f"无数据: {code} ({start}~{end})"}
        
        source = df.attrs.get("_data_source", "unknown")
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row["date"])[:10],
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "volume": int(row["volume"]),
                "amount": int(row["amount"]),
            })
        
        return {
            "code": 0,
            "data": {
                "code": code,
                "source": source,
                "count": len(records),
                "records": records,
            },
            "message": "success",
        }
    except Exception as e:
        logger.error(f"获取价格数据失败: {e}")
        return {"code": -1, "data": None, "message": f"获取失败: {str(e)}"}
