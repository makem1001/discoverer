"""
发现者（Discoverer）— 回测路由

POST /api/backtest/classic  — 经典策略回测
POST /api/backtest/custom   — 自定义策略回测（含三级降级解析链）
POST /api/backtest/with-strategy — 直接传入策略回测
POST /api/llm/parse          — NL解析为结构化策略
POST /api/llm/interpret      — AI回测结果解读

P0-4 增强：custom_backtest() 使用三级降级链：
  Level 1: TemplateMatcher.match()    → 模板匹配
  Level 2: LLMService.parse_strategy() → LLM解析
  Level 3: RuleEngine.parse()         → 规则引擎兜底
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request

from dependencies import get_data_service, get_template_matcher, get_rule_engine
from models.schemas import (
    ClassicBacktestRequest, CustomBacktestRequest, BacktestWithStrategyRequest,
    ParseRequest, ParseResult, InterpretRequest, InterpretResult,
    BacktestResult, Strategy, SignalCondition,
)
from models.signals import build_strategy_from_classic, get_classic_strategy
from services.backtest_engine import BacktestEngine
from services.llm_service import LLMService
from services.strategy_templates import build_strategy_from_spec

logger = logging.getLogger("discoverer.backtest")
router = APIRouter()

# 懒加载
_engine = None
_llm_service = None


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


# ── 辅助：从请求中尝试获取用户（不影响公开访问）────────

async def _try_get_user(request: Request):
    """尝试从请求中获取当前用户，失败返回 None（不影响公开访问）。

    仅当请求头携带有效 JWT Bearer token 时返回用户对象。

    Returns:
        User | None
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        from services.auth_service import AuthService
        payload = AuthService.verify_token(token, "access")
        if payload is None:
            return None
        user_id = payload
        if user_id is None:
            return None
        from database import SessionLocal
        from models.db_models import User as DBUser
        db = SessionLocal()
        try:
            user = db.query(DBUser).filter(DBUser.id == int(user_id)).first()
            return user
        finally:
            db.close()
    except Exception:
        return None


