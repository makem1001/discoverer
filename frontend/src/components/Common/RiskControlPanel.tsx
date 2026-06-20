/**
 * 发现者（Discoverer）— 风控面板组件
 *
 * MUI Accordion（默认折叠），内含：
 *  - ATR 止损倍数 Slider
 *  - 固定止盈比例 TextField
 *  - 仓位模式 Select
 *  - 固定仓位比例 TextField（条件显示）
 *  - 最大仓位上限 TextField
 *  - 最大回撤熔断 TextField
 */

import React, { useCallback } from 'react';
import {
  Accordion, AccordionSummary, AccordionDetails,
  Typography, Box, Slider, TextField, Select, MenuItem,
  FormControl, InputLabel, Tooltip, IconButton,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import type { RiskControlParams } from '../../types';

interface RiskControlPanelProps {
  riskControl: RiskControlParams;
  onChange: (rc: RiskControlParams) => void;
}

const DEFAULT_RISK_CONTROL: RiskControlParams = {
  atr_stop_multiplier: 0,
  take_profit_pct: 0,
  position_sizing: 'full',
  fixed_position_pct: 0.3,
  max_position_pct: 0.5,
  max_drawdown_limit: 0,
};

const POSITION_SIZING_OPTIONS = [
  { value: 'full', label: '满仓' },
  { value: 'kelly', label: '凯利公式' },
  { value: 'half_kelly', label: '半凯利' },
  { value: 'fixed_pct', label: '固定比例' },
] as const;

const RiskControlPanel: React.FC<RiskControlPanelProps> = ({ riskControl, onChange }) => {
  const updateField = useCallback(
    <K extends keyof RiskControlParams>(field: K, value: RiskControlParams[K]) => {
      onChange({ ...riskControl, [field]: value });
    },
    [riskControl, onChange],
  );

  const hasActiveRiskControls =
    riskControl.atr_stop_multiplier > 0 ||
    riskControl.take_profit_pct > 0 ||
    riskControl.position_sizing !== 'full' ||
    riskControl.max_drawdown_limit > 0 ||
    riskControl.max_position_pct < 1.0;

  return (
    <Accordion
      defaultExpanded={hasActiveRiskControls}
      sx={{
        border: hasActiveRiskControls ? '1px solid #f59e0b' : '1px solid #e5e7eb',
        borderRadius: '8px !important',
        '&:before': { display: 'none' },
        boxShadow: 'none',
      }}
    >
      <AccordionSummary
        expandIcon={<ExpandMoreIcon />}
        sx={{
          bgcolor: hasActiveRiskControls ? '#fffbeb' : '#fafafa',
          borderRadius: '8px',
          minHeight: 44,
          '& .MuiAccordionSummary-content': { margin: '8px 0' },
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: 0.5 }}>
          ⚙️ 风控设置（可选）
          {hasActiveRiskControls && (
            <Box component="span" sx={{ ml: 1, px: 1, py: 0.2, bgcolor: '#fef3c7', borderRadius: 1, fontSize: '0.7rem', color: '#92400e' }}>
              已启用
            </Box>
          )}
        </Typography>
      </AccordionSummary>

      <AccordionDetails sx={{ pt: 1, pb: 2 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          {/* ATR 止损倍数 */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 500, color: '#374151' }}>
                ATR 止损倍数
              </Typography>
              <Tooltip title="基于14日ATR的动态止损。倍数越大止损越宽松。0=禁用ATR止损" arrow placement="top">
                <IconButton size="small" sx={{ p: 0 }}>
                  <InfoOutlinedIcon sx={{ fontSize: 14, color: '#9ca3af' }} />
                </IconButton>
              </Tooltip>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Slider
                value={riskControl.atr_stop_multiplier}
                onChange={(_e, val) => updateField('atr_stop_multiplier', val as number)}
                min={0}
                max={5.0}
                step={0.5}
                marks={[
                  { value: 0, label: '关' },
                  { value: 1.5, label: '1.5x' },
                  { value: 3.0, label: '3x' },
                  { value: 5.0, label: '5x' },
                ]}
                size="small"
                sx={{ flex: 1 }}
              />
              <Typography variant="body2" sx={{ minWidth: 36, textAlign: 'right', color: '#6b7280' }}>
                {riskControl.atr_stop_multiplier}x
              </Typography>
            </Box>
          </Box>

          {/* 固定止盈比例 */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 500, color: '#374151' }}>
                固定止盈比例
              </Typography>
              <Tooltip title="持仓收益达到此比例时自动止盈。0=禁用" arrow placement="top">
                <IconButton size="small" sx={{ p: 0 }}>
                  <InfoOutlinedIcon sx={{ fontSize: 14, color: '#9ca3af' }} />
                </IconButton>
              </Tooltip>
            </Box>
            <TextField
              type="number"
              size="small"
              value={riskControl.take_profit_pct * 100}
              onChange={(e) => {
                const pct = Number(e.target.value) / 100;
                updateField('take_profit_pct', Math.max(0, pct));
              }}
              InputProps={{
                inputProps: { min: 0, step: 1 },
                endAdornment: <Typography variant="caption" sx={{ color: '#9ca3af' }}>%</Typography>,
              }}
              fullWidth
            />
          </Box>

          {/* 仓位模式 */}
          <Box>
            <FormControl fullWidth size="small">
              <InputLabel sx={{ fontSize: '0.75rem' }}>仓位模式</InputLabel>
              <Select
                value={riskControl.position_sizing}
                label="仓位模式"
                onChange={(e) => updateField('position_sizing', e.target.value as RiskControlParams['position_sizing'])}
              >
                {POSITION_SIZING_OPTIONS.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value} dense>
                    <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                      <Typography variant="body2">{opt.label}</Typography>
                      {opt.value === 'kelly' && (
                        <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                          根据历史胜率&盈亏比自动计算
                        </Typography>
                      )}
                      {opt.value === 'half_kelly' && (
                        <Typography variant="caption" sx={{ color: '#9ca3af' }}>
                          凯利公式×0.5，更保守
                        </Typography>
                      )}
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          {/* 固定仓位比例（条件显示） */}
          {riskControl.position_sizing === 'fixed_pct' && (
            <Box>
              <Typography variant="caption" sx={{ fontWeight: 500, color: '#374151', display: 'block', mb: 0.5 }}>
                固定仓位比例
              </Typography>
              <TextField
                type="number"
                size="small"
                value={riskControl.fixed_position_pct * 100}
                onChange={(e) => {
                  const pct = Number(e.target.value) / 100;
                  updateField('fixed_position_pct', Math.max(0.01, Math.min(1.0, pct)));
                }}
                InputProps={{
                  inputProps: { min: 1, max: 100, step: 5 },
                  endAdornment: <Typography variant="caption" sx={{ color: '#9ca3af' }}>%</Typography>,
                }}
                fullWidth
              />
            </Box>
          )}

          {/* 最大仓位上限 */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 500, color: '#374151' }}>
                最大仓位上限
              </Typography>
              <Tooltip title="单笔交易最大占用资金比例，对所有仓位模式生效" arrow placement="top">
                <IconButton size="small" sx={{ p: 0 }}>
                  <InfoOutlinedIcon sx={{ fontSize: 14, color: '#9ca3af' }} />
                </IconButton>
              </Tooltip>
            </Box>
            <TextField
              type="number"
              size="small"
              value={(riskControl.max_position_pct * 100).toFixed(0)}
              onChange={(e) => {
                const pct = Number(e.target.value) / 100;
                updateField('max_position_pct', Math.max(0.01, Math.min(1.0, pct)));
              }}
              InputProps={{
                inputProps: { min: 1, max: 100, step: 5 },
                endAdornment: <Typography variant="caption" sx={{ color: '#9ca3af' }}>%</Typography>,
              }}
              helperText="所有仓位模式的硬上限"
              fullWidth
            />
          </Box>

          {/* 最大回撤熔断 */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
              <Typography variant="caption" sx={{ fontWeight: 500, color: '#374151' }}>
                最大回撤熔断
              </Typography>
              <Tooltip title="从峰值回撤超过此比例时立即平仓并停止交易。0=禁用" arrow placement="top">
                <IconButton size="small" sx={{ p: 0 }}>
                  <InfoOutlinedIcon sx={{ fontSize: 14, color: '#9ca3af' }} />
                </IconButton>
              </Tooltip>
            </Box>
            <TextField
              type="number"
              size="small"
              value={(riskControl.max_drawdown_limit * 100).toFixed(0)}
              onChange={(e) => {
                const pct = Number(e.target.value) / 100;
                updateField('max_drawdown_limit', Math.max(0, Math.min(1.0, pct)));
              }}
              InputProps={{
                inputProps: { min: 0, max: 100, step: 5 },
                endAdornment: <Typography variant="caption" sx={{ color: '#9ca3af' }}>%</Typography>,
              }}
              helperText="0 = 禁用回撤熔断"
              fullWidth
            />
          </Box>

          {/* 重置按钮 */}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Typography
              variant="caption"
              onClick={() => onChange({ ...DEFAULT_RISK_CONTROL })}
              sx={{
                color: '#6b7280',
                cursor: 'pointer',
                textDecoration: 'underline',
                '&:hover': { color: '#ef4444' },
              }}
            >
              重置风控参数
            </Typography>
          </Box>
        </Box>
      </AccordionDetails>
    </Accordion>
  );
};

export default RiskControlPanel;
