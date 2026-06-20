"""
发现者（Discoverer）— Pydantic 数据模型定义

包含所有 Request/Response Schema，与前端 TypeScript 类型一一对应。
所有日期格式：ISO 8601 字符串 "YYYY-MM-DD"
所有百分比：小数形式（0.05 表示 5%）
"""

from __future__ import annotations

from datetime import date as DateType
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr

from config import DEFAULT_END_DATE


# ══════════════════════════════════════════════════════════════════
# 基础数据模型
# ══════════════════════════════════════════════════════════════════

class Stock(BaseModel):
    """股票基本信息"""
    code: str = Field(..., description="股票代码，6位数字，如 '000001'")
    name: str = Field(..., description="股票名称，如 '平安银行'")
    market: str = Field(default="SZ", description="市场：SH/SZ")
    industry: str = Field(default="", description="所属行业")
    is_active: bool = Field(default=True, description="是否仍在交易")


class DailyBar(BaseModel):
    """日线行情数据"""
    stock_code: str
    date: str  # "YYYY-MM-DD"
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    pre_close: float = 0.0


class Signal(BaseModel):
    """信号定义"""
    id: str = Field(..., description="信号唯一标识，如 'ma_golden_cross'")
    name: str = Field(..., description="信号中文名，如 '均线金叉'")
    category: str = Field(..., description="信号分类：趋势/动量/反转/量价/波动")
    description: str = Field(default="", description="信号详细说明")
    params: Dict[str, Any] = Field(default_factory=dict, description="信号参数")

    def to_dict(self) -> dict:
        return self.model_dump()


class HoldingRule(BaseModel):
    """持有规则定义"""
    id: str = Field(..., description="规则唯一标识")
    name: str = Field(..., description="规则中文名")
    description: str = Field(default="")
    params: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict:
        return self.model_dump()


class RiskControlParams(BaseModel):
    """风控参数"""
    atr_stop_multiplier: float = 0.0
    take_profit_pct: float = 0.0
    position_sizing: str = "full"  # full / kelly / half_kelly / fixed_pct
    fixed_position_pct: float = 0.3
    max_position_pct: float = 0.5
    max_drawdown_limit: float = 0.0


class SignalCondition(BaseModel):
    """信号条件（信号ID + 运算符 + 阈值）"""
    signal_id: str = Field(..., description="信号ID")
    operator: str = Field(default="cross_above", description="运算符：cross_above/cross_below/gt/lt/eq")
    threshold: float = Field(default=0.0, description="阈值（用于 gt/lt 比较）")


class Strategy(BaseModel):
    """完整策略定义"""
    id: str = Field(default="", description="策略唯一标识")
    name: str = Field(default="", description="策略名称")
    raw_text: str = Field(default="", description="用户原始白话描述")
    entry_conditions: List[SignalCondition] = Field(default_factory=list, description="买入条件列表")
    exit_conditions: List[SignalCondition] = Field(default_factory=list, description="卖出条件列表")
    holding_rule: Optional[HoldingRule] = Field(default=None, description="持有规则")
    params: Dict[str, Any] = Field(default_factory=dict, description="额外参数")


# ══════════════════════════════════════════════════════════════════
# 请求模型
# ══════════════════════════════════════════════════════════════════

class ClassicBacktestRequest(BaseModel):
    """经典策略回测请求"""
    stock_code: str = Field(..., description="股票代码")
    strategy_id: str = Field(..., description="经典策略ID")
    start_date: str = Field(default="2010-01-01", description="回测起始日期")
    end_date: str = Field(default=DEFAULT_END_DATE, description="回测结束日期")
    initial_capital: float = Field(default=100_000.0, description="初始资金")
    risk_control: Optional[RiskControlParams] = None


class CustomBacktestRequest(BaseModel):
    """自定义策略回测请求"""
    stock_code: str = Field(..., description="股票代码")
    natural_language: str = Field(..., description="自然语言策略描述")
    start_date: str = Field(default="2010-01-01")
    end_date: str = Field(default=DEFAULT_END_DATE)
    initial_capital: float = Field(default=100_000.0)
    risk_control: Optional[RiskControlParams] = None


class BacktestWithStrategyRequest(BaseModel):
    """直接传入解析好的策略进行回测"""
    stock_code: str
    strategy: Strategy
    start_date: str = Field(default="2010-01-01")
    end_date: str = Field(default=DEFAULT_END_DATE)
    initial_capital: float = Field(default=100_000.0)
    risk_control: Optional[RiskControlParams] = None


