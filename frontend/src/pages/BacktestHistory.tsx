/**
 * 发现者（Discoverer）— 回测历史页
 *
 * 表格展示回测历史记录，支持筛选和展开详情。
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Collapse,
  TextField,
  Alert,
  Snackbar,
  CircularProgress,
  IconButton,
  TablePagination,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import { useApi } from '../hooks/useApi';
import type {
  BacktestHistoryRecord,
  BacktestHistoryDetail,
  SavedStrategy,
  Trade,
  EquityPoint,
} from '../types';

// 数据来源颜色映射
const DATA_SOURCE_COLORS: Record<string, 'success' | 'primary' | 'default' | 'warning'> = {
  tdx: 'success',
  akshare: 'primary',
  mock: 'default',
  parquet_cache: 'warning',
};

const DATA_SOURCE_LABELS: Record<string, string> = {
  tdx: 'TDX',
  akshare: 'AKShare',
  mock: 'Mock',
  parquet_cache: 'Parquet',
};

const BacktestHistory: React.FC = () => {
  const { get } = useApi();
  const [records, setRecords] = useState<BacktestHistoryRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 筛选状态
  const [stockCodeFilter, setStockCodeFilter] = useState('');
  const [strategyIdFilter, setStrategyIdFilter] = useState<number | ''>('');
  const [strategies, setStrategies] = useState<SavedStrategy[]>([]);

  // 展开状态
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState<BacktestHistoryDetail | null>(null);

  // 分页
  const [page, setPage] = useState(0);
  const [toast, setToast] = useState({ open: false, message: '', severity: 'info' as 'info' | 'error' | 'success' });
  const rowsPerPage = 20;

  // 加载策略列表（用于筛选项）
  useEffect(() => {
    const load = async () => {
      const res = await get<SavedStrategy[]>('/strategies');
      if (res.code === 0 && res.data) {
        setStrategies(res.data);
      }
    };
    load();
  }, [get]);

  // 加载回测历史
  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      let url = '/backtest/history';
      const params: string[] = [];
      if (stockCodeFilter) params.push(`stock_code=${encodeURIComponent(stockCodeFilter)}`);
      if (strategyIdFilter !== '') params.push(`strategy_id=${strategyIdFilter}`);
      if (params.length > 0) url += '?' + params.join('&');

      const res = await get<BacktestHistoryRecord[]>(url);
      if (res.code === 0 && res.data) {
        setRecords(res.data);
      } else {
        setError(res.message || '加载失败');
      }
    } catch {
      setError('网络错误');
    } finally {
      setLoading(false);
    }
  }, [get, stockCodeFilter, strategyIdFilter]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // 展开详情
  const handleExpand = async (recordId: number) => {
    if (expandedId === recordId) {
      setExpandedId(null);
      setDetailData(null);
      return;
    }
    setExpandedId(recordId);
    setDetailLoading(true);
    setDetailData(null);
    try {
      const res = await get<BacktestHistoryDetail>(`/backtest/history/${recordId}`);
      if (res.code === 0 && res.data) {
        setDetailData(res.data);
      }
    } finally {
      setDetailLoading(false);
    }
  };

  // 格式化百分比
  const formatPct = (val: number) => `${(val * 100).toFixed(2)}%`;

  // 格式化日期时间
  const formatDate = (iso: string | undefined) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // ── PDF 导出 ──────────────────────────────────────────
  const handleExportPdf = useCallback(async (recordId: number, e: React.MouseEvent) => {
    e.stopPropagation();

    try {
      const res = await get<{ pdf_base64: string; filename: string }>(`/report/export/${recordId}`);

      if (res.code === 0 && res.data) {
        const byteChars = atob(res.data.pdf_base64);
        const byteArr = new Uint8Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) {
          byteArr[i] = byteChars.charCodeAt(i);
        }
        const blob = new Blob([byteArr], { type: 'application/pdf' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = res.data.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        setToast({ open: true, message: 'PDF 报告已下载', severity: 'success' });
      } else {
        setToast({ open: true, message: res.message || 'PDF 导出失败', severity: 'error' });
      }
    } catch (err) {
      setToast({
        open: true,
        message: err instanceof Error ? err.message : 'PDF 导出失败',
        severity: 'error',
      });
    }
  }, [get]);

  // ── 空状态 ──────────────────────────────────────────
  if (!loading && records.length === 0 && !stockCodeFilter && strategyIdFilter === '') {
    return (
      <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
        <Typography variant="h5" sx={{ fontWeight: 600, mb: 3 }}>
          回测历史
        </Typography>
        <Paper
          sx={{
            p: 6,
            textAlign: 'center',
            borderRadius: 3,
            bgcolor: '#fafafa',
            border: '2px dashed #e0e0e0',
          }}
        >
          <Typography variant="h6" sx={{ color: '#9ca3af', mb: 1 }}>
            📊
          </Typography>
          <Typography variant="body1" sx={{ color: '#9ca3af' }}>
            暂无回测历史记录
          </Typography>
        </Paper>
      </Box>
    );
  }

  return (
    <>
      <Box sx={{ p: 4, maxWidth: 1400, mx: 'auto' }}>
      {/* 页面标题 */}
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 3 }}>
        回测历史
      </Typography>

      {/* 筛选栏 */}
      <Paper sx={{ p: 2, mb: 3, borderRadius: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
        <TextField
          size="small"
          label="股票代码"
          value={stockCodeFilter}
          onChange={(e) => setStockCodeFilter(e.target.value)}
          sx={{ minWidth: 140 }}
          placeholder="如 000001"
        />
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <InputLabel>策略筛选</InputLabel>
          <Select
            value={strategyIdFilter}
            label="策略筛选"
            onChange={(e) => setStrategyIdFilter(e.target.value as number | '')}
          >
            <MenuItem value="">全部策略</MenuItem>
            {strategies.map((s) => (
              <MenuItem key={s.id} value={s.id}>
                {s.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Paper>

      {/* 加载状态 */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {/* 数据表格 */}
      {!loading && records.length > 0 && (
        <TableContainer component={Paper} sx={{ borderRadius: 2, boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow sx={{ bgcolor: '#fafafa' }}>
                <TableCell width={40} />
                <TableCell sx={{ fontWeight: 600 }}>股票代码</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>股票名称</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>策略</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">总收益率</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">年化收益</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">最大回撤</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">胜率</TableCell>
                <TableCell sx={{ fontWeight: 600 }} align="right">夏普比率</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>数据来源</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>回测时间</TableCell>
                <TableCell sx={{ fontWeight: 600 }} width={60}>报告</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {records.slice(page * rowsPerPage, (page + 1) * rowsPerPage).map((record) => (
                <React.Fragment key={record.id}>
                  <TableRow
                    hover
                    sx={{ cursor: 'pointer', '&:hover': { bgcolor: '#f5f8ff' } }}
                    onClick={() => handleExpand(record.id)}
                  >
                    <TableCell>
                      <IconButton size="small">
                        {expandedId === record.id ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
                      </IconButton>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 500, fontFamily: 'monospace' }}>
                        {record.stock_code}
                      </Typography>
                    </TableCell>
                    <TableCell>{record.stock_name || '-'}</TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ maxWidth: 120 }} noWrap>
                        {(record as any).strategy_name || '-'}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: 600,
                          color: record.total_return >= 0 ? '#cf1322' : '#389e0d',
                        }}
                      >
                        {formatPct(record.total_return)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography
                        variant="body2"
                        sx={{ color: record.annual_return >= 0 ? '#cf1322' : '#389e0d' }}
                      >
                        {formatPct(record.annual_return)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Typography variant="body2" sx={{ color: '#cf1322' }}>
                        {formatPct(record.max_drawdown)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      {formatPct(record.win_rate)}
                    </TableCell>
                    <TableCell align="right">
                      {record.sharpe_ratio.toFixed(2)}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={DATA_SOURCE_LABELS[record.data_source] || record.data_source}
                        size="small"
                        color={DATA_SOURCE_COLORS[record.data_source] || 'default'}
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="caption" sx={{ color: '#6b7280' }}>
                        {formatDate(record.created_at)}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <IconButton
                        size="small"
                        onClick={(e) => handleExportPdf(record.id, e)}
                        title="导出 PDF 报告"
                        sx={{ color: '#9ca3af', '&:hover': { color: '#dc2626' } }}
                      >
                        <PictureAsPdfIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>

                  {/* 展开详情行 */}
                  <TableRow>
                    <TableCell colSpan={13} sx={{ py: 0, borderBottom: 0 }}>
                      <Collapse in={expandedId === record.id}>
                        <Box sx={{ p: 3, bgcolor: '#fafafa', borderTop: '1px solid #f0f0f0' }}>
                          {detailLoading ? (
                            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
                              <CircularProgress size={24} />
                            </Box>
                          ) : detailData ? (
                            <Box>
                              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
                                回测详情
                              </Typography>

                              {/* 摘要指标 */}
                              <Box
                                sx={{
                                  display: 'grid',
                                  gridTemplateColumns: {
                                    xs: 'repeat(2, 1fr)',
                                    md: 'repeat(3, 1fr)',
                                    lg: 'repeat(auto-fill, minmax(150px, 1fr))',
                                  },
                                  gap: 2,
                                  mb: 3,
                                }}
                              >
                                <Paper sx={{ p: 1.5, textAlign: 'center' }}>
                                  <Typography variant="caption" sx={{ color: '#9ca3af' }}>交易次数</Typography>
                                  <Typography variant="h6">{detailData.total_trades}</Typography>
                                </Paper>
                                <Paper sx={{ p: 1.5, textAlign: 'center' }}>
                                  <Typography variant="caption" sx={{ color: '#9ca3af' }}>盈亏比</Typography>
                                  <Typography variant="h6">{detailData.profit_loss_ratio.toFixed(2)}</Typography>
                                </Paper>
                                <Paper sx={{ p: 1.5, textAlign: 'center' }}>
                                  <Typography variant="caption" sx={{ color: '#9ca3af' }}>回测区间</Typography>
                                  <Typography variant="body2">
                                    {detailData.start_date} ~ {detailData.end_date}
                                  </Typography>
                                </Paper>
                                <Paper sx={{ p: 1.5, textAlign: 'center' }}>
                                  <Typography variant="caption" sx={{ color: '#9ca3af' }}>数据来源</Typography>
                                  <Typography variant="body2">{detailData.data_source}</Typography>
                                </Paper>
                              </Box>

                              {/* 交易明细 */}
                              {detailData.result_data?.trades &&
                                detailData.result_data.trades.length > 0 && (
                                  <Box sx={{ mb: 3 }}>
                                    <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                                      交易明细（最近 20 笔）
                                    </Typography>
                                    <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
                                      <Table size="small">
                                        <TableHead>
                                          <TableRow sx={{ bgcolor: '#f5f5f5' }}>
                                            <TableCell>买入日期</TableCell>
                                            <TableCell>买入价</TableCell>
                                            <TableCell>卖出日期</TableCell>
                                            <TableCell>卖出价</TableCell>
                                            <TableCell align="right">收益率</TableCell>
                                            <TableCell>卖出原因</TableCell>
                                          </TableRow>
                                        </TableHead>
                                        <TableBody>
                                          {detailData.result_data.trades
                                            .slice(-20)
                                            .reverse()
                                            .map((trade: Trade, idx: number) => (
                                              <TableRow key={idx}>
                                                <TableCell>{trade.entry_date}</TableCell>
                                                <TableCell>{trade.entry_price.toFixed(2)}</TableCell>
                                                <TableCell>{trade.exit_date}</TableCell>
                                                <TableCell>{trade.exit_price.toFixed(2)}</TableCell>
                                                <TableCell align="right">
                                                  <Typography
                                                    variant="body2"
                                                    sx={{
                                                      fontWeight: 600,
                                                      color: trade.return_pct >= 0 ? '#cf1322' : '#389e0d',
                                                    }}
                                                  >
                                                    {formatPct(trade.return_pct)}
                                                  </Typography>
                                                </TableCell>
                                                <TableCell>
                                                  <Typography variant="caption" sx={{ color: '#6b7280' }}>
                                                    {trade.exit_reason}
                                                  </Typography>
                                                </TableCell>
                                              </TableRow>
                                            ))}
                                        </TableBody>
                                      </Table>
                                    </TableContainer>
                                  </Box>
                                )}

                              {/* 资金曲线占位 */}
                              {detailData.result_data?.equity_curve &&
                                detailData.result_data.equity_curve.length > 0 && (
                                  <Box>
                                    <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                                      资金曲线摘要
                                    </Typography>
                                    <Box
                                      sx={{
                                        display: 'grid',
                                        gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' },
                                        gap: 2,
                                      }}
                                    >
                                      <Paper sx={{ p: 1.5, textAlign: 'center' }}>
                                        <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                                          数据点数
                                        </Typography>
                                        <Typography variant="h6">
                                          {detailData.result_data.equity_curve.length}
                                        </Typography>
                                      </Paper>
                                      <Paper sx={{ p: 1.5, textAlign: 'center' }}>
                                        <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                                          最大回撤
                                        </Typography>
                                        <Typography variant="h6" sx={{ color: '#cf1322' }}>
                                          {formatPct(detailData.max_drawdown)}
                                        </Typography>
                                      </Paper>
                                      <Paper sx={{ p: 1.5, textAlign: 'center' }}>
                                        <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                                          夏普比率
                                        </Typography>
                                        <Typography variant="h6">
                                          {detailData.sharpe_ratio.toFixed(2)}
                                        </Typography>
                                      </Paper>
                                    </Box>
                                  </Box>
                                )}
                            </Box>
                          ) : (
                            <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                              暂无详情数据
                            </Typography>
                          )}
                        </Box>
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
          <TablePagination
            component="div"
            count={records.length}
            page={page}
            onPageChange={(_, newPage) => setPage(newPage)}
            rowsPerPage={rowsPerPage}
            rowsPerPageOptions={[rowsPerPage]}
            labelRowsPerPage="每页"
          />
        </TableContainer>
      )}

      {/* 错误提示 */}
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setError(null)} sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>
    </Box>
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

export default BacktestHistory;
