/**
 * 发现者（Discoverer）— 价格查询页面
 *
 * 支持股票代码/名称搜索 + 日期范围 + 价格表展示
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, TextField, Button, Paper, Chip, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, CircularProgress, Alert, Autocomplete, InputAdornment,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

interface StockItem {
  code: string;
  name: string;
  market: string;
}

interface PriceRecord {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
}

interface QueryResult {
  code: string;
  source: string;
  count: number;
  records: PriceRecord[];
}

const SOURCE_LABELS: Record<string, { label: string; color: any }> = {
  tdx: { label: '通达信本地', color: 'success' as const },
  parquet_cache: { label: '本地缓存', color: 'primary' as const },
  akshare: { label: 'akshare在线', color: 'info' as const },
  mock: { label: '模拟数据', color: 'warning' as const },
};

const PriceQuery: React.FC = () => {
  const [keyword, setKeyword] = useState('');
  const [suggestions, setSuggestions] = useState<StockItem[]>([]);
  const [selectedStock, setSelectedStock] = useState<StockItem | null>(null);
  const [startDate, setStartDate] = useState('2025-05-01');
  const [endDate, setEndDate] = useState('2025-05-31');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchLoading, setSearchLoading] = useState(false);

  // 股票名称搜索
  const searchStocks = useCallback(async (q: string) => {
    if (q.length < 1) { setSuggestions([]); return; }
    setSearchLoading(true);
    try {
      const resp = await fetch(`/api/stocks/search?q=${encodeURIComponent(q)}&limit=8`);
      const data = await resp.json();
      if (data.code === 0 && Array.isArray(data.data)) {
        setSuggestions(data.data);
      }
    } catch { /* ignore */ }
    finally { setSearchLoading(false); }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => searchStocks(keyword), 200);
    return () => clearTimeout(timer);
  }, [keyword, searchStocks]);

  // 查询价格
  const handleQuery = async () => {
    if (!selectedStock) { setError('请先选择股票'); return; }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const resp = await fetch(
        `/api/stocks/${selectedStock.code}/prices?start=${startDate}&end=${endDate}`
      );
      const data = await resp.json();
      if (data.code === 0 && data.data) {
        setResult(data.data);
      } else {
        setError(data.message || '查询失败');
      }
    } catch (e: any) {
      setError(e.message || '请求失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 3, maxWidth: 960, mx: 'auto' }}>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5 }}>
        价格数据查询
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        通达信本地数据直读 · 支持代码和名称搜索
      </Typography>

      {/* 搜索和日期 */}
      <Paper sx={{ p: 2.5, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <Autocomplete
            freeSolo
            options={suggestions}
            getOptionLabel={(o) => typeof o === 'string' ? o : `${o.code} ${o.name}`}
            filterOptions={(x) => x}
            loading={searchLoading}
            value={selectedStock}
            onChange={(_, v) => setSelectedStock(v as StockItem | null)}
            onInputChange={(_, v) => setKeyword(v)}
            sx={{ flex: 1, minWidth: 220 }}
            renderInput={(params) => (
              <TextField
                {...params}
                label="股票代码或名称"
                placeholder="输入代码或名称搜索..."
                InputProps={{
                  ...params.InputProps,
                  startAdornment: (
                    <InputAdornment position="start"><SearchIcon color="action" /></InputAdornment>
                  ),
                  endAdornment: (
                    <>
                      {searchLoading && <CircularProgress size={20} />}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                }}
              />
            )}
          />
          <TextField
            label="起始日期"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: 150 }}
          />
          <TextField
            label="结束日期"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: 150 }}
          />
          <Button
            variant="contained"
            size="large"
            onClick={handleQuery}
            disabled={loading || !selectedStock}
            sx={{ height: 56, px: 4, bgcolor: '#1a73e8', '&:hover': { bgcolor: '#1557b0' } }}
          >
            {loading ? <CircularProgress size={24} color="inherit" /> : '查询'}
          </Button>
        </Box>
      </Paper>

      {/* 错误 */}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}

      {/* 结果 */}
      {result && (
        <Paper sx={{ overflow: 'hidden' }}>
          <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 1.5, borderBottom: '1px solid #e5e7eb' }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {result.code}
            </Typography>
            {SOURCE_LABELS[result.source] && (
              <Chip
                label={SOURCE_LABELS[result.source].label}
                color={SOURCE_LABELS[result.source].color}
                size="small"
              />
            )}
            <Typography variant="body2" color="text.secondary">
              共 {result.count} 条记录
            </Typography>
          </Box>
          <TableContainer sx={{ maxHeight: '60vh', overflowX: 'auto' }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>日期</TableCell>
                  <TableCell align="right">开盘</TableCell>
                  <TableCell align="right">最高</TableCell>
                  <TableCell align="right">最低</TableCell>
                  <TableCell align="right">收盘</TableCell>
                  <TableCell align="right">成交量</TableCell>
                  <TableCell align="right">成交额</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {result.records.map((r) => (
                  <TableRow key={r.date} hover>
                    <TableCell>{r.date}</TableCell>
                    <TableCell align="right">{r.open.toFixed(2)}</TableCell>
                    <TableCell align="right">{r.high.toFixed(2)}</TableCell>
                    <TableCell align="right">{r.low.toFixed(2)}</TableCell>
                    <TableCell align="right">{r.close.toFixed(2)}</TableCell>
                    <TableCell align="right">{r.volume.toLocaleString()}</TableCell>
                    <TableCell align="right">{(r.amount / 1e8).toFixed(2)}亿</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Paper>
      )}

      {!result && !loading && !error && (
        <Box sx={{ textAlign: 'center', py: 8, color: '#9ca3af' }}>
          <SearchIcon sx={{ fontSize: 48, mb: 1 }} />
          <Typography>选择股票和日期范围，点击查询</Typography>
        </Box>
      )}
    </Box>
  );
};

export default PriceQuery;
