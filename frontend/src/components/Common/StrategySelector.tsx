/**
 * 发现者（Discoverer）— 经典策略选择器
 *
 * 下拉列表选择内置的13个经典策略。
 */

import React, { useEffect, useState } from 'react';
import {
  FormControl, InputLabel, Select, MenuItem, Typography, Box, Chip,
} from '@mui/material';
import type { ClassicStrategy } from '../../types';
import { useApi } from '../../hooks/useApi';

interface StrategySelectorProps {
  value: string;
  onChange: (strategyId: string) => void;
}

const FALLBACK_STRATEGIES: ClassicStrategy[] = [
  { id: 'macd_golden_death', name: 'MACD金叉死叉', description: 'DIF上穿DEA买入，DIF下穿DEA卖出', entry_signal: 'macd_golden_cross', exit_signal: 'macd_death_cross', holding_rule: 'next_signal_reverse' },
  { id: 'ma_golden_death', name: '均线金叉死叉(5/20)', description: 'MA5上穿MA20买入，MA5下穿MA20卖出', entry_signal: 'ma_golden_cross', exit_signal: 'ma_death_cross', holding_rule: 'next_signal_reverse' },
  { id: 'ma_golden_death_10_30', name: '均线金叉死叉(10/30)', description: 'MA10上穿MA30买入，MA10下穿MA30卖出', entry_signal: 'ma_golden_cross_10_30', exit_signal: 'ma_death_cross_10_30', holding_rule: 'next_signal_reverse' },
  { id: 'ma_golden_death_20_60', name: '均线金叉死叉(20/60)', description: 'MA20上穿MA60买入，MA20下穿MA60卖出', entry_signal: 'ma_golden_cross_20_60', exit_signal: 'ma_death_cross_20_60', holding_rule: 'next_signal_reverse' },
  { id: 'rsi_oversold_overbought', name: 'RSI超卖超买(14)', description: 'RSI(14)低于30买入，高于70卖出', entry_signal: 'rsi_oversold_14', exit_signal: 'rsi_overbought_14', holding_rule: 'next_signal_reverse' },
  { id: 'kdj_golden_death', name: 'KDJ金叉死叉', description: 'K线上穿D线买入，K线下穿D线卖出', entry_signal: 'kdj_golden_cross', exit_signal: 'kdj_death_cross', holding_rule: 'next_signal_reverse' },
  { id: 'boll_lower_buy_upper_sell', name: '布林带下轨买上轨卖', description: '触及布林下轨买入，触及布林上轨卖出', entry_signal: 'boll_lower_touch', exit_signal: 'boll_upper_touch', holding_rule: 'next_signal_reverse' },
  { id: 'vol_breakout_with_ma_golden', name: '放量+均线金叉', description: '成交量放大1.5倍且MA5/20金叉买入', entry_signal: 'vol_breakout_1_5', exit_signal: 'ma_death_cross', holding_rule: 'next_signal_reverse' },
  { id: 'ma_golden_hold_10d', name: '均线金叉+持有10天', description: 'MA5/20金叉买入，持有10个交易日后卖出', entry_signal: 'ma_golden_cross', exit_signal: null, holding_rule: 'hold_n_days' },
  { id: 'breakout_20d_high', name: '突破20日高点+移动止损', description: '收盘价突破20日高点买入，5%移动止损', entry_signal: 'breakout_20day_high', exit_signal: null, holding_rule: 'trailing_stop' },
  { id: 'bullish_alignment_hold', name: '多头排列买入持有', description: '均线多头排列时买入，持有到期末', entry_signal: 'ma_bullish_alignment', exit_signal: null, holding_rule: 'hold_until_end' },
  { id: 'macd_golden_vol_breakout', name: 'MACD金叉+放量确认', description: 'MACD金叉且成交量放大1.5倍买入', entry_signal: 'macd_golden_cross', exit_signal: 'macd_death_cross', holding_rule: 'next_signal_reverse' },
  { id: 'kdj_oversold_buy_overbought_sell', name: 'KDJ超卖买超买卖', description: 'KDJ超卖区买入，超买区卖出', entry_signal: 'kdj_oversold', exit_signal: 'kdj_overbought', holding_rule: 'next_signal_reverse' },
];

const StrategySelector: React.FC<StrategySelectorProps> = ({ value, onChange }) => {
  const [strategies, setStrategies] = useState<ClassicStrategy[]>([]);
  const [loading, setLoading] = useState(false);
  const { get } = useApi();

  useEffect(() => {
    const fetchStrategies = async () => {
      setLoading(true);
      try {
        const res = await get<ClassicStrategy[]>('/strategies/classic');
        if (res.code === 0 && Array.isArray(res.data) && res.data.length > 0) {
          setStrategies(res.data);
        } else {
          console.warn('策略列表API返回异常，使用本地回退', res);
          setStrategies(FALLBACK_STRATEGIES);
        }
      } catch {
        console.warn('策略列表API请求失败，使用本地回退');
        setStrategies(FALLBACK_STRATEGIES);
      } finally {
        setLoading(false);
      }
    };
    fetchStrategies();
  }, [get]);

  const selectedStrategy = strategies.find((s) => s.id === value);

  return (
    <FormControl fullWidth>
      <InputLabel id="strategy-select-label">选择经典策略</InputLabel>
      <Select
        labelId="strategy-select-label"
        value={value}
        label="选择经典策略"
        onChange={(e) => onChange(e.target.value)}
        renderValue={(selected) => {
          const s = strategies.find((st) => st.id === selected);
          return s ? (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip label={s.name} size="small" color="primary" variant="outlined" />
            </Box>
          ) : selected;
        }}
      >
        {strategies.map((s) => (
          <MenuItem key={s.id} value={s.id}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {s.name}
              </Typography>
              <Typography variant="caption" sx={{ color: '#6b7280' }}>
                {s.description}
              </Typography>
            </Box>
          </MenuItem>
        ))}
      </Select>
      {selectedStrategy && (
        <Typography variant="caption" sx={{ mt: 0.5, color: '#6b7280', px: 1 }}>
          {selectedStrategy.description}
        </Typography>
      )}
    </FormControl>
  );
};

export default StrategySelector;