class ParseRequest(BaseModel):
    """自然语言解析请求"""
    natural_language: str = Field(..., description="用户的白话策略描述")
    stock_code: str = Field(default="", description="关联股票代码（可选）")


class DiscoveryRequest(BaseModel):
    """策略发现请求"""
    objective: str = Field(default="max_win_rate", description="优化目标：max_win_rate/min_drawdown/max_sharpe/max_profit_loss_ratio")
    stock_pool: List[str] = Field(default_factory=list, description="股票池代码列表")
    top_n: int = Field(default=20, description="返回 Top-N 结果")
    use_cache: bool = True


class CheckupRequest(BaseModel):
    """策略体检请求"""
    signal_ids: List[str] = Field(..., description="待验证的信号ID列表")
    stock_pool: List[str] = Field(default_factory=list, description="股票池代码列表")


class InterpretRequest(BaseModel):
    """AI解读请求"""

    class BacktestResultSummary(BaseModel):
        """回测结果摘要（传给LLM）"""
        stock_code: str = ""
        stock_name: str = ""
        strategy_name: str = ""
        total_return: float = 0.0
        annual_return: float = 0.0
        max_drawdown: float = 0.0
        win_rate: float = 0.0
        sharpe_ratio: float = 0.0
        total_trades: int = 0
        win_trades: int = 0
        lose_trades: int = 0

    result: BacktestResultSummary = Field(..., description="回测结果摘要")


# ══════════════════════════════════════════════════════════════════
# 响应模型
# ══════════════════════════════════════════════════════════════════

class Trade(BaseModel):
    """单笔交易记录"""
    entry_date: str = ""  # "YYYY-MM-DD"
    entry_price: float = 0.0
    exit_date: str = ""
    exit_price: float = 0.0
    return_pct: float = 0.0  # 小数形式
    exit_reason: str = ""


class EquityPoint(BaseModel):
    """资金曲线上的一个点"""
    date: str = ""  # "YYYY-MM-DD"
    equity: float = 0.0
    drawdown: float = 0.0  # 小数形式


class BacktestMetrics(BaseModel):
    """回测核心指标"""
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    profit_loss_ratio: float = 0.0
    total_trades: int = 0
    win_trades: int = 0
    lose_trades: int = 0
    avg_hold_days: float = 0.0
    dd_breached: bool = False


class YearlyStat(BaseModel):
    """逐年统计"""
    year: int = 0
    return_pct: float = 0.0
    trades: int = 0
    win_rate: float = 0.0


class BacktestResult(BaseModel):
    """回测完整结果"""
    id: str = ""
    stock_code: str = ""
    stock_name: str = ""
    strategy: Optional[Strategy] = None
    trades: List[Trade] = Field(default_factory=list)
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    metrics: BacktestMetrics = Field(default_factory=BacktestMetrics)
    yearly_stats: List[YearlyStat] = Field(default_factory=list)
    ai_interpretation: str = ""


class ParseResult(BaseModel):
    """自然语言解析结果"""
    success: bool = False
    parsed_strategy: Optional[Strategy] = None
    explanation: str = ""
    warnings: List[str] = Field(default_factory=list)
    parse_level: str = "llm"
    error_message: str = ""


class InterpretResult(BaseModel):
    """AI回测解读结果"""
    summary: str = ""
    risk_analysis: str = ""
    benchmark_comparison: str = ""
    suggestion: str = ""


class StrategyScore(BaseModel):
    """策略发现中的单个策略得分"""
    signal: Optional[Signal] = None
    score: float = 0.0
    win_rate: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0


class DiscoveryResult(BaseModel):
    """策略发现结果"""
    objective: str = ""
    rankings: List[StrategyScore] = Field(default_factory=list)
    elapsed_ms: float = 0.0
    cache_hit: bool = False
    progress: str = ""


class CheckupResult(BaseModel):
    """策略体检结果"""
    signal_ids: List[str] = Field(default_factory=list)
    total_tests: int = 0
    triggered: int = 0
    trigger_rate: float = 0.0
    win_rate: float = 0.0
    avg_return: float = 0.0
    best_return: float = 0.0
    worst_return: float = 0.0
    yearly_distribution: List[YearlyStat] = Field(default_factory=list)
    ai_report: str = ""


class ApiResponse(BaseModel):
    """统一API响应封装"""
    code: int = 0
    data: Any = None
    message: str = "success"


# ══════════════════════════════════════════════════════════════════
# 认证相关模型
# ══════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="注册邮箱")
    password: str = Field(..., min_length=6, description="密码（至少6位）")
    agreed_risk_disclosure: bool = False


