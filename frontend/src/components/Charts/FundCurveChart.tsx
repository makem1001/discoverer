/**
 * 发现者（Discoverer）— 资金曲线图组件
 *
 * 使用 ECharts 渲染：
 *  - 资金曲线（面积图）
 *  - 回撤区域（下半部分）
 *
 * 响应式：监听窗口 resize 自动调整图表尺寸
 */

import React, { useMemo, useEffect, useRef, useCallback } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { LineChart, BarChart } from 'echarts/charts';
import {
  GridComponent, TooltipComponent, LegendComponent, DataZoomComponent,
  TitleComponent, MarkLineComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { Box, Typography } from '@mui/material';
import type { EquityPoint } from '../../types';

echarts.use([
  LineChart, BarChart, GridComponent, TooltipComponent,
  LegendComponent, DataZoomComponent, TitleComponent,
  MarkLineComponent, CanvasRenderer,
]);

interface FundCurveChartProps {
  data: EquityPoint[];
  title?: string;
  ddBreached?: boolean;
}

const FundCurveChart: React.FC<FundCurveChartProps> = ({ data, title = '资金曲线', ddBreached = false }) => {
  const chartRef = useRef<ReactEChartsCore | null>(null);

  const handleResize = useCallback(() => {
    chartRef.current?.getEchartsInstance()?.resize();
  }, []);

  useEffect(() => {
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [handleResize]);

  // 在组件挂载或布局变化时主动触发一次 resize
  useEffect(() => {
    const timer = setTimeout(handleResize, 100);
    return () => clearTimeout(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const option = useMemo(() => {
    const dates = data.map((d) => d.date);
    const equity = data.map((d) => d.equity);
    const drawdown = data.map((d) => d.drawdown * 100);

    const initialEquity = equity[0] || 100000;

    const ddBreachMarkLines: object[] = [];
    if (ddBreached) {
      let maxDD = 0;
      let ddDate = '';
      for (let i = 0; i < data.length; i++) {
        if (data[i].drawdown > maxDD) {
          maxDD = data[i].drawdown;
          ddDate = data[i].date;
        }
      }
      if (ddDate) {
        ddBreachMarkLines.push({
          xAxis: ddDate,
          lineStyle: { color: '#ef4444', type: 'dashed' as const, width: 2 },
          label: {
            formatter: '⚠ 熔断',
            position: 'start',
            color: '#ef4444',
            fontSize: 11,
          },
        });
      }
    }

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: Array<{ seriesName: string; value: number; axisValue: string }>) => {
          let html = `<div style="font-weight:600;margin-bottom:4px">${params[0]?.axisValue || ''}</div>`;
          for (const p of params) {
            if (p.seriesName === '回撤') {
              html += `<div>${p.seriesName}: ${p.value.toFixed(2)}%</div>`;
            } else if (p.seriesName === '资金') {
              html += `<div>${p.seriesName}: ¥${p.value.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}</div>`;
            }
          }
          return html;
        },
      },
      legend: {
        data: ['资金', '回撤'],
        bottom: 0,
        textStyle: { fontSize: 12 },
      },
      grid: [
        { left: 60, right: 20, top: 20, height: '60%' },
        { left: 60, right: 20, top: '72%', height: '18%' },
      ],
      xAxis: [
        {
          type: 'category',
          data: dates,
          gridIndex: 0,
          axisLabel: { show: false },
          axisLine: { lineStyle: { color: '#e5e7eb' } },
        },
        {
          type: 'category',
          data: dates,
          gridIndex: 1,
          axisLabel: {
            fontSize: 10,
            color: '#9ca3af',
            formatter: (value: string) => {
              const d = new Date(value);
              return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
            },
            interval: Math.floor(dates.length / 6),
          },
        },
      ],
      yAxis: [
        {
          gridIndex: 0,
          type: 'value',
          axisLabel: {
            formatter: (value: number) => `¥${(value / 10000).toFixed(0)}万`,
            fontSize: 11,
          },
          splitLine: { lineStyle: { color: '#f3f4f6' } },
        },
        {
          gridIndex: 1,
          type: 'value',
          axisLabel: { formatter: '{value}%', fontSize: 11 },
          splitLine: { lineStyle: { color: '#f3f4f6' } },
          inverse: true,
        },
      ],
      dataZoom: [
        {
          type: 'slider',
          xAxisIndex: [0, 1],
          bottom: 30,
          height: 20,
          borderColor: '#e5e7eb',
          fillerColor: 'rgba(26, 115, 232, 0.1)',
          handleStyle: { color: '#1a73e8' },
        },
      ],
      series: [
        {
          name: '资金',
          type: 'line',
          data: equity,
          smooth: true,
          symbol: 'none',
          lineStyle: { color: '#1a73e8', width: 2 },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(26, 115, 232, 0.2)' },
              { offset: 1, color: 'rgba(26, 115, 232, 0.02)' },
            ]),
          },
          markLine: {
            silent: true,
            data: [
              { yAxis: initialEquity, label: { formatter: '初始资金' }, lineStyle: { color: '#9ca3af', type: 'dashed' } },
              ...ddBreachMarkLines,
            ],
          },
          xAxisIndex: 0,
          yAxisIndex: 0,
        },
        {
          name: '回撤',
          type: 'line',
          data: drawdown,
          symbol: 'none',
          lineStyle: { color: '#ef4444', width: 1, type: 'dashed' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(239, 68, 68, 0.15)' },
              { offset: 1, color: 'rgba(239, 68, 68, 0.0)' },
            ]),
          },
          xAxisIndex: 1,
          yAxisIndex: 1,
        },
      ],
    };
  }, [data, ddBreached]);

  if (data.length === 0) {
    return (
      <Box sx={{ p: 4, textAlign: 'center', color: '#9ca3af' }}>
        <Typography variant="body2">暂无资金曲线数据</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {title}
      </Typography>
      <ReactEChartsCore
        ref={chartRef}
        echarts={echarts}
        option={option}
        style={{ height: 400, width: '100%' }}
        notMerge
        lazyUpdate
      />
    </Box>
  );
};

export default FundCurveChart;
