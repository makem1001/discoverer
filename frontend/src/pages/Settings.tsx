/**
 * 发现者（Discoverer）— 设置页
 *
 * 通达信数据目录配置 + 系统状态展示。
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  Typography,
  TextField,
  Button,
  Paper,
  Alert,
  Snackbar,
  CircularProgress,
  Chip,
  Divider,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { useApi } from '../hooks/useApi';
import type { UserSettings, DataSourceStatus } from '../types';

interface SystemStatus {
  tdx_available?: boolean;
  tdx_files_count?: number;
  akshare_available?: boolean;
  signals_count?: number;
  stocks_count?: number;
  initialized?: boolean;
  [key: string]: unknown;
}

const Settings: React.FC = () => {
  const { get, put, loading } = useApi();

  const [tdxDataDir, setTdxDataDir] = useState('');
  const [saving, setSaving] = useState(false);
  const [snackbar, setSnackbar] = useState<{ message: string; severity: 'success' | 'error' } | null>(null);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // 加载用户设置
  useEffect(() => {
    const loadSettings = async () => {
      const res = await get<UserSettings>('/user/settings');
      if (res.code === 0 && res.data) {
        setTdxDataDir(res.data.tdx_data_dir || '');
      }
    };
    loadSettings();
  }, [get]);

  // 加载系统状态
  useEffect(() => {
    const loadStatus = async () => {
      setStatusLoading(true);
      try {
        const res = await get<SystemStatus>('/system/status');
        if (res.code === 0 && res.data) {
          setSystemStatus(res.data);
        }
      } catch {
        // 忽略系统状态加载失败
      } finally {
        setStatusLoading(false);
      }
    };
    loadStatus();
  }, [get]);

  // 保存设置
  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const res = await put<UserSettings>('/user/settings', {
        tdx_data_dir: tdxDataDir,
      });
      if (res.code === 0) {
        setSnackbar({ message: '设置已保存', severity: 'success' });
      } else {
        setSnackbar({ message: res.message || '保存失败', severity: 'error' });
      }
    } catch {
      setSnackbar({ message: '保存失败，请检查网络', severity: 'error' });
    } finally {
      setSaving(false);
    }
  }, [put, tdxDataDir]);

  return (
    <Box sx={{ p: 4, maxWidth: 700, mx: 'auto' }}>
      {/* 页面标题 */}
      <Typography variant="h5" sx={{ fontWeight: 600, mb: 3 }}>
        用户设置
      </Typography>

      {/* 设置表单 */}
      <Paper sx={{ p: 3, mb: 3, borderRadius: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
          通达信数据配置
        </Typography>
        <Typography variant="body2" sx={{ color: '#6b7280', mb: 2 }}>
          配置通达信（TDX）本地数据目录路径，用于读取本地股票日线数据。
          请确保本地已安装通达信并下载了历史日线数据。
        </Typography>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
          <TextField
            fullWidth
            label="通达信数据目录"
            value={tdxDataDir}
            onChange={(e) => setTdxDataDir(e.target.value)}
            placeholder="例如：D:/new_tdx/vipdoc"
            helperText="留空则使用模拟数据或在线数据源"
            disabled={saving}
          />
          <Button
            variant="contained"
            startIcon={saving ? <CircularProgress size={18} color="inherit" /> : <SaveIcon />}
            onClick={handleSave}
            disabled={saving}
            sx={{
              mt: 0.5,
              minWidth: 100,
              bgcolor: '#1a73e8',
              '&:hover': { bgcolor: '#1557b0' },
            }}
          >
            保存
          </Button>
        </Box>
      </Paper>

      {/* 系统状态 */}
      <Paper sx={{ p: 3, borderRadius: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
          数据源状态
        </Typography>

        {statusLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
            <CircularProgress size={24} />
          </Box>
        ) : systemStatus ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {/* TDX 可用状态 */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip
                icon={systemStatus.tdx_available ? <CheckCircleIcon /> : <CancelIcon />}
                label={`TDX 数据: ${systemStatus.tdx_available ? '可用' : '不可用'}`}
                color={systemStatus.tdx_available ? 'success' : 'default'}
                variant="outlined"
                size="small"
              />
              {systemStatus.tdx_files_count !== undefined && (
                <Typography variant="body2" sx={{ color: '#6b7280' }}>
                  文件数量: {systemStatus.tdx_files_count}
                </Typography>
              )}
            </Box>

            {/* akshare 可用状态 */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip
                icon={systemStatus.akshare_available ? <CheckCircleIcon /> : <CancelIcon />}
                label={`AKShare: ${systemStatus.akshare_available ? '可用' : '不可用'}`}
                color={systemStatus.akshare_available ? 'success' : 'default'}
                variant="outlined"
                size="small"
              />
            </Box>

            <Divider sx={{ my: 1 }} />

            {/* 其他状态 */}
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              {systemStatus.signals_count !== undefined && (
                <Typography variant="body2" sx={{ color: '#6b7280' }}>
                  信号数量: {systemStatus.signals_count}
                </Typography>
              )}
              {systemStatus.stocks_count !== undefined && (
                <Typography variant="body2" sx={{ color: '#6b7280' }}>
                  股票数量: {systemStatus.stocks_count}
                </Typography>
              )}
              {systemStatus.initialized !== undefined && (
                <Chip
                  label={systemStatus.initialized ? '已初始化' : '未初始化'}
                  size="small"
                  color={systemStatus.initialized ? 'success' : 'warning'}
                />
              )}
            </Box>
          </Box>
        ) : (
          <Typography variant="body2" sx={{ color: '#9ca3af' }}>
            无法获取系统状态
          </Typography>
        )}
      </Paper>

      {/* Snackbar 提示 */}
      <Snackbar
        open={!!snackbar}
        autoHideDuration={3000}
        onClose={() => setSnackbar(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={snackbar?.severity || 'success'}
          onClose={() => setSnackbar(null)}
          sx={{ width: '100%' }}
        >
          {snackbar?.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Settings;
