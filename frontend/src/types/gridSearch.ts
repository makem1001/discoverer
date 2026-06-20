/**
 * 灵犀（Lingxi）— 网格搜索类型定义
 *
 * 与后端 Pydantic schemas.py 一一对应。
 */

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
  heatmap_data: number[][]; // [[xIdx, yIdx, value], ...]
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
