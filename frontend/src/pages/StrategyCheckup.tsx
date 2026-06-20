/**
 * 发现者（Discoverer）— Tab 4: 策略体检页面
 *
 * 信号组合选择 → 股票池选择 → 验证 → 统计仪表盘 + AI体检报告
 */

import React, { useState, useCallback } from 'react';
import {
  Box, Typography, Button, Divider, Alert, Snackbar,
  FormControl, InputLabel, Select, MenuItem, Chip,
  LinearProgress,
} from '@mui/material';
import ScienceIcon from '@mui/icons-material/Science';
import SplitPane from '../components/Layout/SplitPane';
import SignalTagInput from '../components/Common/SignalTagInput';
import ResultCard from '../components/Common/ResultCard';
import LoadingOverlay from '../components/Common/LoadingOverlay';
import YearlyHeatmap from '../components/Charts/YearlyHeatmap';
import { useApi, useProgressPoll } from '../hooks/useApi';
import type { CheckupResult } from '../types';

const POOL_OPTIONS = [
  { value: 'hs300', label: '沪深300 (约300只)' },
  { value: 'zz500', label: '中证500 (约500只)' },
  { value: 'top50', label: '精选50 (快速)' },
];

const StrategyCheckup: React.FC = () => {
  const [signalIds, setSignalIds] = useState<string[]>([]);
  const [poolName, setPoolName] = useState('hs300');
  const [result, setResult] = useState<CheckupResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState('');
  const { post } = useApi();
  const { progress, setProgress } = useProgressPoll(taskId, loading);

  const handleCheckup = useCallback(async () => {
    if (signalIds.length === 0) {
      setError('请至少选择一个信号');
      return;
    }

    setLoading(true);
    setError(null);
    setTaskId(`checkup_${Date.now()}`);

    try {
      const res = await post<CheckupResult>('/checkup', {
        signal_ids: signalIds,
        stock_pool: [],
      });

      setProgress(100);

      if (res.code === 0 && res.data) {
        setResult(res.data);
      } else {
        setError(res.message || '策略体检失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '体检请求失败');
    } finally {
      setLoading(false);
      setTimeout(() => setProgress(0), 500);
    }
  }, [signalIds, setProgress, post]);

  // ── 左侧输入区 ──────────────────────────────────────
  const leftPanel = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        策略体检
      </Typography>
      <Typography variant="body2" sx={{ color: '#6b7280' }}>
        选择一组交易信号，验证它们在A股全市场的历史表现。
        用数据破除"神策略"迷信。
      </Typography>

      <Divider />

      <SignalTagInput
        value={signalIds}
        onChange={setSignalIds}
        label="选择验证信号"
      />

      <FormControl fullWidth>
        <InputLabel id="pool-label">股票池</InputLabel>
        <Select
          labelId="pool-label"
          value={poolName}
          label="股票池"
          onChange={(e) => setPoolName(e.target.value)}
        >
          {POOL_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {loading && (
        <Box>
          <LinearProgress variant="determinate" value={progress} sx={{ mb: 1, borderRadius: 2 }} />
          <Typography variant="caption" sx={{ color: '#6b7280' }}>
            正在验证 {progress}% ...
          </Typography>
        </Box>
      )}

      <Button
        variant="contained"
        size="large"
        startIcon={<ScienceIcon />}
        onClick={handleCheckup}
        disabled={signalIds.length === 0 || loading}
        sx={{
          bgcolor: '#1a73e8',
          '&:hover': { bgcolor: '#1557b0' },
          py: 1.5,
        }}
      >
        {loading ? '验证中...' : '开始验证'}
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
      <LoadingOverlay visible={loading} message="正在全市场验证..." />

      {!result && !loading && (
        <Box
          sx={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', minHeight: 400, color: '#9ca3af',
          }}
        >
          <Typography variant="h6" sx={{ mb: 1 }}>🔬</Typography>
          <Typography variant="body1">
            选择信号组合，点击"开始验证"
          </Typography>
        </Box>
      )}

      {result && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              策略体检报告
            </Typography>
            <Chip
              label={`${result.signal_ids.length}个信号`}
              size="small"
              color="primary"
            />
          </Box>

          {/* 统计仪表盘 */}
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
            <ResultCard label="触发概率" value={result.trigger_rate} format="percent" color="neutral" />
            <ResultCard label="触发后胜率" value={result.win_rate} format="percent" />
            <ResultCard label="平均收益" value={result.avg_return} format="percent" />
            <ResultCard label="最佳收益" value={result.best_return} format="percent" color="up" />
            <ResultCard label="最差收益" value={result.worst_return} format="percent" color="down" />
            <ResultCard
              label="触发次数"
              value={result.triggered}
              format="integer"
              color="neutral"
              tooltip={`共测试 ${result.total_tests} 次`}
            />
          </Box>

          {/* 逐年分布 */}
          {result.yearly_distribution.length > 0 && (
            <YearlyHeatmap data={result.yearly_distribution} />
          )}

          {/* AI体检报告 */}
          {result.ai_report && (
            <Box
              sx={{
                p: 2.5,
                bgcolor: '#fefce8',
                borderRadius: 2,
                border: '1px solid #fde68a',
              }}
            >
              <Typography variant="subtitle2" sx={{ mb: 1, color: '#a16207' }}>
                🩺 AI 体检报告
              </Typography>
              <Typography variant="body2" sx={{ color: '#374151', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                {result.ai_report}
              </Typography>
            </Box>
          )}

          {/* 风险提示 */}
          <Alert severity="warning" variant="outlined">
            历史表现不代表未来收益。以上统计数据仅供参考，不构成任何投资建议。
          </Alert>
        </Box>
      )}
    </Box>
  );

  return <SplitPane left={leftPanel} right={rightPanel} />;
};

export default StrategyCheckup;