def _save_to_history(
    db,
    user,
    strategy_id: int | None,
    stock_code: str,
    stock_name: str,
    start_date: str,
    end_date: str,
    result: BacktestResult,
    data_source: str = "mock",
) -> int:
    """将回测结果保存到 backtest_history 表。

    Args:
        db: 数据库会话
        user: User ORM 对象
        strategy_id: 关联策略 ID（可选）
        stock_code: 股票代码
        stock_name: 股票名称
        start_date: 起始日期
        end_date: 结束日期
        result: 回测结果
        data_source: 数据来源标识

    Returns:
        新创建的 history_id
    """
    from models.db_models import BacktestRecord

    # 提取 trades 和 equity_curve 序列化
    result_data = {
        "trades": [t.model_dump() for t in result.trades],
        "equity_curve": [e.model_dump() for e in result.equity_curve],
    }

    record = BacktestRecord(
        user_id=user.id,
        strategy_id=strategy_id,
        stock_code=stock_code,
        stock_name=stock_name,
        start_date=start_date,
        end_date=end_date,
        total_return=result.metrics.total_return,
        annual_return=result.metrics.annual_return,
        max_drawdown=result.metrics.max_drawdown,
        win_rate=result.metrics.win_rate,
        sharpe_ratio=result.metrics.sharpe_ratio,
        profit_loss_ratio=result.metrics.profit_loss_ratio,
        total_trades=result.metrics.total_trades,
        result_data=json.dumps(result_data, ensure_ascii=False),
        data_source=data_source,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    logger.info(
        f"回测历史已保存: history_id={record.id}, "
        f"user_id={user.id}, stock={stock_code}, "
        f"total_return={result.metrics.total_return:.4f}"
    )
    return record.id


# ── 经典策略回测 ───────────────────────────────────────

@router.post("/backtest/classic")
async def classic_backtest(req: ClassicBacktestRequest, request: Request):
    """
    经典策略回测：选择内置策略 + 股票代码，执行回测并返回结果。

    当请求携带有效 JWT 时，自动将结果保存到回测历史。
    """
    try:
        # 1. 查找经典策略
        classic = get_classic_strategy(req.strategy_id)
        if classic is None:
            return {
                "code": -1, "data": None,
                "message": f"经典策略 '{req.strategy_id}' 不存在",
            }

        # 2. 构建策略
        strategy = build_strategy_from_classic(req.strategy_id)
        if strategy is None:
            return {
                "code": -1, "data": None,
                "message": f"策略构建失败",
            }

        # 3. 获取日线数据
        ds = get_data_service()
        df = ds.get_daily_data(req.stock_code, req.start_date, req.end_date)
        if df.empty:
            return {
                "code": -1, "data": None,
                "message": f"未获取到股票 {req.stock_code} 的日线数据",
            }

        # 4. 执行回测
        t0 = time.time()
        engine = get_engine()
        result = engine.run_backtest(df, strategy, req.initial_capital, req.risk_control)

        # 5. AI解读
        stock_name = ""
        try:
            stock_info = ds._stock_code_index.get(req.stock_code)
            if stock_info:
                stock_name = stock_info.get("name", "")

            interpret_result = get_llm().interpret_backtest({
                "stock_code": req.stock_code,
                "stock_name": stock_name,
                "strategy_name": classic.get("name", req.strategy_id),
                "total_return": result.metrics.total_return,
                "annual_return": result.metrics.annual_return,
                "max_drawdown": result.metrics.max_drawdown,
                "win_rate": result.metrics.win_rate,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "total_trades": result.metrics.total_trades,
                "win_trades": result.metrics.win_trades,
                "lose_trades": result.metrics.lose_trades,
            })
            result.ai_interpretation = interpret_result.summary
        except Exception as e:
            logger.warning(f"AI解读失败: {e}")
            result.ai_interpretation = ""

        elapsed = (time.time() - t0) * 1000

        # 6. 自动保存回测历史（仅当用户已登录）
        history_id = None
        try:
            user = await _try_get_user(request)
            if user is not None:
                from database import SessionLocal
                sess = SessionLocal()
                try:
                    history_id = _save_to_history(
                        sess, user, None,
                        req.stock_code, stock_name,
                        req.start_date, req.end_date,
                        result, "mock",
                    )
                finally:
                    sess.close()
        except Exception as e:
            logger.warning(f"保存回测历史失败（不影响回测）: {e}")

        logger.info(f"经典回测完成: {req.stock_code}/{req.strategy_id}, 耗时 {elapsed:.0f}ms")

        response_data = result.model_dump()
        if history_id is not None:
            response_data["history_id"] = history_id

        return {
            "code": 0,
            "data": response_data,
            "message": "success",
            "elapsed_ms": elapsed,
        }

    except Exception as e:
        logger.error(f"经典回测失败: {e}", exc_info=True)
        return {"code": -1, "data": {"backtest_result": None}, "message": f"回测失败: {str(e)}"}


# ── 自定义策略回测（P0-4 三级降级链）───────────────────

@router.post("/backtest/custom")
async def custom_backtest(req: CustomBacktestRequest, request: Request):
    """
    自定义策略回测：三级降级链解析 → 回测 → AI解读。

    解析链：
      Level 1: TemplateMatcher 模板匹配（最快）
      Level 2: LLMService LLM解析（准确）
      Level 3: RuleEngine 规则引擎（兜底）

    当请求携带有效 JWT 时，自动将结果保存到回测历史。
    """
    try:
        parse_result: ParseResult
        strategy: Strategy
        parse_level: str = "unknown"

        # ═══ Level 1: 模板匹配 ═══
        template_matcher = get_template_matcher()
        template_result = template_matcher.match(req.natural_language)

        if template_result:
            # 命中模板，直接构建策略
            strategy = build_strategy_from_spec(template_result["strategy_spec"])
            strategy.params["stock_code"] = req.stock_code
            strategy.raw_text = req.natural_language
            strategy.name = template_result["strategy_name"]
            parse_result = ParseResult(
                success=True,
                parsed_strategy=strategy,
                explanation=template_result["explanation"],
                warnings=template_result.get("warnings", []),
                parse_level="template",
            )
            parse_level = "template"
            logger.info(f"Level 1 模板命中: {template_result['strategy_name']}")
        else:
            # ═══ Level 2: LLM 解析 ═══
            parse_result = get_llm().parse_strategy(req.natural_language, req.stock_code)

            if not parse_result.success or parse_result.parsed_strategy is None:
                # ═══ Level 3: 规则引擎兜底 ═══
                logger.info("Level 2 LLM解析失败，降级到 Level 3 规则引擎")
                rule_engine = get_rule_engine()
                rule_result = rule_engine.parse(req.natural_language)
                strategy = build_strategy_from_spec(rule_result["strategy_spec"])
                strategy.params["stock_code"] = req.stock_code
                strategy.raw_text = req.natural_language
                strategy.name = "规则引擎策略"

                warnings = rule_result.get("warnings", [])
                warnings.append("由规则引擎解析，可能不够精确")

                parse_result = ParseResult(
                    success=True,
                    parsed_strategy=strategy,
                    explanation=rule_result["explanation"],
                    warnings=warnings,
                    parse_level="rule_engine",
                )
                parse_level = "rule_engine"
            else:
                strategy = parse_result.parsed_strategy
                parse_level = "llm"
                logger.info("Level 2 LLM解析成功")

        # 2. 获取数据
        ds = get_data_service()
        df = ds.get_daily_data(req.stock_code, req.start_date, req.end_date)
        if df.empty:
            return {
                "code": -1, "data": None,
                "message": f"未获取到股票 {req.stock_code} 的日线数据",
            }

        # 3. 执行回测
        t0 = time.time()
        engine = get_engine()
        result = engine.run_backtest(df, strategy, req.initial_capital, req.risk_control)

        # 4. AI解读
        stock_name = ""
        try:
            stock_info = ds._stock_code_index.get(req.stock_code)
            if stock_info:
                stock_name = stock_info.get("name", "")

            interpret_result = get_llm().interpret_backtest({
                "stock_code": req.stock_code,
                "stock_name": stock_name,
                "strategy_name": strategy.name or "自定义策略",
                "total_return": result.metrics.total_return,
                "annual_return": result.metrics.annual_return,
                "max_drawdown": result.metrics.max_drawdown,
                "win_rate": result.metrics.win_rate,
                "sharpe_ratio": result.metrics.sharpe_ratio,
                "total_trades": result.metrics.total_trades,
                "win_trades": result.metrics.win_trades,
                "lose_trades": result.metrics.lose_trades,
            })
            result.ai_interpretation = interpret_result.summary
        except Exception as e:
            logger.warning(f"AI解读失败: {e}")

        elapsed = (time.time() - t0) * 1000

        # 5. 自动保存回测历史（仅当用户已登录）
        history_id = None
        try:
            user = await _try_get_user(request)
            if user is not None:
                from database import SessionLocal
                sess = SessionLocal()
                try:
                    history_id = _save_to_history(
                        sess, user, None,
                        req.stock_code, stock_name,
                        req.start_date, req.end_date,
                        result, "mock",
                    )
                finally:
                    sess.close()
        except Exception as e:
            logger.warning(f"保存回测历史失败（不影响回测）: {e}")

        logger.info(
            f"自定义回测完成: {req.stock_code}, "
            f"parse_level={parse_level}, 耗时 {elapsed:.0f}ms"
        )

        backtest_result_data = result.model_dump()
        if history_id is not None:
            backtest_result_data["history_id"] = history_id

        return {
            "code": 0,
            "data": {
                "backtest_result": backtest_result_data,
                "parse_result": parse_result.model_dump(),
                "parse_level": parse_level,
            },
            "message": "success",
            "elapsed_ms": elapsed,
        }

    except Exception as e:
        logger.error(f"自定义回测失败: {e}", exc_info=True)
        return {
            "code": -1,
            "data": {
                "backtest_result": None,
                "parse_result": None,
                "parse_level": "error",
            },
            "message": f"回测失败: {str(e)}",
        }


# ── 直接传入策略回测 ───────────────────────────────────

@router.post("/backtest/with-strategy")
async def backtest_with_strategy(req: BacktestWithStrategyRequest, request: Request):
    """直接传入已解析好的策略进行回测。

    当请求携带有效 JWT 时，自动将结果保存到回测历史。
    """
    try:
        ds = get_data_service()
        df = ds.get_daily_data(req.stock_code, req.start_date, req.end_date)
        if df.empty:
            return {
                "code": -1, "data": None,
                "message": f"未获取到股票 {req.stock_code} 的日线数据",
            }

        t0 = time.time()
        engine = get_engine()
        result = engine.run_backtest(df, req.strategy, req.initial_capital, req.risk_control)

        # 获取股票名称
        stock_name = ""
        try:
            stock_info = ds._stock_code_index.get(req.stock_code)
            if stock_info:
                stock_name = stock_info.get("name", "")
        except Exception:
            pass

        elapsed = (time.time() - t0) * 1000

        # 自动保存回测历史（仅当用户已登录）
        history_id = None
        try:
            user = await _try_get_user(request)
            if user is not None:
                from database import SessionLocal
                sess = SessionLocal()
                try:
                    history_id = _save_to_history(
                        sess, user, None,
                        req.stock_code, stock_name,
                        req.start_date, req.end_date,
                        result, "mock",
                    )
                finally:
                    sess.close()
        except Exception as e:
            logger.warning(f"保存回测历史失败（不影响回测）: {e}")

        response_data = result.model_dump()
        if history_id is not None:
            response_data["history_id"] = history_id

        return {
            "code": 0,
            "data": response_data,
            "message": "success",
            "elapsed_ms": elapsed,
        }

    except Exception as e:
        logger.error(f"策略回测失败: {e}", exc_info=True)
        return {"code": -1, "data": {"backtest_result": None}, "message": f"回测失败: {str(e)}"}


# ── LLM 解析端点 ──────────────────────────────────────

@router.post("/llm/parse")
async def parse_natural_language(req: ParseRequest):
    """自然语言解析为结构化策略"""
    try:
        result = get_llm().parse_strategy(req.natural_language, req.stock_code)
        return {
            "code": 0 if result.success else -1,
            "data": result.model_dump(),
            "message": "解析成功" if result.success else "解析失败",
        }
    except Exception as e:
        logger.error(f"NL解析失败: {e}", exc_info=True)
        return {"code": -1, "data": {"parse_result": None}, "message": f"解析失败: {str(e)}"}


@router.post("/llm/interpret")
async def interpret_result(req: InterpretRequest):
    """AI回测结果解读"""
    try:
        summary = req.result.model_dump() if req.result else {}
        result = get_llm().interpret_backtest(summary)
        return {
            "code": 0,
            "data": result.model_dump(),
            "message": "success",
        }
    except Exception as e:
        logger.error(f"AI解读失败: {e}", exc_info=True)
        return {"code": -1, "data": {"interpret_result": None}, "message": f"解读失败: {str(e)}"}
