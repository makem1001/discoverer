"""
发现者（Discoverer）— 策略体检路由

POST /api/checkup  — 策略体检：验证信号组合在全市场的有效性
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from dependencies import get_data_service
from models.schemas import CheckupRequest, CheckupResult, YearlyStat
from models.signals import get_signal_by_id
from services.backtest_engine import BacktestEngine
from services.llm_service import LLMService

logger = logging.getLogger("discoverer.checkup")
router = APIRouter()


@router.post("/checkup")
async def strategy_checkup(req: CheckupRequest):
    """
    策略体检：验证信号组合在全市场的有效性。

    将多个信号按 AND 逻辑组合，统计触发概率、胜率、
    平均收益、最好/最差情况等。

    支持 LLM 生成体检报告解读。
    """
    try:
        # 验证信号ID
        valid_signals = []
        signal_names = []
        for sid in req.signal_ids:
            sig = get_signal_by_id(sid)
            if sig:
                valid_signals.append(sid)
                signal_names.append(sig.name)
            else:
                logger.warning(f"未知信号ID: {sid}")

        if not valid_signals:
            return {
                "code": -1, "data": None,
                "message": "没有有效的信号ID",
            }

        ds = get_data_service()

        # 确定股票池
        stock_pool = req.stock_pool if req.stock_pool else ds.get_default_stock_pool()
        if not stock_pool:
            return {
                "code": -1, "data": None,
                "message": "股票池为空",
            }

        logger.info(f"开始策略体检: signals={valid_signals}, stocks={len(stock_pool)}")

        t0 = time.time()

        # 获取价格矩阵
        price_matrix = ds.get_price_matrix(stock_pool)
        if price_matrix.empty:
            return {
                "code": -1, "data": None,
                "message": "无法获取价格数据",
            }

        # 获取信号矩阵
        signal_matrix = ds.get_signal_matrix(stock_pool, valid_signals)

        # 执行体检
        engine = BacktestEngine(data_service=ds)
        checkup_data = engine.checkup(valid_signals, signal_matrix, price_matrix)

        elapsed = (time.time() - t0) * 1000

        # LLM 生成体检报告
        ai_report = ""
        try:
            llm = LLMService()
            ai_report = llm.generate_checkup_report({
                **checkup_data,
                "signal_names": signal_names,
            })
        except Exception as e:
            logger.warning(f"体检报告生成失败: {e}")
            ai_report = "体检报告生成失败，请查看统计数据。\n\n历史表现不代表未来收益，请谨慎参考。"

        result = CheckupResult(
            signal_ids=valid_signals,
            total_tests=checkup_data.get("total_tests", 0),
            triggered=checkup_data.get("triggered", 0),
            trigger_rate=checkup_data.get("trigger_rate", 0.0),
            win_rate=checkup_data.get("win_rate", 0.0),
            avg_return=checkup_data.get("avg_return", 0.0),
            best_return=checkup_data.get("best_return", 0.0),
            worst_return=checkup_data.get("worst_return", 0.0),
            yearly_distribution=[
                YearlyStat(**ys) for ys in checkup_data.get("yearly_distribution", [])
            ],
            ai_report=ai_report,
        )

        logger.info(f"策略体检完成: 耗时 {elapsed:.0f}ms")

        return {
            "code": 0,
            "data": result.model_dump(),
            "message": "success",
            "elapsed_ms": round(elapsed, 1),
        }

    except Exception as e:
        logger.error(f"策略体检失败: {e}", exc_info=True)
        return {"code": -1, "data": None, "message": f"策略体检失败: {str(e)}"}
