/**
 * 发现者（Discoverer）— 核心指标仪表盘组件
 *
 * 以雷达图 + 进度条形式展示回测核心指标。
 *
 * 响应式：监听窗口 resize 自动调整图表尺寸
 */

import React, { useMemo, useEffect, useRef, useCallback } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { RadarChart } from 'echarts/charts';
import { RadarComponent, TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { Box, Typography, LinearProgress } from '@mui/material';
import type { BacktestMetrics } from '../../types';

echarts.use([
  RadarChart, RadarComponent, TooltipComponent, LegendComponent, CanvasRenderer,
]);

interface MetricsDashboardProps {
  metrics: BacktestMetrics;
}

const MetricsDashboard: React.FC<MetricsDashboardProps> = ({ metrics }) => {
  const chartRef = useRef<ReactEChartsCore | null>(null);

  const handleResize = useCallback(() => {
    chartRef.current?.getEchartsInstance()?.resize();
  }, []);

  useEffect(() => {
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [handleResize]);

  useEffect(() => {
    const timer = setTimeout(handleResize, 100);
    return () => clearTimeout(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const radarOption = useMemo(() => {
    const normalize = (val: number, max: number) => Math.min(Math.max((val / max) * 100, 0), 100);

    const indicators = [
      { name: '总收益', max: 100 },
      { name: '年化收益', max: 100 },
      { name: '抗回撤', max: 100 },
      { name: '胜率', max: 100 },
      { name: '夏普比率', max: 100 },
      { name: '盈亏比', max: 100 },
    ];

    const values = [
      normalize(metrics.total_return, 5.0),
      normalize(metrics.annual_return, 0.5),
      normalize(1 - metrics.max_drawdown, 1.0),
      normalize(metrics.win_rate, 1.0),
      normalize(metrics.sharpe_ratio, 3.0),
      normalize(metrics.profit_loss_ratio, 5.0),
    ];

    return {
      tooltip: {
        trigger: 'item',
      },
      legend: {
        bottom: 0,
        data: ['策略表现'],
        textStyle: { fontSize: 12 },
      },
      radar: {
        indicator: indicators,
        center: ['50%', '48%'],
        radius: '65%',
        axisName: { fontSize: 11, color: '#6b7280' },
        splitArea: {
          areaStyle: { color: ['#fafafa', '#f5f5f5', '#fafafa', '#f5f5f5', '#fafafa'] },
        },
      },
      series: [
        {
          name: '策略表现',
          type: 'radar',
          data: [{ value: values, name: '策略表现' }],
          areaStyle: { color: 'rgba(26, 115, 232, 0.15)' },
          lineStyle: { color: '#1a73e8', width: 2 },
          itemStyle: { color: '#1a73e8' },
          symbol: 'circle',
          symbolSize: 5,
        },
      ],
    };
  }, [metrics]);

  return (
    <Box>
      <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
        指标雷达图
      </Typography>

      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
        {/* 雷达图 */}
        <Box sx={{ flex: '1 1 400px', minWidth: 280, width: '100%' }}>
          <ReactEChartsCore
            ref={chartRef}
            echarts={echarts}
            option={radarOption}
            style={{ height: 320, width: '100%' }}
            notMerge
            lazyUpdate
          />
        </Box>

        {/* 详细进度条 */}
        <Box
          sx={{
            flex: '1 1 280px',
            minWidth: 240,
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            justifyContent: 'center',
          }}
        >
          <MetricBar
            label="总收益率"
            value={metrics.total_return * 100}
            max={500}
            unit="%"
          />
          <MetricBar
            label="年化收益率"
            value={metrics.annual_return * 100}
            max={50}
            unit="%"
          />
          <MetricBar
            label="最大回撤"
            value={metrics.max_drawdown * 100}
            max={80}
            unit="%"
            inverted
          />
          <MetricBar
            label="胜率"
            value={metrics.win_rate * 100}
            max={100}
            unit="%"
          />
          <MetricBar
            label="夏普比率"
            value={metrics.sharpe_ratio}
            max={3.0}
            unit=""
          />
          <MetricBar
            label="盈亏比"
            value={metrics.profit_loss_ratio}
            max={5.0}
            unit=""
          />
        </Box>
      </Box>
    </Box>
  );
};

// ── 辅助组件：指标进度条 ──────────────────────────────

interface MetricBarProps {
  label: string;
  value: number;
  max: number;
  unit: string;
  inverted?: boolean;
}

const MetricBar: React.FC<MetricBarProps> = ({ label, value, max, unit, inverted = false }) => {
  const pct = Math.min(Math.abs(value) / max * 100, 100);
  const isPositive = value > 0;
  const isNegative = value < 0;
  const color = inverted
    ? (value < 0.3 * max ? '#cf1322' : '#389e0d')
    : (isPositive ? '#cf1322' : isNegative ? '#389e0d' : '#6b7280');

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="caption" sx={{ color: '#6b7280' }}>
          {label}
        </Typography>
        <Typography variant="caption" sx={{ fontWeight: 600, color }}>
          {value.toFixed(2)}{unit}
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 8,
          borderRadius: 4,
          bgcolor: '#f3f4f6',
          '& .MuiLinearProgress-bar': {
            bgcolor: color,
            borderRadius: 4,
          },
        }}
      />
    </Box>
  );
};

export default MetricsDashboard;
