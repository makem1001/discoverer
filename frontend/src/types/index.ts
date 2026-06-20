/**
 * 发现者（Discoverer）— TypeScript 类型定义
 *
 * 与后端 Pydantic 模型一一对应。
 * 日期格式: ISO 8601 "YYYY-MM-DD"
 * 百分比: 小数形式（0.05 = 5%）
 */

// ── 基础类型 ──────────────────────────────────────────

export interface Stock {
  code: string;
  name: string;
  market: string;
  industry: string;
  is_active: boolean;
}

export interface Signal {
  id: string;
  name: string;
  category: string;
  description: string;
  params: Record<string, unknown>;
}

export interface HoldingRule {
  id: string;
  name: string;
  description: string;
  params: Record<string, unknown>;
}

export interface SignalCondition {
  signal_id: string;
  operator: string;
  threshold: number;
}

export interface Strategy {
  id: string;
  name: string;
  raw_text: string;
  entry_conditions: SignalCondition[];
  exit_conditions: SignalCondition[];
  holding_rule: HoldingRule | null;
  params: Record<string, unknown>;
}

export interface RiskControlParams {
  atr_stop_multiplier: number;
  take_profit_pct: number;
  position_sizing: 'full' | 'kelly' | 'half_kelly' | 'fixed_pct';
  fixed_position_pct: number;
  max_position_pct: number;
  max_drawdown_limit: number;
}

// ── 请求类型 ──────────────────────────────────────────

export interface ClassicBacktestRequest {
  stock_code: string;
  strategy_id: string;
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
  risk_control?: RiskControlParams;
}

export interface CustomBacktestRequest {
  stock_code: string;
  natural_language: string;
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
  risk_control?: RiskControlParams;
}

export interface ParseRequest {
  natural_language: string;
  stock_code?: string;
}

export interface BacktestWithStrategyRequest {
  stock_code: string;
  strategy: Strategy;
  start_date?: string;
  end_date?: string;
  initial_capital?: number;
  risk_control?: RiskControlParams;
}

export interface DiscoveryRequest {
  objective: string;
  stock_pool: string[];
  top_n: number;
  use_cache: boolean;
}

export interface CheckupRequest {
  signal_ids: string[];
  stock_pool: string[];
}

// ── 响应类型 ──────────────────────────────────────────

export interface Trade {
  entry_date: string;
  entry_price: number;
  exit_date: string;
  exit_price: number;
  return_pct: number;
  exit_reason: string;
}

export interface EquityPoint {
  date: string;
  equity: number;
  drawdown: number;
}

export interface BacktestMetrics {
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  win_rate: number;
  sharpe_ratio: number;
  profit_loss_ratio: number;
  total_trades: number;
  win_trades: number;
  lose_trades: number;
  avg_hold_days: number;
  dd_breached: boolean;
}

export interface YearlyStat {
  year: number;
  return_pct: number;
  trades: number;
  win_rate: number;
}

export interface BacktestResult {
  id: string;
  stock_code: string;
  stock_name: string;
  strategy: Strategy | null;
  trades: Trade[];
  equity_curve: EquityPoint[];
  metrics: BacktestMetrics;
  yearly_stats: YearlyStat[];
  ai_interpretation: string;
}

export interface ParseResult {
  success: boolean;
  parsed_strategy: Strategy | null;
  explanation: string;
  warnings: string[];
  parse_level: string;
  error_message: string;
}

export interface InterpretResult {
  summary: string;
  risk_analysis: string;
  benchmark_comparison: string;
  suggestion: string;
}

export interface StrategyScore {
  signal: Signal | null;
  score: number;
  win_rate: number;
  annual_return: number;
  max_drawdown: number;
  total_trades: number;
}

export interface DiscoveryResult {
  objective: string;
  rankings: StrategyScore[];
  elapsed_ms: number;
  cache_hit: boolean;
  progress: string;
}

export interface CheckupResult {
  signal_ids: string[];
  total_tests: number;
  triggered: number;
  trigger_rate: number;
  win_rate: number;
  avg_return: number;
  best_return: number;
  worst_return: number;
  yearly_distribution: YearlyStat[];
  ai_report: string;
}

// ── API 响应封装 ──────────────────────────────────────

export interface ApiResponse<T = unknown> {
  code: number;
  data: T;
  message: string;
  elapsed_ms?: number;
}

// ── 经典策略 ──────────────────────────────────────────

export interface ClassicStrategy {
  id: string;
  name: string;
  description: string;
  entry_signal: string;
  exit_signal: string | null;
  holding_rule: string;
}

// ── 系统状态 ──────────────────────────────────────────

export interface SystemStatus {
  signals_loaded: boolean;
  signals_count: number;
  stocks_count: number;
  cached_stocks: number;
  data_range: {
    start: string | null;
    end: string | null;
  };
  initialized: boolean;
}

// ── 回测历史记录 ──────────────────────────────────────

export interface BacktestHistoryItem {
  id: string;
  timestamp: string;
  tab: string;
  stock_code: string;
  stock_name: string;
  strategy_name: string;
  result: BacktestResult;
}

// ── 认证相关 ──────────────────────────────────────────

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  agreed_risk_disclosure: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string; // "bearer"
}

export interface UserInfo {
  id: number;
  email: string;
  created_at: string;
}

// ── 用户设置 ──────────────────────────────────────────