class LoginRequest(BaseModel):
    email: str = Field(..., description="登录邮箱")
    password: str = Field(..., description="登录密码")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="refresh token")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    created_at: Optional[str] = None  # ISO 8601 string


# ══════════════════════════════════════════════════════════════════
# 策略持久化模型
# ══════════════════════════════════════════════════════════════════

class StrategyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="策略名称")
    description: str = Field(default="", description="策略描述")
    raw_text: str = Field(default="", description="用户原始自然语言描述")
    entry_conditions: List[SignalCondition] = Field(default_factory=list)
    exit_conditions: List[SignalCondition] = Field(default_factory=list)
    holding_rule: Optional[HoldingRule] = Field(default=None)
    params: Dict[str, Any] = Field(default_factory=dict)


class StrategyUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    raw_text: Optional[str] = None
    entry_conditions: Optional[List[SignalCondition]] = None
    exit_conditions: Optional[List[SignalCondition]] = None
    holding_rule: Optional[HoldingRule] = None
    params: Optional[Dict[str, Any]] = None


class StrategyResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: str
    raw_text: str
    entry_conditions: List[SignalCondition] = Field(default_factory=list)
    exit_conditions: List[SignalCondition] = Field(default_factory=list)
    holding_rule: Optional[HoldingRule] = None
    params: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ══════════════════════════════════════════════════════════════════
# 用户设置模型
# ══════════════════════════════════════════════════════════════════

class SettingsResponse(BaseModel):
    tdx_data_dir: str = ""


class SettingsUpdateRequest(BaseModel):
    tdx_data_dir: str = Field(default="", description="通达信数据目录路径")


# ══════════════════════════════════════════════════════════════════
# 回测历史模型
# ══════════════════════════════════════════════════════════════════

class BacktestHistoryItem(BaseModel):
    id: int
    user_id: int
    strategy_id: Optional[int] = None
    stock_code: str
    stock_name: str = ""
    start_date: str
    end_date: str
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    profit_loss_ratio: float = 0.0
    total_trades: int = 0
    data_source: str = "mock"
    created_at: Optional[str] = None


class BacktestHistoryDetail(BaseModel):
    """包含完整回测结果的详情"""
    id: int
    user_id: int
    strategy_id: Optional[int] = None
    stock_code: str
    stock_name: str = ""
    start_date: str
    end_date: str
    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    profit_loss_ratio: float = 0.0
    total_trades: int = 0
    data_source: str = "mock"
    result_data: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None


# ============================================================
# P1-1: PDF 导出
# ============================================================

class ReportExportRequest(BaseModel):
    """PDF 报告导出请求。"""

    backtest_result: dict  # BacktestResult 完整字典
    chart_images: dict[str, str] = {}  # {"equity_curve": "data:image/png;base64,..."}
    include_ai: bool = True
    include_chart: bool = True


class ReportExportResponse(BaseModel):
    """PDF 报告导出响应。"""

    pdf_base64: str
    filename: str


# ============================================================
# P1-2: 多策略对比回测
# ============================================================

class CompareBacktestRequest(BaseModel):
    """多策略对比回测请求。"""

    stock_code: str
    strategy_ids: list[str]  # 最少2个，最多5个
    start_date: str = "2010-01-01"
    end_date: str  # 必填，前端传
    initial_capital: float = 100000.0
    risk_control: Optional[RiskControlParams] = None


class CompareStrategyResult(BaseModel):
    """单个策略的对比回测结果。"""

    strategy_id: str
    strategy_name: str
    result: Optional[dict] = None  # BacktestResult dict
    error: Optional[str] = None


class CompareBacktestResponse(BaseModel):
    """多策略对比回测响应。"""

    stock_code: str
    stock_name: str
    results: list[CompareStrategyResult]


class CompareStrategySummary(BaseModel):
    """对比策略摘要（发给 AI 解读时使用）。"""

    strategy_name: str
    metrics: dict  # BacktestMetrics dict


class InterpretCompareRequest(BaseModel):
    """AI 对比解读请求。"""

    stock_code: str
    stock_name: str
    strategies: list[CompareStrategySummary]


# ============================================================
# P1-3: 模拟交易
# ============================================================

class PaperAccountCreate(BaseModel):
    """创建模拟账户请求。"""

    name: str = Field(..., min_length=1, max_length=100)
    initial_capital: float = Field(default=100000.0, ge=10000.0, le=10000000.0)
    strategy_id: str
    stock_code: str


class PaperAccountOut(BaseModel):
    """模拟账户输出。"""

    id: str
    user_id: int
    name: str
    strategy_id: str
    stock_code: str
    initial_capital: float
    current_cash: float
    total_value: float
    status: str  # "running" | "paused" | "closed"
    created_at: str
    updated_at: str


