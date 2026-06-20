/**
 * 发现者（Discoverer）— 我的策略列表页
 *
 * 展示用户保存的策略，支持查看/编辑/删除/立即回测。
 */

import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  CardActions,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Chip,
  Alert,
  Snackbar,
  CircularProgress,
  IconButton,
  Tooltip,
  Collapse,
  Paper,
  Divider,
  Grid,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { useApi } from '../hooks/useApi';
import type { SavedStrategy, SignalCondition } from '../types';

const MyStrategies: React.FC = () => {
  const navigate = useNavigate();
  const { get, del, loading, error, setError } = useApi();

  const [strategies, setStrategies] = useState<SavedStrategy[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<SavedStrategy | null>(null);
  const [snackbar, setSnackbar] = useState<string | null>(null);

  // 加载策略列表
  const loadStrategies = useCallback(async () => {
    const res = await get<SavedStrategy[]>('/strategies');
    if (res.code === 0 && res.data) {
      setStrategies(res.data);
    }
  }, [get]);

  useEffect(() => {
    loadStrategies();
  }, [loadStrategies]);

  // 展开/收起详情
  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  // 删除确认
  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    const res = await del(`/strategies/${deleteTarget.id}`);
    if (res.code === 0) {
      setSnackbar('策略已删除');
      setStrategies((prev) => prev.filter((s) => s.id !== deleteTarget.id));
    } else {
      setSnackbar(res.message || '删除失败');
    }
    setDeleteTarget(null);
  };

  // 立即回测
  const handleQuickBacktest = (strategy: SavedStrategy) => {
    navigate(
      `/custom?strategy_name=${encodeURIComponent(strategy.name)}&` +
      `raw_text=${encodeURIComponent(strategy.raw_text || '')}&` +
      `entry_conditions=${encodeURIComponent(JSON.stringify(strategy.entry_conditions))}&` +
      `exit_conditions=${encodeURIComponent(JSON.stringify(strategy.exit_conditions))}&` +
      `holding_rule=${encodeURIComponent(JSON.stringify(strategy.holding_rule))}`
    );
  };

  // 格式化时间
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

  // 获取条件展示文本
  const conditionLabel = (c: SignalCondition) => {
    const opLabels: Record<string, string> = {
      cross_above: '上穿',
      cross_below: '下穿',
      gt: '>',
      lt: '<',
      eq: '=',
    };
    const op = opLabels[c.operator] || c.operator;
    if (c.operator === 'cross_above' || c.operator === 'cross_below') {
      return `${c.signal_id} ${op}`;
    }
    return `${c.signal_id} ${op} ${c.threshold}`;
  };

  // ── 空状态 ──────────────────────────────────────────
  if (!loading && strategies.length === 0) {
    return (
      <Box sx={{ p: 4, maxWidth: 800, mx: 'auto' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h5" sx={{ fontWeight: 600 }}>
            我的策略
          </Typography>
        </Box>
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
            📋
          </Typography>
          <Typography variant="body1" sx={{ color: '#9ca3af', mb: 2 }}>
            暂无保存的策略，去创建第一个策略吧！
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => navigate('/custom')}
            sx={{ bgcolor: '#1a73e8', '&:hover': { bgcolor: '#1557b0' } }}
          >
            新建策略
          </Button>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 900, mx: 'auto' }}>
      {/* 页面标题 */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" sx={{ fontWeight: 600 }}>
          我的策略
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/custom')}
          sx={{ bgcolor: '#1a73e8', '&:hover': { bgcolor: '#1557b0' } }}
        >
          新建策略
        </Button>
      </Box>

      {/* 加载状态 */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
          <CircularProgress />
        </Box>
      )}

      {/* 策略卡片列表 */}
      {strategies.map((strategy) => (
        <Card
          key={strategy.id}
          sx={{
            mb: 2,
            borderRadius: 2,
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
            border: '1px solid #f0f0f0',
          }}
        >
          <CardContent sx={{ pb: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Box sx={{ flex: 1 }}>
                <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '1.05rem' }}>
                  {strategy.name}
                </Typography>
                {strategy.description && (
                  <Typography
                    variant="body2"
                    sx={{ color: '#6b7280', mt: 0.5, lineHeight: 1.5 }}
                  >
                    {strategy.description}
                  </Typography>
                )}
              </Box>
              <Box sx={{ display: 'flex', gap: 0.5, ml: 2, flexShrink: 0 }}>
                <Tooltip title="查看详情" arrow>
                  <IconButton size="small" onClick={() => toggleExpand(strategy.id)}>
                    {expandedId === strategy.id ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </IconButton>
                </Tooltip>
                <Tooltip title="编辑" arrow>
                  <IconButton size="small" color="primary">
                    <EditIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="立即回测" arrow>
                  <IconButton
                    size="small"
                    sx={{ color: '#1a73e8' }}
                    onClick={() => handleQuickBacktest(strategy)}
                  >
                    <PlayArrowIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="删除" arrow>
                  <IconButton
                    size="small"
                    color="error"
                    onClick={() => setDeleteTarget(strategy)}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>

            {/* 时间信息 */}
            <Box sx={{ display: 'flex', gap: 2, mt: 1 }}>
              <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                创建于 {formatDate(strategy.created_at)}
              </Typography>
              <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                更新于 {formatDate(strategy.updated_at)}
              </Typography>
            </Box>
          </CardContent>

          {/* 展开详情 */}
          <Collapse in={expandedId === strategy.id}>
            <Divider />
            <Box sx={{ p: 2, bgcolor: '#fafafa' }}>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                    买入条件
                  </Typography>
                  {strategy.entry_conditions.length > 0 ? (
                    strategy.entry_conditions.map((c, idx) => (
                      <Chip
                        key={idx}
                        label={conditionLabel(c)}
                        size="small"
                        color="success"
                        variant="outlined"
                        sx={{ mr: 0.5, mb: 0.5 }}
                      />
                    ))
                  ) : (
                    <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                      无
                    </Typography>
                  )}
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                    卖出条件
                  </Typography>
                  {strategy.exit_conditions.length > 0 ? (
                    strategy.exit_conditions.map((c, idx) => (
                      <Chip
                        key={idx}
                        label={conditionLabel(c)}
                        size="small"
                        color="error"
                        variant="outlined"
                        sx={{ mr: 0.5, mb: 0.5 }}
                      />
                    ))
                  ) : (
                    <Typography variant="body2" sx={{ color: '#9ca3af' }}>
                      无
                    </Typography>
                  )}
                </Grid>
                {strategy.holding_rule && (
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                      持有规则
                    </Typography>
                    <Typography variant="body2">
                      {strategy.holding_rule.name} — {strategy.holding_rule.description}
                    </Typography>
                  </Grid>
                )}
                {strategy.raw_text && (
                  <Grid item xs={12}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                      原始描述
                    </Typography>
                    <Typography variant="body2" sx={{ color: '#6b7280' }}>
                      {strategy.raw_text}
                    </Typography>
                  </Grid>
                )}
              </Grid>
            </Box>
          </Collapse>
        </Card>
      ))}

      {/* 删除确认 Dialog */}
      <Dialog open={!!deleteTarget} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>确认删除</DialogTitle>
        <DialogContent>
          <DialogContentText>
            确定要删除策略「{deleteTarget?.name}」吗？此操作不可撤销。
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>取消</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            删除
          </Button>
        </DialogActions>
      </Dialog>

      {/* Snackbar 提示 */}
      <Snackbar
        open={!!snackbar}
        autoHideDuration={3000}
        onClose={() => setSnackbar(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="success" onClose={() => setSnackbar(null)} sx={{ width: '100%' }}>
          {snackbar}
        </Alert>
      </Snackbar>

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
  );
};

export default MyStrategies;
