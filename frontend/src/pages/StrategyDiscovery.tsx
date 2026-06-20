/**
 * 发现者（Discoverer）— Tab 3: 策略发现页面
 *
 * 目标选择 → 股票池选择 → 扫描 → Top-20排行榜展示
 */

import React, { useState, useCallback } from 'react';
import {
  Box, Typography, Button, Divider, Alert, Snackbar,
  FormControl, InputLabel, Select, MenuItem, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Paper, LinearProgress,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import SplitPane from '../components/Layout/SplitPane';
import ResultCard from '../components/Common/ResultCard';
import LoadingOverlay from '../components/Common/LoadingOverlay';
import { useApi, useProgressPoll } from '../hooks/useApi';
import type { DiscoveryResult, StrategyScore, Signal } from '../types';

const OBJECTIVE_OPTIONS = [
  { value: 'max_win_rate', label: '最高胜率' },
  { value: 'min_drawdown', label: '最小回撤' },
  { value: 'max_sharpe', label: '最高夏普比率' },
  { value: 'max_profit_loss_ratio', label: '最佳盈亏比' },
];

const POOL_OPTIONS = [
  { value: 'hs300', label: '沪深300 (约300只)' },
  { value: 'zz500', label: '中证500 (约500只)' },
  { value: 'top50', label: '精选50 (快速)' },
];

const StrategyDiscovery: React.FC = () => {
  const [objective, setObjective] = useState('max_win_rate');
  const [poolName, setPoolName] = useState('hs300');
  const [result, setResult] = useState<DiscoveryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<StrategyScore | null>(null);
  const [taskId, setTaskId] = useState('');
  const { post } = useApi();
  const { progress, setProgress } = useProgressPoll(taskId, loading);

  const handleDiscover = useCallback(async () => {
    setLoading(true);
    setError(null);
    setTaskId(`discovery_${Date.now()}`);

    try {
      const res = await post<DiscoveryResult>('/discovery', {
        objective,
        stock_pool: [],
        top_n: 20,
        use_cache: true,
      });

      setProgress(100);

      if (res.code === 0 && res.data) {
        setResult(res.data);
      } else {
        setError(res.message || '策略发现失败');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '扫描请求失败');
    } finally {
      setLoading(false);
      setTimeout(() => setProgress(0), 500);
    }
  }, [objective, setProgress, post]);

  // ── 左侧输入区 ──────────────────────────────────────
  const leftPanel = (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        策略发现
      </Typography>
      <Typography variant="body2" sx={{ color: '#6b7280' }}>
        设定优化目标，系统自动扫描全市场股票，找出历史上表现最好的交易信号。
      </Typography>

      <Divider />

      <FormControl fullWidth>
        <InputLabel id="objective-label">优化目标</InputLabel>
        <Select
          labelId="objective-label"
          value={objective}
          label="优化目标"
          onChange={(e) => setObjective(e.target.value)}
        >
          {OBJECTIVE_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

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
            正在扫描 {progress}% ...
          </Typography>
        </Box>
      )}

      <Button
        variant="contained"
        size="large"
        startIcon={<SearchIcon />}
        onClick={handleDiscover}
        disabled={loading}
        sx={{
          bgcolor: '#1a73e8',
          '&:hover': { bgcolor: '#1557b0' },
          py: 1.5,
        }}
      >
        {loading ? '扫描中...' : '开始扫描'}
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
      <LoadingOverlay visible={loading} message={`正在扫描69个信号...`} />

      {!result && !loading && (
        <Box
          sx={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', minHeight: 400, color: '#9ca3af',
          }}
        >
          <Typography variant="h6" sx={{ mb: 1 }}>🔍</Typography>
          <Typography variant="body1">
            选择优化目标和股票池，点击"开始扫描"
          </Typography>
        </Box>
      )}

      {result && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              策略发现结果
            </Typography>
            <Chip
              label={`Top ${result.rankings.length}`}
              size="small"
              color="primary"
            />
            <Chip
              label={`耗时 ${result.elapsed_ms}ms`}
              size="small"
              variant="outlined"
            />
          </Box>

          {/* 合规提示 */}
          <Alert severity="warning" sx={{ mb: 2 }}>
            ⚠️ 以下排名仅反映信号在历史数据中的统计表现，不构成任何投资建议。
          </Alert>

          {/* 排行榜表格 */}
          <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>排名</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>信号名称</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">胜率</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">年化收益</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">最大回撤</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">交易次数</TableCell>
                  <TableCell sx={{ fontWeight: 600 }} align="right">综合得分</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {result.rankings.map((item, idx) => (
                  <TableRow
                    key={idx}
                    hover
                    selected={selectedSignal?.signal?.id === item.signal?.id}
                    onClick={() => setSelectedSignal(item)}
                    sx={{ cursor: 'pointer' }}
                  >
                    <TableCell>
                      <Chip
                        label={`#${idx + 1}`}
                        size="small"
                        color={idx < 3 ? 'primary' : 'default'}
                        variant={idx < 3 ? 'filled' : 'outlined'}
                      />
                    </TableCell>
                    <TableCell>
                      <Box>
                        <Typography variant="body2" sx={{ fontWeight: 500 }}>
                          {item.signal?.name || '未知'}
                        </Typography>
                        <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                          {item.signal?.category || ''}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <span style={{ color: item.win_rate > 0.5 ? '#cf1322' : '#389e0d' }}>
                        {(item.win_rate * 100).toFixed(1)}%
                      </span>
                    </TableCell>
                    <TableCell align="right">
                      <span style={{ color: item.annual_return > 0 ? '#cf1322' : '#389e0d' }}>
                        {(item.annual_return * 100).toFixed(2)}%
                      </span>
                    </TableCell>
                    <TableCell align="right">
                      {(item.max_drawdown * 100).toFixed(2)}%
                    </TableCell>
                    <TableCell align="right">{item.total_trades}</TableCell>
                    <TableCell align="right">
                      <Chip
                        label={item.score.toFixed(2)}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {/* 选中信号详情 */}
          {selectedSignal && (
            <Paper variant="outlined" sx={{ p: 2.5, bgcolor: '#fafafa' }}>
              <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
                📋 {selectedSignal.signal?.name || '信号'} 详情
              </Typography>
              <Typography variant="body2" sx={{ mb: 1.5, color: '#6b7280' }}>
                {selectedSignal.signal?.description || ''}
              </Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(3, 1fr)' }, gap: 1.5 }}>
                <ResultCard label="胜率" value={selectedSignal.win_rate} format="percent" />
                <ResultCard label="年化收益" value={selectedSignal.annual_return} format="percent" />
                <ResultCard label="最大回撤" value={selectedSignal.max_drawdown} format="percent" color="down" />
              </Box>
            </Paper>
          )}
        </Box>
      )}
    </Box>
  );

  return <SplitPane left={leftPanel} right={rightPanel} />;
};

export default StrategyDiscovery;
