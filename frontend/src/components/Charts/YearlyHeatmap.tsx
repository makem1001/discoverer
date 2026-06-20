/**
 * 发现者（Discoverer）— 逐年收益热力图/柱状图组件
 *
 * 展示每个年份的收益率、交易次数和胜率。
 *
 * 响应式：监听窗口 resize 自动调整图表尺寸
 */

import React, { useMemo, useEffect, useRef, useCallback } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { BarChart } from 'echarts/charts';
import {
  GridComponent, TooltipComponent, LegendComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { Box, Typography } from '@mui/material';
import type { YearlyStat } from '../../types';

echarts.use([
  BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer,
]);

interface YearlyHeatmapProps {
  data: YearlyStat[];
}

const YearlyHeatmap: React.FC<YearlyHeatmapProps> = ({ data }) => {
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

  const option = useMemo(() => {
    const years = data.map((d) => String(d.year));
    const returns = data.map((d) => d.return_pct * 100);
    const trades = data.map((d) => d.trades);
    const winRates = data.map((d) => d.win_rate * 100);

    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: Array<{ seriesName: string; value: number; axisValue: string }>) => {
          let html = `<div style="font-weight:600;margin-bottom:4px">${params[0]?.axisValue || ''}年</div>`;
          for (const p of params) {
            const unit = p.seriesName === '交易次数' ? '次' : '%';
            html += `<div>${p.seriesName}: ${p.value.toFixed(p.seriesName === '交易次数' ? 0 : 1)}${unit}</div>`;
          }
          return html;
        },
      },
      legend: {
        data: ['收益率', '胜率', '交易次数'],
        bottom: 0,
        textStyle: { fontSize: 12 },
      },
      grid: {
        left: 50,
        right: 50,
        top: 10,
        bottom: 35,
      },
      xAxis: {
        type: 'category',
        data: years,
        axisLabel: { fontSize: 11 },
      },
      yAxis: [
        {
          type: 'value',
          name: '%',
          axisLabel: { formatter: '{value}%', fontSize: 11 },
          splitLine: { lineStyle: { color: '#f3f4f6' } },
        },
        {
          type: 'value',
          name: '次',
          axisLabel: { fontSize: 11 },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '收益率',
          type: 'bar',
          data: returns.map((v) => ({
            value: v,
            itemStyle: { color: v >= 0 ? '#cf1322' : '#389e0d' },
          })),
          barWidth: '40%',
        },
        {
          name: '胜率',
          type: 'line',
          data: winRates,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { color: '#1a73e8', width: 2 },
          itemStyle: { color: '#1a73e8' },
        },
        {
          name: '交易次数',
          type: 'line',
          yAxisIndex: 1,
          data: trades,
          smooth: true,
          symbol: 'diamond',
          symbolSize: 6,
          lineStyle: { color: '#f59e0b', width: 2, type: 'dashed' },
          itemStyle: { color: '#f59e0b' },
        },
      ],
    };
  }, [data]);

  if (data.length === 0) {
    return (
      <Box sx={{ p: 4, textAlign: 'center', color: '#9ca3af' }}>
        <Typography variant="body2">暂无逐年数据</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        逐年收益分布
      </Typography>
      <ReactEChartsCore
        ref={chartRef}
        echarts={echarts}
        option={option}
        style={{ height: 300, width: '100%' }}
        notMerge
        lazyUpdate
      />
    </Box>
  );
};

export default YearlyHeatmap;
