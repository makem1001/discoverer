/**
 * 发现者（Discoverer）— P1-3: 模拟交易页面
 *
 * 功能：
 *  - 左侧账户列表（创建/删除/选择）
 *  - 右侧账户详情（持仓表格 + 权益曲线 + 交易记录）
 *  - "前进一天"按钮
 */

import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
  Box, Typography, Button, TextField, Divider, Snackbar, Alert,
  Card, CardContent, CardActions, IconButton, CircularProgress,
  Dialog, DialogTitle, DialogContent, DialogActions,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, Chip, Pagination,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import { useApi } from '../hooks/useApi';
import type {
  PaperAccount,
  PaperAccountCreate,
  PaperAccountSummary,
  PaperPosition,
  PaperTrade,
  PaperTradeListResponse,
} from '../types';

const PaperTrading: React.FC = () => {
  const { get, post, del, loading, setError } = useApi();

  // 状态
  const [accounts, setAccounts] = useState<PaperAccount[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [summary, setSummary] = useState<PaperAccountSummary | null>(null);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [tradesTotal, setTradesTotal] = useState(0);
  const [tradesPage, setTradesPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [toast, setToast] = useState({ open: false, message: '', severity: 'info' as 'info' | 'error' | 'success' });
  const pageSize = 10;

  // 创建表单
  const [newName, setNewName] = useState('');
  const [newCapital, setNewCapital] = useState('100000');
  const [newStrategy, setNewStrategy] = useState('ma_cross');
  const [newStock, setNewStock] = useState('000001');

  // ── 加载账户列表 ────────────────────────────────────

  const loadAccounts = useCallback(async () => {
    const res = await get<PaperAccount[]>('/paper/accounts');
    if (res.code === 0 && res.data) {
      setAccounts(res.data);
    }
  }, [get]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  // ── 选中账户 → 加载摘要和交易记录 ──────────────────

  const loadSummary = useCallback(async (id: string) => {
    const res = await get<PaperAccountSummary>(`/paper/accounts/${id}`);
    if (res.code === 0 && res.data) {
      setSummary(res.data);
    } else {
      setSummary(null);
      setToast({ open: true, message: res.message || '加载失败', severity: 'error' });
    }
  }, [get]);

  const loadTrades = useCallback(async (id: string, page: number = 1) => {
    const res = await get<PaperTradeListResponse>(
      `/paper/accounts/${id}/trades?page=${page}&page_size=${pageSize}`,
    );
    if (res.code === 0 && res.data) {
      setTrades(res.data.trades);
      setTradesTotal(res.data.total);
      setTradesPage(page);
    } else {
      setTrades([]);
      setTradesTotal(0);
    }
  }, [get]);

  const handleSelect = useCallback(
    (id: string) => {
      setSelectedId(id);
      loadSummary(id);
      loadTrades(id, 1);
    },
    [loadSummary, loadTrades],
  );

  // ── 创建账户 ────────────────────────────────────────

  const handleCreate = useCallback(async () => {
    if (!newName.trim()) {
      setToast({ open: true, message: '请输入账户名称', severity: 'error' });
      return;
    }

    const capital = parseFloat(newCapital);
    if (isNaN(capital) || capital < 10000 || capital > 10000000) {
      setToast({ open: true, message: '初始资金需在 10,000 ~ 10,000,000 之间', severity: 'error' });
      return;
    }

    const body: PaperAccountCreate = {
      name: newName.trim(),
      initial_capital: capital,
      strategy_id: newStrategy,
      stock_code: newStock,
    };

    const res = await post<PaperAccount>('/paper/accounts', body);
    if (res.code === 0 && res.data) {
      setToast({ open: true, message: `账户「${res.data.name}」创建成功`, severity: 'success' });
      setCreateOpen(false);
      setNewName('');
      setNewCapital('100000');
      await loadAccounts();
      handleSelect(res.data.id);
    } else {
      setToast({ open: true, message: res.message || '创建失败', severity: 'error' });
    }
  }, [newName, newCapital, newStrategy, newStock, post, loadAccounts, handleSelect]);

  // ── 删除账户 ────────────────────────────────────────

  const handleDelete = useCallback(
    async (id: string) => {
      const res = await del(`/paper/accounts/${id}`);
      if (res.code === 0) {
        setToast({ open: true, message: '账户已删除', severity: 'success' });
        if (selectedId === id) {
          setSelectedId(null);
          setSummary(null);
          setTrades([]);
          setTradesTotal(0);
        }
        await loadAccounts();
      } else {
        setToast({ open: true, message: res.message || '删除失败', severity: 'error' });
      }
    },
    [del, loadAccounts, selectedId],
  );

  // ── 前进一天 ────────────────────────────────────────

  const handleAdvance = useCallback(async () => {
    if (!selectedId) return;

    const res = await post<PaperAccount>(`/paper/accounts/${selectedId}/advance`);
    if (res.code === 0) {
      setToast({ open: true, message: '推进成功', severity: 'success' });
      await loadSummary(selectedId);
      await loadTrades(selectedId, tradesPage);
      await loadAccounts();
    } else {
      setToast({ open: true, message: res.message || '推进失败', severity: 'error' });
    }
  }, [selectedId, post, loadSummary, loadTrades, loadAccounts, tradesPage]);

  // ── 格式化金额 ──────────────────────────────────────

  const fmtMoney = (v: number) => v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const fmtPct = (v: number) => `${(v * 100).toFixed(2)}%`;
  const pnlColor = (v: number) => (v >= 0 ? '#cf1322' : '#389e0d');

  // ── ECharts 权益曲线占位 (T05 集成完整图表) ─────────

  const chartRef = useRef<HTMLDivElement>(null);

  // ── 渲染 ────────────────────────────────────────────

  const selectedAccount = accounts.find((a) => a.id === selectedId);

  return (
    <div className="flex h-full">
      {/* 左侧：账户列表 */}
      <div className="w-72 border-r border-gray-200 bg-white flex flex-col">
        <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            模拟账户
          </Typography>
          <IconButton
            size="small"
            color="primary"
            onClick={() => setCreateOpen(true)}
            title="创建账户"
          >
            <AddIcon />
          </IconButton>
        </Box>

        <Divider />

        <div className="flex-1 overflow-auto p-2">
          {accounts.length === 0 ? (
            <div className="text-center text-gray-400 py-12">
              <AccountBalanceIcon sx={{ fontSize: 48, mb: 1, color: '#d1d5db' }} />
              <Typography variant="body2">暂无模拟账户</Typography>
              <Button
                variant="outlined"
                size="small"
                sx={{ mt: 2 }}
                startIcon={<AddIcon />}
                onClick={() => setCreateOpen(true)}
              >
                创建第一个账户
              </Button>
            </div>
          ) : (
            accounts.map((acc) => (
              <Card
                key={acc.id}
                sx={{
                  mb: 1,
                  cursor: 'pointer',
                  border: selectedId === acc.id ? '2px solid #1a73e8' : '2px solid transparent',
                  bgcolor: selectedId === acc.id ? '#eff6ff' : '#ffffff',
                  '&:hover': { bgcolor: '#f9fafb' },
                }}
                elevation={0}
                onClick={() => handleSelect(acc.id)}
              >
                <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                  <div className="flex justify-between items-start">
                    <div>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {acc.name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {acc.stock_code}
                      </Typography>
                    </div>
                    <Chip
                      label={acc.status === 'running' ? '运行中' : acc.status === 'paused' ? '已暂停' : '已关闭'}
                      size="small"
                      color={acc.status === 'running' ? 'success' : 'default'}
                      sx={{ fontSize: '0.7rem' }}
                    />
                  </div>
                  <div className="mt-2 flex justify-between text-sm">
                    <span className="text-gray-500">总资产</span>
                    <span style={{ fontWeight: 600, color: pnlColor(acc.total_value - acc.initial_capital) }}>
                      ¥{fmtMoney(acc.total_value)}
                    </span>
                  </div>
                </CardContent>
                <CardActions sx={{ pt: 0, justifyContent: 'flex-end' }}>
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(acc.id);
                    }}
                    sx={{ color: '#9ca3af' }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </CardActions>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* 右侧：账户详情 */}
      <div className="flex-1 overflow-auto bg-gray-50 p-6">
        {!selectedAccount ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center text-gray-400">
              <TrendingUpIcon sx={{ fontSize: 64, mb: 2, color: '#d1d5db' }} />
              <Typography variant="h6">选择一个模拟账户</Typography>
              <Typography variant="body2">从左侧列表选择或创建一个新账户</Typography>
            </div>
          </div>
        ) : (
          <>
            {/* 账户头部 */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {selectedAccount.name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  股票: {selectedAccount.stock_code} · 初始资金: ¥{fmtMoney(selectedAccount.initial_capital)}
                </Typography>
              </div>
              <Button
                variant="contained"
                startIcon={<PlayArrowIcon />}
                onClick={handleAdvance}
                disabled={selectedAccount.status !== 'running' || loading}
                sx={{
                  bgcolor: '#059669',
                  '&:hover': { bgcolor: '#047857' },
                  textTransform: 'none',
                  fontWeight: 600,
                }}
              >
                前进一天
              </Button>
            </div>

            {/* 指标卡片 */}
            {summary && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <Card elevation={0} sx={{ border: '1px solid #e5e7eb' }}>
                  <CardContent sx={{ p: 3, textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">总资产</Typography>
                    <Typography variant="h6" sx={{ fontWeight: 700, mt: 0.5 }}>
                      ¥{fmtMoney(summary.total_value)}
                    </Typography>
                  </CardContent>
                </Card>
                <Card elevation={0} sx={{ border: '1px solid #e5e7eb' }}>
                  <CardContent sx={{ p: 3, textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">可用资金</Typography>
                    <Typography variant="h6" sx={{ fontWeight: 700, mt: 0.5 }}>
                      ¥{fmtMoney(summary.current_cash)}
                    </Typography>
                  </CardContent>
                </Card>
                <Card elevation={0} sx={{ border: '1px solid #e5e7eb' }}>
                  <CardContent sx={{ p: 3, textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">持仓市值</Typography>
                    <Typography variant="h6" sx={{ fontWeight: 700, mt: 0.5 }}>
                      ¥{fmtMoney(summary.position_value)}
                    </Typography>
                  </CardContent>
                </Card>
                <Card elevation={0} sx={{ border: '1px solid #e5e7eb' }}>
                  <CardContent sx={{ p: 3, textAlign: 'center' }}>
                    <Typography variant="caption" color="text.secondary">总盈亏</Typography>
                    <Typography
                      variant="h6"
                      sx={{ fontWeight: 700, mt: 0.5, color: pnlColor(summary.total_pnl) }}
                    >
                      {summary.total_pnl >= 0 ? '+' : ''}¥{fmtMoney(summary.total_pnl)} ({fmtPct(summary.total_pnl_pct)})
                    </Typography>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* 权益曲线区域（占位） */}
            <Card elevation={0} sx={{ border: '1px solid #e5e7eb', mb: 4 }}>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                  权益曲线
                </Typography>
                <div
                  ref={chartRef}
                  className="w-full bg-gray-50 rounded-lg flex items-center justify-center"
                  style={{ height: 280 }}
                >
                  <Typography variant="body2" color="text.secondary">
                    📈 权益曲线图表将在 T05 阶段集成 ECharts
                  </Typography>
                </div>
              </CardContent>
            </Card>

            {/* 持仓表格 */}
            {summary && summary.positions.length > 0 && (
              <Card elevation={0} sx={{ border: '1px solid #e5e7eb', mb: 4 }}>
                <CardContent sx={{ p: 3 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                    当前持仓
                  </Typography>
                  <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e5e7eb', overflowX: 'auto' }}>
                    <Table size="small">
                      <TableHead>
                        <TableRow sx={{ bgcolor: '#f9fafb' }}>
                          <TableCell>股票代码</TableCell>
                          <TableCell align="right">持仓数量</TableCell>
                          <TableCell align="right">均价</TableCell>
                          <TableCell align="right">现价</TableCell>
                          <TableCell align="right">市值</TableCell>
                          <TableCell align="right">浮动盈亏</TableCell>
                          <TableCell align="right">盈亏%</TableCell>
                          <TableCell>开仓日期</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {summary.positions.map((pos: PaperPosition) => (
                          <TableRow key={pos.id} hover>
                            <TableCell sx={{ fontWeight: 600 }}>{pos.stock_code}</TableCell>
                            <TableCell align="right">{pos.shares}</TableCell>
                            <TableCell align="right">¥{pos.avg_cost.toFixed(2)}</TableCell>
                            <TableCell align="right">¥{pos.current_price.toFixed(2)}</TableCell>
                            <TableCell align="right">¥{fmtMoney(pos.market_value)}</TableCell>
                            <TableCell align="right" sx={{ color: pnlColor(pos.unrealized_pnl) }}>
                              {pos.unrealized_pnl >= 0 ? '+' : ''}¥{fmtMoney(pos.unrealized_pnl)}
                            </TableCell>
                            <TableCell align="right" sx={{ color: pnlColor(pos.unrealized_pnl_pct) }}>
                              {fmtPct(pos.unrealized_pnl_pct)}
                            </TableCell>
                            <TableCell>{pos.open_date}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </CardContent>
              </Card>
            )}

            {/* 交易记录 */}
            <Card elevation={0} sx={{ border: '1px solid #e5e7eb' }}>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                  交易记录
                </Typography>
                {trades.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                    暂无交易记录
                  </Typography>
                ) : (
                  <>
                    <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e5e7eb', overflowX: 'auto' }}>
                      <Table size="small">
                        <TableHead>
                          <TableRow sx={{ bgcolor: '#f9fafb' }}>
                            <TableCell>时间</TableCell>
                            <TableCell>类型</TableCell>
                            <TableCell>股票</TableCell>
                            <TableCell align="right">价格</TableCell>
                            <TableCell align="right">数量</TableCell>
                            <TableCell align="right">手续费</TableCell>
                            <TableCell align="right">盈亏</TableCell>
                            <TableCell>原因</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {trades.map((trade: PaperTrade) => (
                            <TableRow key={trade.id} hover>
                              <TableCell sx={{ fontSize: '0.8rem' }}>
                                {new Date(trade.traded_at).toLocaleString('zh-CN')}
                              </TableCell>
                              <TableCell>
                                <Chip
                                  label={trade.trade_type === 'buy' ? '买入' : '卖出'}
                                  size="small"
                                  color={trade.trade_type === 'buy' ? 'primary' : 'warning'}
                                  sx={{ fontSize: '0.7rem', fontWeight: 600 }}
                                />
                              </TableCell>
                              <TableCell>{trade.stock_code}</TableCell>
                              <TableCell align="right">¥{trade.price.toFixed(2)}</TableCell>
                              <TableCell align="right">{trade.shares}</TableCell>
                              <TableCell align="right">¥{trade.fee.toFixed(2)}</TableCell>
                              <TableCell
                                align="right"
                                sx={{
                                  color: trade.pnl != null ? pnlColor(trade.pnl) : undefined,
                                  fontWeight: trade.pnl != null ? 600 : 400,
                                }}
                              >
                                {trade.pnl != null
                                  ? `${trade.pnl >= 0 ? '+' : ''}¥${trade.pnl.toFixed(2)}`
                                  : '—'}
                              </TableCell>
                              <TableCell sx={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {trade.reason}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                    {tradesTotal > pageSize && (
                      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 2 }}>
                        <Pagination
                          count={Math.ceil(tradesTotal / pageSize)}
                          page={tradesPage}
                          onChange={(_e, page) => loadTrades(selectedId!, page)}
                          size="small"
                        />
                      </Box>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* 创建账户对话框 */}
      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 600 }}>创建模拟账户</DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, pt: 1 }}>
            <TextField
              label="账户名称"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="例如：我的双均线策略"
              fullWidth
              required
              helperText="1-100 个字符"
            />
            <TextField
              label="初始资金"
              type="number"
              value={newCapital}
              onChange={(e) => setNewCapital(e.target.value)}
              fullWidth
              required
              helperText="10,000 ~ 10,000,000 元"
              inputProps={{ min: 10000, max: 10000000, step: 10000 }}
            />
            <TextField
              label="策略 ID"
              value={newStrategy}
              onChange={(e) => setNewStrategy(e.target.value)}
              fullWidth
              helperText="例如: ma_cross, macd_golden_cross"
            />
            <TextField
              label="股票代码"
              value={newStock}
              onChange={(e) => setNewStock(e.target.value)}
              fullWidth
              helperText="例如: 000001 (平安银行)"
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setCreateOpen(false)} color="inherit">
            取消
          </Button>
          <Button
            variant="contained"
            onClick={handleCreate}
            disabled={!newName.trim() || loading}
          >
            创建
          </Button>
        </DialogActions>
      </Dialog>

      {/* Toast */}
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
    </div>
  );
};

export default PaperTrading;
