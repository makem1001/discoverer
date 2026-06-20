/**
 * 发现者（Discoverer）— 核心指标卡片组件
 *
 * 展示单个回测指标（名称 + 数值 + 格式化）。
 * 数值为百分比时自动 ×100 显示。
 */

import React from 'react';
import { Box, Typography, Tooltip } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

interface ResultCardProps {
  label: string;
  value: number;
  format?: 'percent' | 'number' | 'ratio' | 'integer';
  tooltip?: string;
  color?: 'auto' | 'up' | 'down' | 'neutral';
}

const ResultCard: React.FC<ResultCardProps> = ({
  label,
  value,
  format = 'number',
  tooltip,
  color = 'auto',
}) => {
  const formatValue = (): string => {
    switch (format) {
      case 'percent':
        return `${(value * 100).toFixed(2)}%`;
      case 'ratio':
        return value.toFixed(2);
      case 'integer':
        return String(Math.round(value));
      default:
        return value.toFixed(2);
    }
  };

  const getColor = (): string => {
    if (color === 'up') return '#cf1322';
    if (color === 'down') return '#389e0d';
    if (color === 'neutral') return '#1f2937';
    // auto: positive = red (up), negative = green (down)
    if (value > 0) return '#cf1322';
    if (value < 0) return '#389e0d';
    return '#1f2937';
  };

  return (
    <Box className="metric-card">
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Typography variant="caption" sx={{ color: '#6b7280' }}>
          {label}
        </Typography>
        {tooltip && (
          <Tooltip title={tooltip} arrow placement="top">
            <InfoOutlinedIcon sx={{ fontSize: 14, color: '#9ca3af' }} />
          </Tooltip>
        )}
      </Box>
      <Typography
        className="metric-value"
        sx={{ color: getColor(), fontSize: '1.5rem' }}
      >
        {formatValue()}
      </Typography>
    </Box>
  );
};

export default ResultCard;
