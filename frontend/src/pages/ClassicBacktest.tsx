/**
 * 发现者（Discoverer）— Tab 1: 经典回测页面
 *
 * 股票搜索 → 经典策略选择 → 回测 → 结果展示
 */

import React, { useState, useCallback, useMemo } from 'react';
import {
  Box, Typography, Button, TextField, Divider, Alert, Snackbar, Chip,
  CircularProgress,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import SplitPane from '../components/Layout/SplitPane';
import StockSearch from '../components/Common/StockSearch';
import StrategySelector from '../components/Common/StrategySelector';
import RiskControlPanel from '../components/Common/RiskControlPanel';
import ResultCard from '../components/Common/ResultCard';
import LoadingOverlay from '../components/Common/LoadingOverlay';
import FundCurveChart from '../components/Charts/FundCurveChart';
import YearlyHeatmap from '../components/Charts/YearlyHeatmap';
import MetricsDashboard from '../components/Charts/MetricsDashboard';
import { useApi } from '../hooks/useApi';
import type { Stock, BacktestResult, RiskControlParams } from '../types';

const ClassicBacktest: React.FC = () => {
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [strategyId, setStrategyId] = useState('macd_golden_death');
  const [initialCapital, setInitialCapital] = useState(100000);
  const [riskControl, setRiskControl] = useState<RiskControlParams>({
    atr_stop_multiplier: 0,
    take_profit_pct: 0,
    position_sizing: 'full',
    fixed_position_pct: 0.3,
    max_position_pct: 0.5,
    max_drawdown_limit: 0,
  });
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfExporting, setPdfExporting] = useState(false);
  const [toast, setToast] = useState({ open: false, message: '', severity: 'info' as 'info' | 'error' | 'success' });
  const { post } = useApi();

  const handleRunBacktest = useCallback(async () => {
    if (!selectedStock) {
      setError('请先选择一只股票');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await post<BacktestResult>('/backtest/classic', {
        stock_code: selectedStock.code,
        strategy_id: strategyId,
        initial_capital: initialCapital,
        risk_control: riskControl,
      });

      if (res.code === 0 && res.data) {
        setResult(res.data);
      } else {
        setError(res.message || '回测失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '回测请求失败');
    } finally {
      setLoading(false);
    }
  }, [selectedStock, strategyId, initialCapital, riskControl, post]);

  // ── PDF 导出 ──────────────────────────────────────────
  const handleExportPdf = useCallback(async () => {
    if (!result) return;

    setPdfExporting(true);
    try {
      const res = await post<{ pdf_base64: string; filename: string }>('/report/export', {
        backtest_result: result,
        chart_images: {},
        include_ai: true,
        include_chart: false,
      });

      if (res.code === 0 && res.data) {
        // Blob → 下载
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
    } finally {
      setPdfExporting(false);
    }
  }, [result, post]);

  // ── 左侧输入区 ──────────────────────────────────────
  const leftPanel = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        经典策略回测
      </Typography>
      <Typography variant="body2" sx={{ color: '#6b7280' }}>
        选择一只A股股票和内置的经典策略，查看过去15年的回测表现。
      </Typography>

      <Divider />

      <StockSearch
        value={selectedStock}
        onChange={setSelectedStock}
        label="选择股票"
      />

      <StrategySelector value={strategyId} onChange={setStrategyId} />

      <RiskControlPanel riskControl={riskControl} onChange={setRiskControl} />

      <TextField
        label="初始资金（元）"
        type="number"
        value={initialCapital}
        onChange={(e) => setInitialCapital(Number(e.target.value))}
        InputProps={{ inputProps: { min: 10000, step: 10000 } }}
        fullWidth
      />

      <Button
        variant="contained"
        size="large"
        startIcon={<PlayArrowIcon />}
        onClick={handleRunBacktest}
        disabled={!selectedStock || loading}
        sx={{
          bgcolor: '#1a73e8',
          '&:hover': { bgcolor: '#1557b0' },
          py: 1.5,
          fontSize: '1rem',
        }}
      >
        开始回测
      </Button>

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
  );

  // ── 右侧结果区 ──────────────────────────────────────
  const rightPanel = (
    <Box sx={{ position: 'relative', minHeight: 400 }}>
      <LoadingOverlay visible={loading} message="正在执行回测..." />

      {!result && !loading && (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 400,
            color: '#9ca3af',
          }}
        >
          <Typography variant="h6" sx={{ mb: 1 }}>
            📊
          </Typography>
          <Typography variant="body1">
            选择股票和策略，点击"开始回测"查看结果
          </Typography>
        </Box>
      )}

      {result && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* 标题 + 导出 */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {result.stock_name || result.stock_code}
              </Typography>
              <Chip
                label={result.strategy?.name || '经典策略'}
                size="small"
                color="primary"
                variant="outlined"
              />
            </Box>
            <Button
              variant="outlined"
              size="small"
              startIcon={pdfExporting ? <CircularProgress size={16} /> : <PictureAsPdfIcon />}
              onClick={handleExportPdf}
              disabled={pdfExporting}
              sx={{
                textTransform: 'none',
                borderColor: '#d1d5db',
                color: '#374151',
                '&:hover': { borderColor: '#dc2626', color: '#dc2626', bgcolor: '#fef2f2' },
              }}
            >
              {pdfExporting ? '导出中...' : '导出PDF'}
            </Button>
          </Box>

          {/* 指标卡片 */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: 'repeat(2, 1fr)',
                md: 'repeat(3, 1fr)',
                lg: 'repeat(auto-fill, minmax(160px, 1fr))',
              },
              gap: 2,
            }}
          >
            <ResultCard label="总收益率" value={result.metrics.total_return} format="percent" />
            <ResultCard label="年化收益率" value={result.metrics.annual_return} format="percent" />
            <ResultCard label="最大回撤" value={result.metrics.max_drawdown} format="percent" color="down" />
            <ResultCard label="胜率" value={result.metrics.win_rate} format="percent" />
            <ResultCard label="夏普比率" value={result.metrics.sharpe_ratio} format="ratio" />
            <ResultCard label="交易次数" value={result.metrics.total_trades} format="integer" color="neutral" />
          </Box>

          {/* 资金曲线图 */}
          {result.equity_curve.length > 0 && (
            <FundCurveChart data={result.equity_curve} ddBreached={result.metrics.dd_breached} />
          )}

          {/* 回撤熔断警告 */}
          {result.metrics.dd_breached && (
            <Alert severity="warning" variant="outlined" sx={{ borderRadius: 2 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                ⚠️ 回撤熔断已触发
              </Typography>
              <Typography variant="caption" sx={{ color: '#92400e' }}>
                最大回撤超过了设定的熔断阈值，回测已在触发点自动平仓并停止交易。
              </Typography>
            </Alert>
          )}

          {/* 指标仪表盘 */}
          <MetricsDashboard metrics={result.metrics} />

          {/* 逐年热力图 */}
          {result.yearly_stats.length > 0 && (
            <YearlyHeatmap data={result.yearly_stats} />
          )}

          {/* AI 解读 */}
          {result.ai_interpretation && (
            <Box
              sx={{
                p: 2.5,
                bgcolor: '#f0f7ff',
                borderRadius: 2,
                border: '1px solid #bfdbfe',
              }}
            >
              <Typography variant="subtitle2" sx={{ mb: 1, color: '#1e40af' }}>
                🤖 AI 解读
              </Typography>
              <Typography variant="body2" sx={{ color: '#374151', lineHeight: 1.7 }}>
                {result.ai_interpretation}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ mt: 2, display: 'block' }}
              >
                ⚠️ 风险提示：以上回测结果基于历史数据，不构成投资建议。投资有风险，入市需谨慎。
              </Typography>
            </Box>
          )}

          {/* 交易记录摘要 */}
          {result.trades.length > 0 && (
            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                最近交易记录
              </Typography>
              <Box sx={{ maxHeight: 200, overflow: 'auto' }}>
                {result.trades.slice(-10).reverse().map((trade, idx) => {
                  const reasonMap: Record<string, string> = {
                    signal: '信号卖出',
                    hold_expired: '持有到期',
                    stop_loss: '止损',
                    stop_profit: '止盈',
                    trailing_stop: '移动止损',
                    end_of_period: '期末平仓',
                    atr_stop: 'ATR止损',
                    dd_breached: '回撤熔断',
                  };
                  const reasonLabel = reasonMap[trade.exit_reason] || trade.exit_reason;
                  return (
                    <Box
                      key={idx}
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        py: 1,
                        px: 1.5,
                        borderBottom: '1px solid #f3f4f6',
                        fontSize: '0.8rem',
                      }}
                    >
                      <span>
                        {trade.entry_date} → {trade.exit_date}
                      </span>
                      <span style={{ color: trade.return_pct > 0 ? '#cf1322' : '#389e0d' }}>
                        {(trade.return_pct * 100).toFixed(2)}%
                      </span>
                      <Chip
                        label={reasonLabel}
                        size="small"
                        sx={{
                          fontSize: '0.7rem',
                          height: 20,
                          bgcolor:
                            trade.exit_reason === 'atr_stop' ? '#fef3c7' :
                            trade.exit_reason === 'dd_breached' ? '#fee2e2' :
                            '#f3f4f6',
                          color:
                            trade.exit_reason === 'atr_stop' ? '#92400e' :
                            trade.exit_reason === 'dd_breached' ? '#991b1b' :
                            '#6b7280',
                        }}
                      />
                    </Box>
                  );
                })}
              </Box>
            </Box>
          )}
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

export default ClassicBacktest;
