/**
 * 发现者（Discoverer）— 加载覆盖层组件
 *
 * 全屏半透明遮罩 + 居中加载指示器 + 进度文字。
 */

import React from 'react';
import { Box, CircularProgress, Typography, Fade } from '@mui/material';

interface LoadingOverlayProps {
  visible: boolean;
  message?: string;
}

const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  visible,
  message = '正在计算...',
}) => {
  return (
    <Fade in={visible}>
      <Box
        sx={{
          position: 'absolute',
          inset: 0,
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'rgba(255, 255, 255, 0.85)',
          backdropFilter: 'blur(4px)',
        }}
      >
        <CircularProgress size={48} sx={{ color: '#1a73e8', mb: 2 }} />
        <Typography variant="body1" sx={{ color: '#4b5563', fontWeight: 500 }}>
          {message}
        </Typography>
      </Box>
    </Fade>
  );
};

export default LoadingOverlay;
