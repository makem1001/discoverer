/**
 * 发现者（Discoverer）— 参数网格搜索配置组件
 *
 * 提供二维参数网格搜索的配置界面：
 * - X/Y 轴参数选择（Select 下拉）
 * - 参数范围设定（Range Slider）
 * - 优化目标指标选择
 * - 固定参数配置（Accordion 折叠面板）
 * - 预估组合数显示与验证
 *
 * 类型别名说明：
 * - GridSearchConfig 是 GridSearchRequest（见 types/gridSearch.ts）的参数配置子集，
 *   供 UI 层使用（camelCase 命名）。调用方应在提交前将 GridSearchConfig 映射为
 *   GridSearchRequest 的 x_param / y_param / target_metric / fixed_params 字段
 *   （转换为 snake_case），并补齐 stock_code / strategy_id 后发起请求。
 */

import React, { useState, useMemo, useCallback } from 'react';
import type { ParamRange } from '../../types/gridSearch';
import {
  Paper, Typography, Box, FormControl, InputLabel, Select,
  MenuItem, Slider, Button, Accordion, AccordionSummary,
  AccordionDetails, TextField,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

/* ------------------------------------------------------------------ */
/*  类型定义                                                           */
/* ------------------------------------------------------------------ */

interface ParamOption {
  value: string;
  label: string;
  min: number;
  max: number;
  step: number;
  format: (v: number) => string;
  unit: string;
}

interface GridSearchConfig {
  xParam: { name: string; min: number; max: number; step: number; label: string };
  yParam: { name: string; min: number; max: number; step: number; label: string };
  targetMetric: string;
  fixedParams: Record<string, number>;
}

interface ParamGridConfigProps {
  onSearch: (config: GridSearchConfig) => void;
  loading?: boolean;
  disabled?: boolean;
}

/* ------------------------------------------------------------------ */
/*  常量                                                               */
/* ------------------------------------------------------------------ */

const PARAM_OPTIONS: ParamOption[] = [
  { value: 'stop_loss_pct', label: '止损比例', min: 0, max: 0.2, step: 0.01, format: (v) => `${(v * 100).toFixed(0)}%`, unit: '%' },
  { value: 'stop_profit_pct', label: '止盈比例', min: 0, max: 0.5, step: 0.01, format: (v) => `${(v * 100).toFixed(0)}%`, unit: '%' },
  { value: 'atr_stop_multiplier', label: 'ATR止损倍数', min: 0, max: 5, step: 0.5, format: (v) => (v === 0 ? '关' : `${v}x`), unit: 'x' },
  { value: 'hold_days', label: '持有天数', min: 1, max: 60, step: 1, format: (v) => `${v}天`, unit: '天' },
  { value: 'fixed_position_pct', label: '固定仓位', min: 0.1, max: 1.0, step: 0.1, format: (v) => `${(v * 100).toFixed(0)}%`, unit: '%' },
  { value: 'max_drawdown_limit', label: '回撤熔断', min: 0, max: 0.5, step: 0.01, format: (v) => (v === 0 ? '关' : `${(v * 100).toFixed(0)}%`), unit: '%' },
  { value: 'ma_fast', label: 'MA快线周期', min: 3, max: 50, step: 1, format: (v) => `${v}日`, unit: '日' },
  { value: 'ma_slow', label: 'MA慢线周期', min: 10, max: 200, step: 5, format: (v) => `${v}日`, unit: '日' },
];

const METRIC_OPTIONS: { value: string; label: string; lowerIsBetter: boolean }[] = [
  { value: 'total_return', label: '总收益', lowerIsBetter: false },
  { value: 'annual_return', label: '年化收益', lowerIsBetter: false },
  { value: 'sharpe_ratio', label: '夏普比率', lowerIsBetter: false },
  { value: 'win_rate', label: '胜率', lowerIsBetter: false },
  { value: 'max_drawdown', label: '最大回撤', lowerIsBetter: true },
  { value: 'profit_loss_ratio', label: '盈亏比', lowerIsBetter: false },
];

const DEFAULT_X_PARAM = 'stop_loss_pct';
const DEFAULT_Y_PARAM = 'stop_profit_pct';
const DEFAULT_METRIC = 'total_return';
const MAX_COMBINATIONS_WARN = 500;

/* ------------------------------------------------------------------ */
/*  组件                                                               */
/* ------------------------------------------------------------------ */

const ParamGridConfig: React.FC<ParamGridConfigProps> = ({
  onSearch,
  loading = false,
  disabled = false,
}) => {
  /* ---- 状态 ---- */
  const [xParamName, setXParamName] = useState(DEFAULT_X_PARAM);
  const [xRange, setXRange] = useState<number[]>([0, 0.1]);
  const [yParamName, setYParamName] = useState(DEFAULT_Y_PARAM);
  const [yRange, setYRange] = useState<number[]>([0, 0.2]);
  const [targetMetric, setTargetMetric] = useState(DEFAULT_METRIC);
  const [fixedParams, setFixedParams] = useState<Record<string, number>>({});

  /* ---- 派生数据 ---- */
  const xOption = useMemo(() => PARAM_OPTIONS.find((o) => o.value === xParamName)!, [xParamName]);
  const yOption = useMemo(() => PARAM_OPTIONS.find((o) => o.value === yParamName)!, [yParamName]);

  const isSameParam = xParamName === yParamName;

  const combinationCount = useMemo(() => {
    const xSteps = Math.floor((xRange[1] - xRange[0]) / xOption.step) + 1;
    const ySteps = Math.floor((yRange[1] - yRange[0]) / yOption.step) + 1;
    return xSteps * ySteps;
  }, [xRange, yRange, xOption.step, yOption.step]);

  const isConfigValid = useMemo(() => {
    if (isSameParam) return false;
    if (xRange[0] >= xRange[1]) return false;
    if (yRange[0] >= yRange[1]) return false;
    if (targetMetric === undefined) return false;
    return true;
  }, [isSameParam, xRange, yRange, targetMetric]);

  /* ---- 处理器 ---- */
  const handleXParamChange = useCallback(
    (name: string) => {
      setXParamName(name);
      const opt = PARAM_OPTIONS.find((o) => o.value === name);
      if (opt) setXRange([opt.min, opt.max]);
    },
    [],
  );

  const handleYParamChange = useCallback(
    (name: string) => {
      setYParamName(name);
      const opt = PARAM_OPTIONS.find((o) => o.value === name);
      if (opt) setYRange([opt.min, opt.max]);
    },
    [],
  );

  const handleSearch = useCallback(() => {
    if (!isConfigValid) return;
    onSearch({
      xParam: { name: xParamName, min: xRange[0], max: xRange[1], step: xOption.step, label: xOption.label },
      yParam: { name: yParamName, min: yRange[0], max: yRange[1], step: yOption.step, label: yOption.label },
      targetMetric,
      fixedParams,
    });
  }, [isConfigValid, onSearch, xParamName, xRange, xOption, yParamName, yRange, yOption, targetMetric, fixedParams]);

  const handleReset = useCallback(() => {
    setXParamName(DEFAULT_X_PARAM);
    setYParamName(DEFAULT_Y_PARAM);
    setTargetMetric(DEFAULT_METRIC);
    setFixedParams({});
    const xOpt = PARAM_OPTIONS.find((o) => o.value === DEFAULT_X_PARAM)!;
    const yOpt = PARAM_OPTIONS.find((o) => o.value === DEFAULT_Y_PARAM)!;
    setXRange([xOpt.min, xOpt.max]);
    setYRange([yOpt.min, yOpt.max]);
  }, []);

  const handleFixedParamChange = useCallback(
    (paramName: string, value: number) => {
      setFixedParams((prev) => {
        if (value < 0) {
          // 删除：负值表示移除
          const next = { ...prev };
          delete next[paramName];
          return next;
        }
        return { ...prev, [paramName]: value };
      });
    },
    [],
  );

  /* ---- 渲染辅助 ---- */
  const rangeMarks = useCallback(
    (option: ParamOption, range: number[]) => [
      { value: option.min, label: option.format(option.min) },
      { value: range[0], label: option.format(range[0]) },
      { value: range[1], label: option.format(range[1]) },
      { value: option.max, label: option.format(option.max) },
    ],
    [],
  );

  const availableFixedParams = useMemo(
    () => PARAM_OPTIONS.filter(
      (o) => o.value !== xParamName && o.value !== yParamName,
    ),
    [xParamName, yParamName],
  );

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.5,
        bgcolor: '#fafafa',
        border: '1px solid #e5e7eb',
        borderRadius: 2,
      }}
    >
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: '#1f2937' }}>
        参数网格搜索配置
      </Typography>

      {/* ---- 主配置区域 ---- */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>

        {/* X轴参数 */}
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 500, color: '#374151', display: 'block', mb: 0.75 }}>
            X轴参数
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <FormControl fullWidth size="small">
              <InputLabel>参数名</InputLabel>
              <Select
                value={xParamName}
                label="参数名"
                onChange={(e) => handleXParamChange(e.target.value)}
              >
                {PARAM_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="caption" sx={{ color: '#6b7280' }}>
                  搜索范围
                </Typography>
                <Typography variant="caption" sx={{ color: '#6b7280', fontWeight: 500 }}>
                  {xOption.format(xRange[0])} — {xOption.format(xRange[1])}
                </Typography>
              </Box>
              <Slider
                value={xRange}
                onChange={(_e, val) => setXRange(val as number[])}
                min={xOption.min}
                max={xOption.max}
                step={xOption.step}
                marks={rangeMarks(xOption, xRange)}
                size="small"
                valueLabelDisplay="auto"
                valueLabelFormat={(v) => xOption.format(v)}
                disableSwap
              />
            </Box>
          </Box>
        </Box>

        {/* Y轴参数 */}
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 500, color: '#374151', display: 'block', mb: 0.75 }}>
            Y轴参数
          </Typography>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <FormControl fullWidth size="small" error={isSameParam}>
              <InputLabel>参数名</InputLabel>
              <Select
                value={yParamName}
                label="参数名"
                onChange={(e) => handleYParamChange(e.target.value)}
              >
                {PARAM_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="caption" sx={{ color: '#6b7280' }}>
                  搜索范围
                </Typography>
                <Typography variant="caption" sx={{ color: '#6b7280', fontWeight: 500 }}>
                  {yOption.format(yRange[0])} — {yOption.format(yRange[1])}
                </Typography>
              </Box>
              <Slider
                value={yRange}
                onChange={(_e, val) => setYRange(val as number[])}
                min={yOption.min}
                max={yOption.max}
                step={yOption.step}
                marks={rangeMarks(yOption, yRange)}
                size="small"
                valueLabelDisplay="auto"
                valueLabelFormat={(v) => yOption.format(v)}
                disableSwap
              />
            </Box>
          </Box>
        </Box>

        {/* 相同参数错误提示 */}
        {isSameParam && (
          <Typography variant="caption" sx={{ color: '#cf1322' }}>
            X轴和Y轴不能选择同一个参数
          </Typography>
        )}

        {/* 优化目标 */}
        <Box>
          <Typography variant="caption" sx={{ fontWeight: 500, color: '#374151', display: 'block', mb: 0.75 }}>
            优化目标指标
          </Typography>
          <FormControl fullWidth size="small">
            <InputLabel>指标</InputLabel>
            <Select
              value={targetMetric}
              label="指标"
              onChange={(e) => setTargetMetric(e.target.value)}
            >
              {METRIC_OPTIONS.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2">{opt.label}</Typography>
                    {opt.lowerIsBetter && (
                      <Typography variant="caption" sx={{ color: '#f59e0b' }}>
                        越小越好
                      </Typography>
                    )}
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>

        {/* 预估组合数 */}
        {isConfigValid && (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.5,
              py: 1,
              bgcolor: combinationCount > MAX_COMBINATIONS_WARN ? '#fff7ed' : '#f0fdf4',
              borderRadius: 1,
              border: `1px solid ${combinationCount > MAX_COMBINATIONS_WARN ? '#fed7aa' : '#bbf7d0'}`,
            }}
          >
            <Typography
              variant="body2"
              sx={{
                fontWeight: 500,
                color: combinationCount > MAX_COMBINATIONS_WARN ? '#c2410c' : '#166534',
              }}
            >
              预计运行 {combinationCount} 个组合
            </Typography>
            {combinationCount > MAX_COMBINATIONS_WARN && (
              <Typography variant="caption" sx={{ color: '#c2410c' }}>
                （组合数较多，建议缩小搜索范围）
              </Typography>
            )}
          </Box>
        )}

        {/* 固定参数 Accordion */}
        <Accordion
          defaultExpanded={false}
          sx={{
            border: '1px solid #e5e7eb',
            borderRadius: '8px !important',
            '&:before': { display: 'none' },
            boxShadow: 'none',
          }}
        >
          <AccordionSummary
            expandIcon={<ExpandMoreIcon />}
            sx={{
              bgcolor: '#fafafa',
              borderRadius: '8px',
              minHeight: 40,
              '& .MuiAccordionSummary-content': { margin: '6px 0' },
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                固定参数（可选）
              </Typography>
              {Object.keys(fixedParams).length > 0 && (
                <Typography variant="caption" sx={{ color: '#6b7280' }}>
                  已设置 {Object.keys(fixedParams).length} 项
                </Typography>
              )}
            </Box>
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0.5, pb: 1.5 }}>
            {availableFixedParams.length > 0 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                <Typography variant="caption" sx={{ color: '#6b7280' }}>
                  以下参数不参与搜索，可设为固定值（留空则使用策略默认值）
                </Typography>
                {availableFixedParams.map((param) => (
                  <Box key={param.value}>
                    <TextField
                      label={param.label}
                      type="number"
                      size="small"
                      fullWidth
                      value={
                        fixedParams[param.value] !== undefined
                          ? fixedParams[param.value]
                          : ''
                      }
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '') {
                          handleFixedParamChange(param.value, -1);
                        } else {
                          handleFixedParamChange(param.value, Number(val));
                        }
                      }}
                      InputProps={{
                        inputProps: {
                          min: param.min,
                          max: param.max,
                          step: param.step,
                        },
                        endAdornment: (
                          <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                            {param.unit}
                          </Typography>
                        ),
                      }}
                    />
                  </Box>
                ))}
              </Box>
            ) : (
              <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                所有参数均已参与搜索，无需设置固定参数
              </Typography>
            )}
          </AccordionDetails>
        </Accordion>
      </Box>

      {/* ---- 按钮区域 ---- */}
      <Box sx={{ display: 'flex', gap: 1.5, mt: 3, justifyContent: 'flex-end' }}>
        <Button
          variant="outlined"
          size="small"
          onClick={handleReset}
          disabled={disabled}
          sx={{
            borderColor: '#d1d5db',
            color: '#6b7280',
            textTransform: 'none',
            '&:hover': {
              borderColor: '#9ca3af',
              bgcolor: '#f3f4f6',
            },
          }}
        >
          重置
        </Button>
        <Button
          variant="contained"
          size="small"
          onClick={handleSearch}
          disabled={!isConfigValid || loading || disabled}
          sx={{
            bgcolor: '#1a73e8',
            textTransform: 'none',
            '&:hover': { bgcolor: '#1557b0' },
            '&.Mui-disabled': { bgcolor: '#e5e7eb', color: '#9ca3af' },
          }}
        >
          {loading ? '搜索中...' : '开始网格搜索'}
        </Button>
      </Box>
    </Paper>
  );
};

export default ParamGridConfig;
export type { GridSearchConfig, ParamGridConfigProps };
// Re-export ParamRange from types/gridSearch.ts for convenience
export type { ParamRange };
