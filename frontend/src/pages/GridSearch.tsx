/**
 * 发现者（Discoverer）— 参数网格搜索页面
 *
 * 双参数穷举式搜索 + 热力图可视化 + 结果表格展示。
 * SplitPane 布局：左栏参数配置，右栏热力图+表格。
 *
 * 数据流：
 *   用户配置参数 → POST /api/backtest/grid-search → job_id
 *   → setInterval 轮询 GET /api/backtest/grid-search/{job_id}
 *   → completed → 渲染热力图 + 结果表
 */

import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Box, Paper, Typography, LinearProgress, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, Alert, Chip,
} from '@mui/material';
import SplitPane from '../components/Layout/SplitPane';
import StockSearch from '../components/Common/StockSearch';
import StrategySelector from '../components/Common/StrategySelector';
import ParamGridConfig from '../components/GridSearch/ParamGridConfig';
import type { GridSearchConfig } from '../components/GridSearch/ParamGridConfig';
import ParamHeatmap from '../components/Charts/ParamHeatmap';
import { useApi } from '../hooks/useApi';
import type {
  Stock, GridSearchRequest, GridSearchJob, GridSearchResult,
} from '../types';

/* ------------------------------------------------------------------ */
/*  常量                                                               */
/* ------------------------------------------------------------------ */

const POLL_INTERVAL_MS = 1500;
const TIMEOUT_MS = 60_000;

/** 结果表列定义 */
const METRIC_COLUMNS = [
  { key: 'annual_return', label: '年化收益' },
  { key: 'max_drawdown', label: '最大回撤' },
  { key: 'win_rate', label: '胜率' },
  { key: 'sharpe_ratio', label: '夏普比率' },
  { key: 'total_return', label: '总收益' },
  { key: 'target_value', label: '目标值' },
] as const;

const METRIC_FORMAT: Record<string, (v: number) => string> = {
  annual_return: (v) => `${(v * 100).toFixed(2)}%`,
  max_drawdown: (v) => `${(v * 100).toFixed(2)}%`,
  win_rate: (v) => `${(v * 100).toFixed(1)}%`,
  sharpe_ratio: (v) => v.toFixed(2),
  total_return: (v) => `${(v * 100).toFixed(2)}%`,
  target_value: (v) => `${(v * 100).toFixed(2)}%`,
};

/** 将 GridSearchConfig 转换为后端 GridSearchRequest */
function mapConfigToRequest(
  config: GridSearchConfig,
  stockCode: string,
  strategyId: string,
): GridSearchRequest {
  return {
    stock_code: stockCode,
    strategy_id: strategyId,
    x_param: {
      name: config.xParam.name,
      min_value: config.xParam.min,
      max_value: config.xParam.max,
      step: config.xParam.step,
      label: config.xParam.label,
    },
    y_param: {
      name: config.yParam.name,
      min_value: config.yParam.min,
      max_value: config.yParam.max,
      step: config.yParam.step,
      label: config.yParam.label,
    },
    target_metric: config.targetMetric,
    fixed_params: config.fixedParams,
  };
}

/* ------------------------------------------------------------------ */
/*  组件                                                               */
/* ------------------------------------------------------------------ */

