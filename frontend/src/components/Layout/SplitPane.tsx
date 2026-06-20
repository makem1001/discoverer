/**
 * 发现者（Discoverer）— 左右分栏布局容器
 *
 * 左栏：输入区（固定宽度 420px）
 * 右栏：结果区（自适应剩余空间）
 *
 * 响应式适配：
 * - 桌面端（≥768px）：左右分栏，左栏固定 420px
 * - 移动端（<768px）：上下布局，左栏全宽可折叠
 */

import React, { ReactNode, useState } from 'react';
import {
  Box, Paper, IconButton, useMediaQuery, Theme,
} from '@mui/material';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';

interface SplitPaneProps {
  left: ReactNode;
  right: ReactNode;
  leftWidth?: number;
}

const SplitPane: React.FC<SplitPaneProps> = ({ left, right, leftWidth = 420 }) => {
  const isMobile = useMediaQuery((theme: Theme) => theme.breakpoints.down('md'));
  const [leftOpen, setLeftOpen] = useState(true);

  // ── 桌面端：保持原有左右分栏 ──
  if (!isMobile) {
    return (
      <Box
        sx={{
          display: 'flex',
          height: '100%',
          overflow: 'hidden',
        }}
      >
        <Paper
          elevation={0}
          sx={{
            width: leftWidth,
            minWidth: leftWidth,
            borderRight: '1px solid #e5e7eb',
            overflow: 'auto',
            p: 3,
            bgcolor: '#fafafa',
          }}
        >
          {left}
        </Paper>

        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            p: 3,
            bgcolor: '#ffffff',
          }}
        >
          {right}
        </Box>
      </Box>
    );
  }

  // ── 移动端：上下布局，左栏可折叠 ──
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* 左栏 - 可折叠 */}
      <Box
        sx={{
          borderBottom: '1px solid #e5e7eb',
          bgcolor: '#fafafa',
          transition: 'max-height 0.3s ease',
        }}
      >
        {/* 折叠/展开按钮 */}
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            py: 0.5,
            bgcolor: '#f3f4f6',
            borderBottom: leftOpen ? '1px solid #e5e7eb' : 'none',
          }}
        >
          <IconButton
            size="small"
            onClick={() => setLeftOpen(!leftOpen)}
            aria-label={leftOpen ? '收起输入区' : '展开输入区'}
            sx={{ borderRadius: 1 }}
          >
            {leftOpen ? (
              <KeyboardArrowUpIcon fontSize="small" />
            ) : (
              <KeyboardArrowDownIcon fontSize="small" />
            )}
          </IconButton>
        </Box>

        {/* 左栏内容 */}
        {leftOpen && (
          <Box sx={{ p: 2, overflow: 'auto', maxHeight: '50vh' }}>
            {left}
          </Box>
        )}
      </Box>

      {/* 右栏 - 结果区 */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 2,
          bgcolor: '#ffffff',
        }}
      >
        {right}
      </Box>
    </Box>
  );
};

export default SplitPane;