class PaperPositionOut(BaseModel):
    """模拟持仓输出。"""

    id: str
    account_id: str
    stock_code: str
    shares: int
    avg_cost: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    open_date: str


class PaperTradeOut(BaseModel):
    """模拟交易记录输出。"""

    id: str
    account_id: str
    stock_code: str
    trade_type: str  # "buy" | "sell"
    price: float
    shares: int
    fee: float
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    reason: str
    traded_at: str


class PaperAccountSummary(BaseModel):
    """模拟账户摘要（含持仓列表）。"""

    account_id: str
    total_value: float
    current_cash: float
    position_value: float
    total_pnl: float
    total_pnl_pct: float
    position_count: int
    positions: list[PaperPositionOut]


class PaperEquityPoint(BaseModel):
    """模拟交易权益曲线数据点。"""

    date: str
    total_value: float
    cash: float
    position_value: float
    cumulative_pnl: float
    cumulative_pnl_pct: float


class PaperTradeListResponse(BaseModel):
    """模拟交易记录分页响应。"""

    trades: list[PaperTradeOut]
    total: int
    page: int
    page_size: int


# ============================================================
# 网格搜索（Grid Search）模型
# ============================================================

class ParamRange(BaseModel):
    """单个参数的搜索范围定义"""

    name: str = Field(..., description="参数名，如 stop_loss_pct / hold_days / atr_stop_multiplier")
    min_value: float = Field(..., description="最小值")
    max_value: float = Field(..., description="最大值")
    step: float = Field(..., description="步长")
    label: str = Field(default="", description="中文显示名，如 止损比例")


class GridSearchRequest(BaseModel):
    """网格搜索请求"""

    stock_code: str = Field(..., description="股票代码")
    start_date: Optional[str] = Field(default=None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="结束日期 YYYY-MM-DD")
    strategy_id: str = Field(..., description="基础策略ID，如 macd_golden_death")
    x_param: ParamRange = Field(..., description="X 轴参数（热力图列）")
    y_param: ParamRange = Field(..., description="Y 轴参数（热力图行）")
    target_metric: str = Field(default="total_return", description="优化目标指标")
    initial_capital: float = Field(default=100_000.0, description="初始资金")
    fixed_params: Dict[str, Any] = Field(default_factory=dict, description="固定参数（不参与搜索），如 {'hold_days': 5}")


class GridCell(BaseModel):
    """单个网格单元的回测结果"""

    x_value: float = Field(..., description="X 轴参数值")
    y_value: float = Field(..., description="Y 轴参数值")
    x_label: str = Field(default="", description="X 轴显示标签")
    y_label: str = Field(default="", description="Y 轴显示标签")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="回测指标快照，如 {'total_return': 0.15, 'sharpe': 1.2}")
    target_value: float = Field(default=0.0, description="目标指标的值")


class GridSearchResult(BaseModel):
    """网格搜索完整结果"""

    x_param: ParamRange = Field(..., description="X 参数定义（回传）")
    y_param: ParamRange = Field(..., description="Y 参数定义（回传）")
    target_metric: str = Field(default="total_return", description="优化目标")
    cells: List[GridCell] = Field(default_factory=list, description="所有网格单元")
    x_labels: List[str] = Field(default_factory=list, description="X 轴标签列表（去重排序）")
    y_labels: List[str] = Field(default_factory=list, description="Y 轴标签列表（去重排序）")
    heatmap_data: List[List] = Field(
        default_factory=list,
        description="[[xIdx, yIdx, targetValue], ...] 供前端 ECharts 直接使用",
    )
    best_cell: Optional[GridCell] = Field(default=None, description="最优参数组合")
    total_combinations: int = Field(default=0, description="总参数组合数")
    elapsed_seconds: float = Field(default=0.0, description="耗时（秒）")


class GridSearchJob(BaseModel):
    """异步网格搜索任务状态"""

    job_id: str = Field(..., description="任务 ID（UUID 前8位）")
    status: str = Field(default="pending", description="pending | running | completed | failed")
    progress: float = Field(default=0.0, description="进度 0.0 ~ 1.0")
    total: int = Field(default=0, description="总任务数")
    completed: int = Field(default=0, description="已完成数")
    request: Optional[GridSearchRequest] = Field(default=None, description="原始请求")
    result: Optional[GridSearchResult] = Field(default=None, description="搜索结果")
    error: Optional[str] = Field(default=None, description="错误信息")
    created_at: str = Field(default="", description="创建时间 ISO 8601")
