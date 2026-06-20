/**
 * 发现者（Discoverer）— 参数网格搜索热力图组件
 *
 * 使用 ECharts HeatmapChart 展示双参数网格搜索的结果。
 * X轴/Y轴分别代表两个参数的不同取值，颜色映射目标指标。
 *
 * 响应式：监听窗口 resize 自动调整图表尺寸
 */

import React, { useMemo, useEffect, useRef, useCallback } from 'react';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { Box, Typography, CircularProgress } from '@mui/material';

echarts.use([
  HeatmapChart,
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

interface ParamHeatmapProps {
  /** 热力图数据：[[xIdx, yIdx, targetValue], ...] */
  data: number[][];
  /** X轴标签（参数值） */
  xLabels: string[];
  /** Y轴标签（参数值） */
  yLabels: string[];
  /** X轴参数名 */
  xName: string;
  /** Y轴参数名 */
  yName: string;
  /** 目标指标名 */
  metricName: string;
  /** 点击某个 cell 的回调 */
  onCellClick?: (xLabel: string, yLabel: string, value: number) => void;
  /** 加载状态 */
  loading?: boolean;
  /** 图表高度 */
  height?: number;
}

const ParamHeatmap: React.FC<ParamHeatmapProps> = ({
  data,
  xLabels,
  yLabels,
  xName,
  yName,
  metricName,
  onCellClick,
  loading = false,
  height = 400,
}) => {
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

  const handleClick = useCallback(
    (params: any) => {
      if (!onCellClick || !params.data) return;
      const [xIdx, yIdx, value] = params.data as number[];
      onCellClick(xLabels[xIdx], yLabels[yIdx], value);
    },
    [onCellClick, xLabels, yLabels],
  );

  const option = useMemo(() => {
    if (data.length === 0) return {};

    const values = data.map((d) => d[2]);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);

    return {
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const [xIdx, yIdx, value] = params.data as number[];
          return `${xName}: ${xLabels[xIdx]}<br/>${yName}: ${yLabels[yIdx]}<br/>${metricName}: ${(value * 100).toFixed(2)}%`;
        },
      },
      grid: {
        left: 80,
        right: 60,
        top: 40,
        bottom: 80,
      },
      xAxis: {
        type: 'category',
        data: xLabels,
        name: xName,
        nameLocation: 'center',
        nameGap: 50,
        splitArea: { show: true },
      },
      yAxis: {
        type: 'category',
        data: yLabels,
        name: yName,
        nameLocation: 'center',
        nameGap: 60,
        splitArea: { show: true },
      },
      visualMap: {
        min: minValue,
        max: maxValue,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: {
          // 从绿（差）到黄（中）到红（好），中国习惯红涨绿跌
          color: ['#389e0d', '#fadb14', '#cf1322'],
        },
        formatter: (value: number) => `${(value * 100).toFixed(1)}%`,
      },
      series: [
        {
          name: metricName,
          type: 'heatmap',
          data,
          label: {
            show: true,
            formatter: (params: any) => `${(params.data[2] * 100).toFixed(1)}%`,
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };
  }, [data, xLabels, yLabels, xName, yName, metricName]);

  if (!loading && data.length === 0) {
    return (
      <Box
        sx={{
          p: 4,
          textAlign: 'center',
          color: '#6b7280',
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography variant="body2">暂无数据</Typography>
      </Box>
    );
  }

  if (loading) {
    return (
      <Box
        sx={{
          p: 4,
          textAlign: 'center',
          color: '#6b7280',
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'column',
          gap: 1,
        }}
      >
        <CircularProgress size={24} />
        <Typography variant="body2">加载中...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>
        {xName} × {yName} 参数热力图
      </Typography>
      <ReactEChartsCore
        ref={chartRef}
        echarts={echarts}
        option={option}
        style={{ height, width: '100%' }}
        notMerge
        lazyUpdate
        onEvents={{ click: handleClick }}
      />
    </Box>
  );
};

export default ParamHeatmap;
