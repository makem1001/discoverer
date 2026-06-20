/**
 * 发现者（Discoverer）— 信号标签输入/选择组件
 *
 * 支持从69个信号中多选，以 Chip 形式展示。
 */

import React, { useState, useEffect } from 'react';
import {
  Autocomplete, TextField, Chip, Box, Typography,
} from '@mui/material';
import type { Signal } from '../../types';
import { useApi } from '../../hooks/useApi';

interface SignalTagInputProps {
  value: string[];
  onChange: (signalIds: string[]) => void;
  label?: string;
}

const SignalTagInput: React.FC<SignalTagInputProps> = ({
  value,
  onChange,
  label = '选择信号',
}) => {
  const [allSignals, setAllSignals] = useState<Signal[]>([]);
  const { get } = useApi();

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const res = await get<{ signals: Signal[] }>('/signals');
        if (res.code === 0 && res.data?.signals) {
          setAllSignals(res.data.signals);
        }
      } catch {
        // 静默失败
      }
    };
    fetchSignals();
  }, [get]);

  const selectedSignals = allSignals.filter((s) => value.includes(s.id));

  // 将信号按类别分组
  const groupedSignals: Record<string, Signal[]> = {};
  for (const s of allSignals) {
    if (!groupedSignals[s.category]) {
      groupedSignals[s.category] = [];
    }
    groupedSignals[s.category].push(s);
  }

  return (
    <Autocomplete
      multiple
      value={selectedSignals}
      onChange={(_event, newValue) => {
        onChange(newValue.map((s) => s.id));
      }}
      options={allSignals}
      getOptionLabel={(option) => `${option.name} (${option.id})`}
      groupBy={(option) => option.category}
      isOptionEqualToValue={(option, val) => option.id === val.id}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          placeholder="搜索信号名称..."
        />
      )}
      renderTags={(tagValue, getTagProps) =>
        tagValue.map((option, index) => (
          <Chip
            {...getTagProps({ index })}
            key={option.id}
            label={option.name}
            size="small"
            sx={{
              bgcolor: '#eff6ff',
              color: '#1e40af',
              border: '1px solid #bfdbfe',
            }}
          />
        ))
      }
      renderOption={(props, option) => (
        <Box component="li" {...props} key={option.id}>
          <Box sx={{ display: 'flex', flexDirection: 'column' }}>
            <Typography variant="body2" sx={{ fontWeight: 500 }}>
              {option.name}
            </Typography>
            <Typography variant="caption" sx={{ color: '#9ca3af' }}>
              {option.id} · {option.description}
            </Typography>
          </Box>
        </Box>
      )}
      sx={{ width: '100%' }}
    />
  );
};

export default SignalTagInput;
