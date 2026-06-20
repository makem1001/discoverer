/**
 * 发现者（Discoverer）— P1-2: 多策略对比回测页面
 *
 * 功能：
 *  - 股票搜索 + 多策略选择
 *  - 开始对比 → 并行回测
 *  - 结果区：叠加资金曲线图 + 指标对比表格 + AI 解读
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  Box, Typography, Button, TextField, Divider, Snackbar, Alert,
  FormControl, InputLabel, Select, MenuItem, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, CircularProgress, Checkbox, ListItemText, OutlinedInput,
} from '@mui/material';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import SplitPane from '../components/Layout/SplitPane';
import StockSearch from '../components/Common/StockSearch';
import LoadingOverlay from '../components/Common/LoadingOverlay';
import { useApi } from '../hooks/useApi';
import type {
  Stock, CompareBacktestRequest, CompareBacktestResponse,
  CompareStrategyResult,
} from '../types';

// 经典策略列表（与后端 CLASSIC_STRATEGIES 同步）
const STRATEGY_OPTIONS = [
  { value: 'macd_golden_death', label: 'MACD 金叉死叉' },
  { value: 'ma_cross', label: '双均线交叉' },
  { value: 'ma_triple', label: '三均线系统' },
  { value: 'bollinger_break', label: '布林带突破' },
  { value: 'rsi_oversold', label: 'RSI 超卖反转' },
  { value: 'kdj_golden', label: 'KDJ 金叉' },
  { value: 'volume_break', label: '放量突破' },
  { value: 'momentum_break', label: '动量突破' },
  { value: 'turtle', label: '海龟交易法' },
  { value: 'dual_thrust', label: 'Dual Thrust' },
  { value: 'atr_channel', label: 'ATR 通道' },
  { value: 'ma_envelope', label: '均线包络' },
  { value: 'macd_divergence', label: 'MACD 背离' },
];

const CompareBacktest: React.FC = () => {
  const { post } = useApi();
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [strategyIds, setStrategyIds] = useState<string[]>(['macd_golden_death', 'ma_cross']);
  const [initialCapital] = useState(100000);
  const [endDate, setEndDate] = useState('2024-12-31');
  const [startDate] = useState('2010-01-01');
  const [result, setResult] = useState<CompareBacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState({ open: false, message: '', severity: 'info' as 'info' | 'error' | 'success' });
  const chartRef = useRef<HTMLDivElement>(null);

  const handleCompare = useCallback(async () => {
    if (!selectedStock) {
      setError('请先选择一只股票');
      return;
    }
    if (strategyIds.length < 2) {
      setError('请至少选择 2 个策略');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const body: CompareBacktestRequest = {
        stock_code: selectedStock.code,
        strategy_ids: strategyIds,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital,
      };

      const res = await post<CompareBacktestResponse>('/compare', body);

      if (res.code === 0 && res.data) {
        setResult(res.data);
      } else {
        setError(res.message || '对比回测失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '对比请求失败');
    } finally {
      setLoading(false);
    }
  }, [selectedStock, strategyIds, endDate, startDate, initialCapital, post]);

  // 格式化
  const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;
  const pnlColor = (v: number) => (v >= 0 ? '#cf1322' : '#389e0d');

  // 策略颜色
  const COLORS = ['#1a73e8', '#dc2626', '#7c3aed', '#d97706', '#059669'];

  // ── 左侧输入区 ──────────────────────────────────────
  const leftPanel = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        策略对比
      </Typography>
      <Typography variant="body2" sx={{ color: '#6b7280' }}>
        选择同一只股票和多个经典策略，一键对比各策略的历史表现。
      </Typography>

      <Divider />

      <StockSearch
        value={selectedStock}
        onChange={setSelectedStock}
        label="选择股票"
      />

      {/* 多策略选择 */}
      <FormControl fullWidth>
        <InputLabel id="strategies-label">选择策略（至少2个）</InputLabel>
        <Select
          labelId="strategies-label"
          multiple
          value={strategyIds}
          onChange={(e) => {
            const val = e.target.value as string[];
            if (val.length <= 5) setStrategyIds(val);
          }}
          input={<OutlinedInput label="选择策略（至少2个）" />}
          renderValue={(selected) => (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {selected.map((id) => {
                const opt = STRATEGY_OPTIONS.find((o) => o.value === id);
                return (
                  <Chip
                    key={id}
                    label={opt?.label || id}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                );
              })}
            </Box>
          )}
        >
          {STRATEGY_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              <Checkbox checked={strategyIds.includes(opt.value)} size="small" />
              <ListItemText primary={opt.label} />
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <TextField
        label="回测结束日期"
        type="date"
        value={endDate}
        onChange={(e) => setEndDate(e.target.value)}
        InputLabelProps={{ shrink: true }}
        fullWidth
        helperText={`起始日期: ${startDate}`}
      />

      <Button
        variant="contained"
        size="large"
        startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <CompareArrowsIcon />}
        onClick={handleCompare}
        disabled={!selectedStock || strategyIds.length < 2 || loading}
        sx={{
          bgcolor: '#7c3aed',
          '&:hover': { bgcolor: '#6d28d9' },
          py: 1.5,
          fontSize: '1rem',
        }}
      >
        {loading ? '对比中...' : '开始对比'}
      </Button>

      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      </Snackbar>
    </Box>
  );

  // ── 右侧结果区 ──────────────────────────────────────
  const rightPanel = (
    <Box sx={{ position: 'relative', minHeight: 400 }}>
      <LoadingOverlay visible={loading} message="正在执行对比回测..." />

      {!result && !loading && (
        <Box
          sx={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', minHeight: 400, color: '#9ca3af',
          }}
        >
          <Typography variant="h6" sx={{ mb: 1 }}>📊</Typography>
          <Typography variant="body1">
            选择股票和多个策略，点击"开始对比"
          </Typography>
        </Box>
      )}

      {result && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* 标题 */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {result.stock_name || result.stock_code}
              </Typography>
              <Chip
                label={`${result.results.length} 个策略`}
                size="small"
                color="secondary"
                variant="outlined"
              />
            </Box>
          </Box>

          {/* 叠加资金曲线（占位，T05 ECharts 完整集成） */}
          <Paper variant="outlined" sx={{ border: '1px solid #e5e7eb' }}>
            <Box sx={{ p: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                叠加资金曲线
              </Typography>
              <div
                ref={chartRef}
                className="w-full bg-gray-50 rounded-lg flex items-center justify-center"
                style={{ height: 280 }}
              >
                <Box sx={{ textAlign: 'center' }}>
                  {result.results
                    .filter((r) => r.result?.equity_curve?.length > 0)
                    .slice(0, 5)
                    .map((r, i) => (
                      <Box key={r.strategy_id} sx={{ mb: 0.5 }}>
                        <Chip
                          label={`${r.strategy_name}: ${r.result?.equity_curve?.length || 0} 个数据点`}
                          size="small"
                          sx={{
                            bgcolor: COLORS[i % COLORS.length],
                            color: '#fff',
                            fontSize: '0.7rem',
                          }}
                        />
                      </Box>
                    ))}
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    📈 ECharts 多线叠加图表将在 T05 集成
                  </Typography>
                </Box>
              </div>
            </Box>
          </Paper>

          {/* 指标对比表格 */}
          <Paper variant="outlined" sx={{ border: '1px solid #e5e7eb' }}>
            <Box sx={{ p: 3 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                指标对比
              </Typography>
              <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e5e7eb', overflowX: 'auto' }}>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: '#f9fafb' }}>
                      <TableCell sx={{ fontWeight: 600 }}>指标</TableCell>
                      {result.results.map((r, i) => (
                        <TableCell key={r.strategy_id} align="right" sx={{ fontWeight: 600, color: COLORS[i % COLORS.length] }}>
                          {r.strategy_name}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {[
                      { key: 'total_return', label: '总收益率', fmt: fmtPct, color: true },
                      { key: 'annual_return', label: '年化收益率', fmt: fmtPct, color: true },
                      { key: 'max_drawdown', label: '最大回撤', fmt: fmtPct, color: false },
                      { key: 'win_rate', label: '胜率', fmt: fmtPct, color: true },
                      { key: 'sharpe_ratio', label: '夏普比率', fmt: (v: number) => v.toFixed(2), color: true },
                      { key: 'profit_loss_ratio', label: '盈亏比', fmt: (v: number) => v.toFixed(2), color: true },
                      { key: 'total_trades', label: '交易次数', fmt: (v: number) => String(v), color: false },
                    ].map((metric) => {
                      // 找最大值策略（用于高亮）
                      const values = result.results.map((r) => {
                        const m = r.result?.metrics;
                        return m ? (m as Record<string, number>)[metric.key] ?? 0 : 0;
                      });
                      const maxVal = Math.max(...values.filter((v) => !isNaN(v)));

                      return (
                        <TableRow key={metric.key} hover>
                          <TableCell sx={{ fontWeight: 500 }}>{metric.label}</TableCell>
                          {result.results.map((r, idx) => {
                            const m = r.result?.metrics;
                            const val = r.error
                              ? '—'
                              : m
                                ? metric.fmt((m as Record<string, number>)[metric.key] ?? 0)
                                : '—';
                            const numVal = r.error
                              ? 0
                              : m
                                ? (m as Record<string, number>)[metric.key] ?? 0
                                : 0;
                            const isBest = !r.error && numVal === maxVal && maxVal !== 0;

                            return (
                              <TableCell
                                key={r.strategy_id}
                                align="right"
                                sx={{
                                  fontWeight: isBest ? 700 : 400,
                                  bgcolor: isBest ? '#fefce8' : 'transparent',
                                  color: metric.color
                                    ? pnlColor(numVal)
                                    : undefined,
                                }}
                              >
                                {isBest ? '🥇 ' : ''}{val}
                              </TableCell>
                            );
                          })}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          </Paper>

          {/* 风险提示 */}
          <Alert severity="warning" variant="outlined" sx={{ borderRadius: 2 }}>
            <Typography variant="caption">
              ⚠️ 以上对比结果基于历史数据回测，不构成投资建议。投资有风险，入市需谨慎。
            </Typography>
          </Alert>
        </Box>
      )}
    </Box>
  );

  return (
    <>
      <SplitPane left={leftPanel} right={rightPanel} />
      <Snackbar
        open={toast.open}
        autoHideDuration={3000}
        onClose={() => setToast({ ...toast, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={toast.severity}
          onClose={() => setToast({ ...toast, open: false })}
          variant="filled"
        >
          {toast.message}
        </Alert>
      </Snackbar>
    </>
  );
};

export default CompareBacktest;
