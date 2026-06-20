"""
发现者（Discoverer）— 多策略对比回测路由 (P1-2)

POST /api/compare  — 接收多个 strategy_id + 同一股票 → 并行回测并对比
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from dependencies import get_data_service
from models.db_models import User
from models.schemas import (
    CompareBacktestRequest,
    CompareBacktestResponse,
    CompareStrategyResult,
    CompareStrategySummary,
    InterpretCompareRequest,
    RiskControlParams,
)
from models.signals import CLASSIC_STRATEGIES, get_classic_strategy, build_strategy_from_classic
from routers.auth import get_current_user
from services.backtest_engine import BacktestEngine
from services.llm_service import LLMService

logger = logging.getLogger("discoverer.compare")
router = APIRouter()

_engine: Optional[BacktestEngine] = None
_llm_service: Optional[LLMService] = None


def get_engine() -> BacktestEngine:
    global _engine
    if _engine is None:
        _engine = BacktestEngine(data_service=get_data_service())
    return _engine


def get_llm() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


# ══════════════════════════════════════════════════════════
# POST /api/compare — 多策略对比回测
# ══════════════════════════════════════════════════════════

@router.post("/compare")
async def compare_strategies(
    req: CompareBacktestRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """对同一只股票用多个经典策略执行回测并对比。

    并行调用每个策略的回测，收集结果后返回对比数据，
    可选调用 LLM 生成对比解读。

    Args:
        req: 对比回测请求体

    Returns:
        {code: 0, data: CompareBacktestResponse, message: "success"}
    """
    try:
        # 验证策略数量
        if len(req.strategy_ids) < 2:
            return {"code": -1, "data": None, "message": "至少选择 2 个策略进行对比"}
        if len(req.strategy_ids) > 5:
            return {"code": -1, "data": None, "message": "最多支持 5 个策略同时对比"}

        # 获取数据
        ds = get_data_service()
        df = ds.get_daily_data(req.stock_code, req.start_date, req.end_date)
        if df.empty:
            return {
                "code": -1, "data": None,
                "message": f"未获取到股票 {req.stock_code} 的日线数据",
            }

        # 获取股票名称
        stock_name = ""
        try:
            stock_info = ds._stock_code_index.get(req.stock_code)
            if stock_info:
                stock_name = stock_info.get("name", "")
        except Exception:
            pass

        t0 = time.time()
        engine = get_engine()
        risk_control = req.risk_control or RiskControlParams()

        results: list[CompareStrategyResult] = []

        # 串行执行（经典策略回测很快，无需并行增加复杂度）
        for strategy_id in req.strategy_ids:
            try:
                classic = get_classic_strategy(strategy_id)
                if classic is None:
                    results.append(CompareStrategyResult(
                        strategy_id=strategy_id,
                        strategy_name=strategy_id,
                        error=f"策略 '{strategy_id}' 不存在",
                    ))
                    continue

                strategy = build_strategy_from_classic(strategy_id)
                if strategy is None:
                    results.append(CompareStrategyResult(
                        strategy_id=strategy_id,
                        strategy_name=classic.get("name", strategy_id),
                        error="策略构建失败",
                    ))
                    continue

                # 为每个策略重新传入同一份数据副本
                result = engine.run_backtest(df.copy(), strategy, req.initial_capital, risk_control)
                result_dict = result.model_dump()

                results.append(CompareStrategyResult(
                    strategy_id=strategy_id,
                    strategy_name=classic.get("name", strategy_id),
                    result=result_dict,
                ))

            except Exception as e:
                logger.warning("策略 %s 回测失败: %s", strategy_id, e)
                results.append(CompareStrategyResult(
                    strategy_id=strategy_id,
                    strategy_name=strategy_id,
                    error=f"回测异常: {str(e)}",
                ))

        elapsed_ms = (time.time() - t0) * 1000

        response = CompareBacktestResponse(
            stock_code=req.stock_code,
            stock_name=stock_name,
            results=results,
        )

        logger.info(
            "对比回测完成: stock=%s, strategies=%d, elapsed=%.0fms",
            req.stock_code, len(results), elapsed_ms,
        )

        return {
            "code": 0,
            "data": response.model_dump(),
            "message": "success",
            "elapsed_ms": elapsed_ms,
        }

    except Exception as e:
        logger.error("对比回测失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"对比回测失败: {str(e)}"}


# ══════════════════════════════════════════════════════════
# POST /api/compare/interpret — AI 对比解读
# ══════════════════════════════════════════════════════════

@router.post("/compare/interpret")
async def interpret_compare(req: InterpretCompareRequest):
    """对多策略对比结果生成 AI 解读。

    Args:
        req: AI 对比解读请求

    Returns:
        {code: 0, data: {interpretation: str}, message: "success"}
    """
    try:
        llm = get_llm()

        # 构建摘要文本
        summaries = []
        for s in req.strategies:
            metrics = s.metrics
            summaries.append({
                "strategy_name": s.strategy_name,
                "total_return": metrics.get("total_return", 0),
                "annual_return": metrics.get("annual_return", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
                "win_rate": metrics.get("win_rate", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "profit_loss_ratio": metrics.get("profit_loss_ratio", 0),
                "total_trades": metrics.get("total_trades", 0),
            })

        interpretation = llm.interpret_backtest({
            "stock_code": req.stock_code,
            "stock_name": req.stock_name,
            "strategy_name": "多策略对比",
            "strategies": summaries,
        })

        return {
            "code": 0,
            "data": {
                "interpretation": interpretation.summary if interpretation else "",
            },
            "message": "success",
        }

    except Exception as e:
        logger.error("AI 对比解读失败: %s", e, exc_info=True)
        return {"code": -1, "data": None, "message": f"解读失败: {str(e)}"}