export interface UserSettings {
  tdx_data_dir: string;
}

export interface UserSettingsUpdate {
  tdx_data_dir: string;
}

// ── 策略持久化 ────────────────────────────────────────

export interface SavedStrategy {
  id: number;
  user_id: number;
  name: string;
  description: string;
  raw_text: string;
  entry_conditions: SignalCondition[]; // JSON 解析后
  exit_conditions: SignalCondition[];
  holding_rule: HoldingRule | null;
  params: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StrategyCreateRequest {
  name: string;
  description?: string;
  raw_text?: string;
  entry_conditions?: SignalCondition[];
  exit_conditions?: SignalCondition[];
  holding_rule?: HoldingRule | null;
  params?: Record<string, unknown>;
}

export interface StrategyUpdateRequest {
  name?: string;
  description?: string;
  raw_text?: string;
  entry_conditions?: SignalCondition[];
  exit_conditions?: SignalCondition[];
  holding_rule?: HoldingRule | null;
  params?: Record<string, unknown>;
}

// ── 回测历史（服务端持久化版本）──────────────────────

export interface BacktestHistoryRecord {
  id: number;
  user_id: number;
  strategy_id: number | null;
  stock_code: string;
  stock_name: string;
  start_date: string;
  end_date: string;
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  win_rate: number;
  sharpe_ratio: number;
  profit_loss_ratio: number;
  total_trades: number;
  data_source: string;
  created_at: string;
}

export interface BacktestHistoryDetail extends BacktestHistoryRecord {
  result_data: {
    trades: Trade[];
    equity_curve: EquityPoint[];
  };
}

// ── 数据源状态 ────────────────────────────────────────

export interface DataSourceStatus {
  current_source: string; // "tdx" | "akshare" | "mock" | "parquet_cache"
  tdx_available: boolean;
  tdx_dir: string;
  akshare_available: boolean;
}

// ── P0-Gap: Progress Polling ────────────────────────

export interface ProgressData {
  progress: number;
  status: string;       // "running" | "completed" | "failed"
  result: any | null;
  error: string | null;
}

// ── P1-1: PDF Export ────────────────────────────────

export interface ReportExportRequest {
  backtest_result: any;
  chart_images: Record<string, string>;
  include_ai: boolean;
  include_chart: boolean;
}

export interface ReportExportResponse {
  pdf_base64: string;
  filename: string;
}

// ── P1-2: Multi-Strategy Compare Backtest ───────────

export interface CompareBacktestRequest {
  stock_code: string;
  strategy_ids: string[];
  start_date?: string;
  end_date: string;
  initial_capital?: number;
  risk_control?: RiskControlParams;
}

export interface CompareStrategyResult {
  strategy_id: string;
  strategy_name: string;
  result: any | null;
  error: string | null;
}

export interface CompareBacktestResponse {
  stock_code: string;
  stock_name: string;
  results: CompareStrategyResult[];
}

export interface CompareStrategySummary {
  strategy_name: string;
  metrics: any;
}

export interface InterpretCompareRequest {
  stock_code: string;
  stock_name: string;
  strategies: CompareStrategySummary[];
}

// ── P1-3: Paper Trading ─────────────────────────────

export interface PaperAccountCreate {
  name: string;
  initial_capital?: number;
  strategy_id: string;
  stock_code: string;
}

export interface PaperAccount {
  id: string;
  user_id: number;
  name: string;
  strategy_id: string;
  stock_code: string;
  initial_capital: number;
  current_cash: number;
  total_value: number;
  status: 'running' | 'paused' | 'closed';
  created_at: string;
  updated_at: string;
}

export interface PaperPosition {
  id: string;
  account_id: string;
  stock_code: string;
  shares: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  open_date: string;
}

export interface PaperTrade {
  id: string;
  account_id: string;
  stock_code: string;
  trade_type: 'buy' | 'sell';
  price: number;
  shares: number;
  fee: number;
  pnl: number | null;
  pnl_pct: number | null;
  reason: string;
  traded_at: string;
}

export interface PaperAccountSummary {
  account_id: string;
  total_value: number;
  current_cash: number;
  position_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  position_count: number;
  positions: PaperPosition[];
}

export interface PaperEquityPoint {
  date: string;
  total_value: number;
  cash: number;
  position_value: number;
  cumulative_pnl: number;
  cumulative_pnl_pct: number;
}

export interface PaperTradeListResponse {
  trades: PaperTrade[];
  total: number;
  page: number;
  page_size: number;
}

// ── P2: 网格搜索 (Grid Search) ───────────────────────

export interface ParamRange {
  name: string;
  min_value: number;
  max_value: number;
  step: number;
  label: string;
}

export interface GridSearchRequest {
  stock_code: string;
  strategy_id: string;
  x_param: ParamRange;
  y_param: ParamRange;
  target_metric: string;
  fixed_params: Record<string, number>;
  start_date?: string;
  end_date?: string;
}

export interface GridCell {
  x_value: number;
  y_value: number;
  metrics: Record<string, number>;
  target_value: number;
}

export interface GridSearchResult {
  request: GridSearchRequest;
  cells: GridCell[];
  heatmap_data: number[][];  // [[xIdx, yIdx, targetValue], ...]
  best_cell: GridCell;
  elapsed_seconds: number;
}

export interface GridSearchJob {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  request: GridSearchRequest;
  result?: GridSearchResult;
  error?: string;
}