const GridSearch: React.FC = () => {
  /* ---- 输入状态 ---- */
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [strategyId, setStrategyId] = useState('macd_golden_death');

  /* ---- 搜索状态 ---- */
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<GridSearchJob | null>(null);
  const [result, setResult] = useState<GridSearchResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);

  /* ---- 交互状态 ---- */
  const [highlightedCell, setHighlightedCell] = useState<{ x: number; y: number } | null>(null);

  const { post, get } = useApi();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef(0);
  const tableContainerRef = useRef<HTMLDivElement>(null);

  /* ---- 生命周期：清理 interval ---- */
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  /* ---- 清除轮询 ---- */
  const clearPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  /* ---- 重置 ---- */
  const handleReset = useCallback(() => {
    clearPolling();
    setJobId(null);
    setJob(null);
    setResult(null);
    setProgress(0);
    setIsSearching(false);
    setPageError(null);
    setHighlightedCell(null);
  }, [clearPolling]);

  /* ---- 发起网格搜索 + 轮询 ---- */
  const handleSearch = useCallback(async (config: GridSearchConfig) => {
    if (!selectedStock) {
      setPageError('请先选择一只股票');
      return;
    }

    handleReset();
    setIsSearching(true);

    const request = mapConfigToRequest(config, selectedStock.code, strategyId);

    try {
      const postRes = await post<{ job_id: string }>('/backtest/grid-search', request);

      if (postRes.code !== 0 || !postRes.data?.job_id) {
        setPageError(postRes.message || '启动网格搜索失败');
        setIsSearching(false);
        return;
      }

      const jid = postRes.data.job_id;
      setJobId(jid);
      startTimeRef.current = Date.now();

      intervalRef.current = setInterval(async () => {
        try {
          const elapsed = Date.now() - startTimeRef.current;

          if (elapsed > TIMEOUT_MS) {
            clearPolling();
            setIsSearching(false);
            setPageError('网格搜索超时（60秒），请重试');
            return;
          }

          const getRes = await get<GridSearchJob>(`/backtest/grid-search/${jid}`);

          if (getRes.code !== 0) {
            setPageError(getRes.message || '轮询失败');
            clearPolling();
            setIsSearching(false);
            return;
          }

          const jobData = getRes.data;
          setJob(jobData);
          setProgress(jobData.progress);

          if (jobData.status === 'completed') {
            clearPolling();
            setIsSearching(false);
            setProgress(100);
            if (jobData.result) {
              setResult(jobData.result);
            }
          } else if (jobData.status === 'failed') {
            clearPolling();
            setIsSearching(false);
            setPageError(jobData.error || '网格搜索失败');
          }
        } catch (_err) {
          // 轮询过程中的网络错误不终止轮询
        }
      }, POLL_INTERVAL_MS);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : '请求失败');
      setIsSearching(false);
    }
  }, [selectedStock, strategyId, post, get, clearPolling, handleReset]);

  /* ---- 热力图数据 ---- */
  const xLabels = useMemo(() => {
    if (!result) return [];
    const values = [...new Set(result.cells.map((c) => c.x_value))];
    values.sort((a, b) => a - b);
    return values.map(String);
  }, [result]);

  const yLabels = useMemo(() => {
    if (!result) return [];
    const values = [...new Set(result.cells.map((c) => c.y_value))];
    values.sort((a, b) => a - b);
    return values.map(String);
  }, [result]);

  const xName = result?.request.x_param.label ?? 'X参数';
  const yName = result?.request.y_param.label ?? 'Y参数';
  const metricDisplayName = METRIC_COLUMNS.find(
    (c) => c.key === result?.request.target_metric,
  )?.label ?? result?.request.target_metric ?? '目标值';

  /* ---- 热力图 cell 点击 → 高亮表格行 ---- */
  const handleCellClick = useCallback((xLabel: string, yLabel: string) => {
    const xVal = parseFloat(xLabel);
    const yVal = parseFloat(yLabel);
    setHighlightedCell({ x: xVal, y: yVal });

    const container = tableContainerRef.current;
    if (!container) return;

    const row = container.querySelector<HTMLTableRowElement>(
      `tr[data-gs-x="${xVal}"][data-gs-y="${yVal}"]`,
    );
    row?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, []);

  /* ---- 左侧面板 ---- */
  const leftPanel = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        网格搜索
      </Typography>
      <Typography variant="body2" sx={{ color: '#6b7280' }}>
        对双参数进行穷举式搜索，通过热力图直观呈现最优参数组合。
      </Typography>

      <StockSearch
        value={selectedStock}
        onChange={(s) => {
          setSelectedStock(s);
          handleReset();
        }}
        label="选择股票"
      />

      <StrategySelector value={strategyId} onChange={setStrategyId} />

      <ParamGridConfig
        onSearch={handleSearch}
        loading={isSearching}
        disabled={!selectedStock}
      />

      {pageError && (
        <Alert severity="error" onClose={() => setPageError(null)}>
          {pageError}
        </Alert>
      )}
    </Box>
  );

  /* ---- 右侧面板 ---- */
  const rightPanel = (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 2 }}>
      {/* 进度指示 */}
      {isSearching && (
        <Paper variant="outlined" sx={{ p: 2, flexShrink: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {job?.status === 'running' ? '搜索进行中...' : '准备中...'}
            </Typography>
            <Typography variant="caption" sx={{ color: '#6b7280' }}>
              {progress}%
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={progress}
            sx={{ height: 6, borderRadius: 1 }}
          />
        </Paper>
      )}

      {/* 失败: 无结果 */}
      {!isSearching && pageError && !result && (
        <Box sx={{ p: 4, textAlign: 'center' }}>
          <Alert severity="error" onClose={() => setPageError(null)}>
            {pageError}
          </Alert>
        </Box>
      )}

      {/* 空状态 */}
      {!isSearching && !result && !pageError && (
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            color: '#9ca3af',
            gap: 1,
          }}
        >
          <Typography variant="body1">选择股票和策略后开始网格搜索</Typography>
          <Typography variant="body2">
            配置 X/Y 参数范围，系统将自动搜索最优参数组合
          </Typography>
        </Box>
      )}

      {/* 结果展示 */}
      {result && (
        <>
          {/* 热力图 */}
          <Paper variant="outlined" sx={{ p: 2, flexShrink: 0 }}>
            <ParamHeatmap
              data={result.heatmap_data}
              xLabels={xLabels}
              yLabels={yLabels}
              xName={xName}
              yName={yName}
              metricName={metricDisplayName}
              onCellClick={handleCellClick}
              height={350}
            />
            {result.best_cell && (
              <Box sx={{ display: 'flex', gap: 1, mt: 1.5, flexWrap: 'wrap' }}>
                <Chip
                  label={`最优: ${xName}=${result.best_cell.x_value}, ${yName}=${result.best_cell.y_value}`}
                  color="success"
                  size="small"
                />
                <Chip
                  label={`目标值: ${(result.best_cell.target_value * 100).toFixed(2)}%`}
                  variant="outlined"
                  size="small"
                />
                <Chip
                  label={`耗时: ${result.elapsed_seconds.toFixed(1)}秒`}
                  variant="outlined"
                  size="small"
                />
              </Box>
            )}
          </Paper>

          {/* 结果表格 */}
          <Paper variant="outlined" sx={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
            <TableContainer sx={{ maxHeight: '100%' }} ref={tableContainerRef}>
              <Table stickyHeader size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 600, bgcolor: '#fafafa' }}>
                      {xName}
                    </TableCell>
                    <TableCell sx={{ fontWeight: 600, bgcolor: '#fafafa' }}>
                      {yName}
                    </TableCell>
                    {METRIC_COLUMNS.map((col) => (
                      <TableCell
                        key={col.key}
                        align="right"
                        sx={{ fontWeight: 600, bgcolor: '#fafafa' }}
                      >
                        {col.label}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.cells.map((cell, idx) => {
                    const isBest =
                      result.best_cell &&
                      cell.x_value === result.best_cell.x_value &&
                      cell.y_value === result.best_cell.y_value;

                    const isHl =
                      highlightedCell &&
                      cell.x_value === highlightedCell.x &&
                      cell.y_value === highlightedCell.y;

                    return (
                      <TableRow
                        key={`${cell.x_value}_${cell.y_value}_${idx}`}
                        data-gs-x={cell.x_value}
                        data-gs-y={cell.y_value}
                        sx={{
                          bgcolor: isBest
                            ? '#f6ffed'
                            : isHl
                              ? '#e6f7ff'
                              : undefined,
                          '&:hover': { bgcolor: '#fafafa' },
                        }}
                      >
                        <TableCell>{cell.x_value}</TableCell>
                        <TableCell>{cell.y_value}</TableCell>
                        {METRIC_COLUMNS.map((col) => {
                          let value: number | undefined;
                          if (col.key === 'target_value') {
                            value = cell.target_value;
                          } else {
                            value = cell.metrics[col.key];
                          }

                          const formatter = METRIC_FORMAT[col.key];
                          const display = value !== undefined && formatter
                            ? formatter(value)
                            : '-';

                          return (
                            <TableCell key={col.key} align="right">
                              {display}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </>
      )}
    </Box>
  );

  return <SplitPane left={leftPanel} right={rightPanel} leftWidth={420} />;
};

export default GridSearch;
