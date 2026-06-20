/**
 * 发现者（Discoverer）— 股票搜索组件
 *
 * 支持：代码 / 名称 / 拼音首字母搜索
 * 使用 Autocomplete + 防抖实现
 */

import React, { useState, useCallback, useRef } from 'react';
import {
  Autocomplete, TextField, CircularProgress, Box, Typography,
} from '@mui/material';
import type { Stock } from '../../types';
import { useApi } from '../../hooks/useApi';

interface StockSearchProps {
  value: Stock | null;
  onChange: (stock: Stock | null) => void;
  label?: string;
  error?: boolean;
  helperText?: string;
}

const StockSearch: React.FC<StockSearchProps> = ({
  value,
  onChange,
  label = '搜索股票',
  error = false,
  helperText,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [options, setOptions] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { get } = useApi();

  const handleInputChange = useCallback(
    (_event: React.SyntheticEvent, newInputValue: string) => {
      setInputValue(newInputValue);

      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (newInputValue.trim().length < 1) {
        setOptions([]);
        return;
      }

      setLoading(true);
      debounceRef.current = setTimeout(async () => {
        try {
          const res = await get<Stock[]>(`/stocks/search?q=${encodeURIComponent(newInputValue.trim())}&limit=15`);
          if (res.code === 0 && res.data) {
            setOptions(res.data);
          } else {
            setOptions([]);
          }
        } catch {
          setOptions([]);
        } finally {
          setLoading(false);
        }
      }, 300);
    },
    [get],
  );

  return (
    <Autocomplete
      value={value}
      onChange={(_event, newValue) => onChange(newValue)}
      inputValue={inputValue}
      onInputChange={handleInputChange}
      options={options}
      getOptionLabel={(option) => `${option.name} (${option.code})`}
      isOptionEqualToValue={(option, val) => option.code === val.code}
      loading={loading}
      noOptionsText={inputValue.length > 0 ? '未找到匹配股票' : '输入代码或名称搜索'}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          error={error}
          helperText={helperText}
          placeholder="输入代码/名称/拼音，如 平安银行"
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <>
                {loading && <CircularProgress size={20} />}
                {params.InputProps.endAdornment}
              </>
            ),
          }}
        />
      )}
      renderOption={(props, option) => (
        <Box component="li" {...props} key={option.code}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, width: '100%' }}>
            <Typography variant="body2" sx={{ fontWeight: 600, color: '#1f2937', minWidth: 70 }}>
              {option.code}
            </Typography>
            <Typography variant="body2" sx={{ flex: 1 }}>
              {option.name}
            </Typography>
            <Typography variant="caption" sx={{ color: '#9ca3af' }}>
              {option.market}
            </Typography>
          </Box>
        </Box>
      )}
      sx={{ width: '100%' }}
    />
  );
};

export default StockSearch;
