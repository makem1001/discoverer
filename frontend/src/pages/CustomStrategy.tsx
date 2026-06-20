/**
 * 发现者（Discoverer）— Tab 2: 自由定制页面
 *
 * 股票搜索 → 白话策略输入 → LLM解析预览 → 确认回测 → 结果展示
 */

import React, { useState, useCallback } from 'react';
import {
  Box, Typography, Button, TextField, Divider, Alert, Snackbar,
  Chip, Paper, CircularProgress, Stepper, Step, StepLabel,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf';
import SplitPane from '../components/Layout/SplitPane';
import StockSearch from '../components/Common/StockSearch';
import RiskControlPanel from '../components/Common/RiskControlPanel';
import ResultCard from '../components/Common/ResultCard';
import LoadingOverlay from '../components/Common/LoadingOverlay';
import FundCurveChart from '../components/Charts/FundCurveChart';
import YearlyHeatmap from '../components/Charts/YearlyHeatmap';
import MetricsDashboard from '../components/Charts/MetricsDashboard';
import { useApi } from '../hooks/useApi';
import { useAuth } from '../contexts/AuthContext';
import type { Stock, BacktestResult, ParseResult, RiskControlParams } from '../types';

const CustomStrategy: React.FC = () => {
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null);
  const [naturalLanguage, setNaturalLanguage] = useState('');
  const [parseResult, setParseResult] = useState<ParseResult | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [saveLoading, setSaveLoading] = useState(false);
  const [pdfExporting, setPdfExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [toast, setToast] = useState({ open: false, message: '', severity: 'info' as 'info' | 'error' | 'success' });
  const [step, setStep] = useState(0); // 0=输入, 1=解析预览, 2=完成
  const [riskControl, setRiskControl] = useState<RiskControlParams>({
    atr_stop_multiplier: 0,
    take_profit_pct: 0,
    position_sizing: 'full',
    fixed_position_pct: 0.3,
    max_position_pct: 0.5,
    max_drawdown_limit: 0,
  });
  const { post } = useApi();
  const { user } = useAuth();

  // Step 1: 解析策略
  const handleParse = useCallback(async () => {
    if (!naturalLanguage.trim()) {
      setError('请输入策略描述');
      return;
    }

    setParsing(true);
    setError(null);

    try {
      const res = await post<ParseResult>('/llm/parse', {
        natural_language: naturalLanguage.trim(),
        stock_code: selectedStock?.code || '',
      });

      if (res.code === 0 && res.data) {
        setParseResult(res.data);
        setStep(1);
      } else {
        setError(res.message || '策略解析失败，请重新描述');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '解析请求失败');
    } finally {
      setParsing(false);
    }
  }, [naturalLanguage, selectedStock, post]);

  // Step 2: 执行回测
  const handleRunBacktest = useCallback(async () => {
    if (!selectedStock) {
      setError('请先选择一只股票');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await post<{
        backtest_result: BacktestResult;
        parse_result: ParseResult;
      }>('/backtest/custom', {
        stock_code: selectedStock.code,
        natural_language: naturalLanguage.trim(),
        risk_control: riskControl,
      });

      if (res.code === 0 && res.data) {
        setResult(res.data.backtest_result);
        setParseResult(res.data.parse_result);
        setStep(2);
      } else {
        setError(res.message || '回测失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '回测请求失败');
    } finally {
      setLoading(false);
    }
  }, [selectedStock, naturalLanguage, riskControl, post]);

  // 保存策略到服务端
  const handleSaveStrategy = useCallback(async () => {
    if (!parseResult?.parsed_strategy) return;

    setSaveLoading(true);
    setError(null);
    try {
      const strategyName = naturalLanguage.trim().slice(0, 50) + (naturalLanguage.trim().length > 50 ? '...' : '');
      const resp = await post<{ id: number }>('/strategies', {
        name: strategyName,
        description: naturalLanguage.trim(),
        raw_text: naturalLanguage.trim(),
        entry_conditions: parseResult.parsed_strategy.entry_conditions,
        exit_conditions: parseResult.parsed_strategy.exit_conditions,
        holding_rule: parseResult.parsed_strategy.holding_rule || null,
        params: {},
      });

      if (resp.code === 0) {
        setSaveSuccess(true);
      } else {
        setError(resp.message || '保存失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存请求失败');
    } finally {
      setSaveLoading(false);
    }
  }, [parseResult, naturalLanguage, post]);

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

  const handleReset = () => {
    setStep(0);
    setParseResult(null);
    setResult(null);
    setNaturalLanguage('');
  };

  // ── 左侧输入区 ──────────────────────────────────────
  const leftPanel = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        自由定制策略
      </Typography>
      <Typography variant="body2" sx={{ color: '#6b7280' }}>
        用大白话描述你的交易策略，AI会帮你自动解析并执行回测。
      </Typography>

      <Divider />

      <StockSearch
        value={selectedStock}
        onChange={setSelectedStock}
        label="选择股票"
      />

      <RiskControlPanel riskControl={riskControl} onChange={setRiskControl} />

      <TextField
        label="策略描述（大白话）"
        placeholder="比如：MACD金叉并且成交量放大，连续3天站上5日线后买入，跌破20日线卖出"
        multiline
        rows={4}
        value={naturalLanguage}
        onChange={(e) => setNaturalLanguage(e.target.value)}
        disabled={step > 0}
        fullWidth
      />

      {/* 解析预览 */}
      {parseResult && step >= 1 && (
        <Paper variant="outlined" sx={{ p: 2, bgcolor: '#f0f7ff' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="subtitle2" sx={{ color: '#1e40af' }}>
              🤖 AI解析结果
            </Typography>
            {parseResult.parse_level && (
              <Chip
                label={`解析来源: ${parseResult.parse_level === 'template' ? '模板匹配' : parseResult.parse_level === 'llm' ? 'LLM解析' : parseResult.parse_level === 'rule_engine' ? '规则引擎' : parseResult.parse_level}`}
                size="small"
                sx={{
                  fontSize: '0.7rem',
                  bgcolor: parseResult.parse_level === 'template' ? '#dbeafe' : parseResult.parse_level === 'llm' ? '#ede9fe' : '#fef3c7',
                  color: parseResult.parse_level === 'template' ? '#1e40af' : parseResult.parse_level === 'llm' ? '#6d28d9' : '#92400e',
                }}
              />
            )}
          </Box>

          {parseResult.explanation && (
            <Typography variant="body2" sx={{ mb: 1.5, color: '#374151' }}>
              {parseResult.explanation}
            </Typography>
          )}

          {parseResult.parsed_strategy && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
              <Typography variant="caption" sx={{ color: '#6b7280', width: '100%' }}>
                买入条件：
              </Typography>
              {parseResult.parsed_strategy.entry_conditions.map((cond, idx) => (
                <Chip key={idx} label={cond.signal_id} size="small" color="success" variant="outlined" />
              ))}
              {parseResult.parsed_strategy.entry_conditions.length === 0 && (
                <Typography variant="caption" sx={{ color: '#9ca3af' }}>无</Typography>
              )}
            </Box>
          )}

          {parseResult.parsed_strategy && (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
              <Typography variant="caption" sx={{ color: '#6b7280', width: '100%' }}>
                卖出条件：
              </Typography>
              {parseResult.parsed_strategy.exit_conditions.map((cond, idx) => (
                <Chip key={idx} label={cond.signal_id} size="small" color="error" variant="outlined" />
              ))}
              {parseResult.parsed_strategy.exit_conditions.length === 0 && (
                <Typography variant="caption" sx={{ color: '#9ca3af' }}>无</Typography>
              )}
            </Box>
          )}

          {parseResult.parsed_strategy?.holding_rule && (
            <Box sx={{ display: 'flex', gap: 0.5 }}>
              <Typography variant="caption" sx={{ color: '#6b7280' }}>
                持有规则：
              </Typography>
              <Chip
                label={parseResult.parsed_strategy.holding_rule.name}
                size="small"
                color="warning"
                variant="outlined"
              />
            </Box>
          )}

          {parseResult.warnings.length > 0 && (
            <Box sx={{ mt: 1 }}>
              {parseResult.warnings.map((w, idx) => (
                <Typography key={idx} variant="caption" sx={{ color: '#f59e0b', display: 'block' }}>
                  ⚠️ {w}
                </Typography>
              ))}
            </Box>
          )}
        </Paper>
      )}

      {/* 操作按钮 */}
      <Box sx={{ display: 'flex', gap: 1.5 }}>
        {step === 0 && (
          <Button
            variant="contained"
            size="large"
            startIcon={parsing ? <CircularProgress size={20} color="inherit" /> : <AutoAwesomeIcon />}
            onClick={handleParse}
            disabled={!naturalLanguage.trim() || parsing}
            fullWidth
            sx={{
              bgcolor: '#7c3aed',
              '&:hover': { bgcolor: '#6d28d9' },
              py: 1.5,
            }}
          >
            {parsing ? '解析中...' : 'AI 解析策略'}
          </Button>
        )}

        {step === 1 && (
          <>
            <Button
              variant="contained"
              size="large"
              startIcon={<PlayArrowIcon />}
              onClick={handleRunBacktest}
              disabled={!selectedStock}
              sx={{
                bgcolor: '#1a73e8',
                '&:hover': { bgcolor: '#1557b0' },
                py: 1.5,
                flex: 1,
              }}
            >
              确认并回测
            </Button>
            {user && (
              <Button
                variant="outlined"
                size="large"
                startIcon={saveLoading ? <CircularProgress size={20} color="inherit" /> : <BookmarkIcon />}
                onClick={handleSaveStrategy}
                disabled={!parseResult?.parsed_strategy || saveLoading}
                sx={{ py: 1.5, flex: 1, borderColor: '#d1d5db', color: '#374151' }}
              >
                {saveLoading ? '保存中...' : '保存策略'}
              </Button>
            )}
            <Button
              variant="outlined"
              size="large"
              onClick={handleReset}
              sx={{ py: 1.5 }}
            >
              重新描述
            </Button>
          </>
        )}

        {step === 2 && (
          <Button
            variant="outlined"
            size="large"
            onClick={handleReset}
            fullWidth
            sx={{ py: 1.5 }}
          >
            开始新的回测
          </Button>
        )}
      </Box>

      {/* 错误提示 Snackbar */}
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

      {/* 保存成功 Snackbar */}
      <Snackbar
        open={saveSuccess}
        autoHideDuration={3000}
        onClose={() => setSaveSuccess(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" onClose={() => setSaveSuccess(false)}>
          策略已保存
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
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', minHeight: 400, color: '#9ca3af',
          }}
        >
          <Typography variant="h6" sx={{ mb: 1 }}>📝</Typography>
          <Typography variant="body1">
            输入策略描述，点击"AI解析策略"开始
          </Typography>
        </Box>
      )}

      {result && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {result.stock_name || result.stock_code}
              </Typography>
              <Chip label="自定义策略" size="small" color="secondary" variant="outlined" />
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

          <MetricsDashboard metrics={result.metrics} />
          {result.yearly_stats.length > 0 && <YearlyHeatmap data={result.yearly_stats} />}

          {result.ai_interpretation && (
            <Box sx={{ p: 2.5, bgcolor: '#f0f7ff', borderRadius: 2, border: '1px solid #bfdbfe' }}>
              <Typography variant="subtitle2" sx={{ mb: 1, color: '#1e40af' }}>🤖 AI 解读</Typography>
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

export default CustomStrategy;
