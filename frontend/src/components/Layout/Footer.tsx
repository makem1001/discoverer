/**
 * 发现者（Discoverer）— 全局页脚
 *
 * 在所有受保护页面底部展示风险提示和法律链接。
 */
import React from 'react';
import { Box, Typography, Link } from '@mui/material';

const Footer: React.FC = () => {
  return (
    <Box
      component="footer"
      sx={{
        py: 2,
        px: 3,
        mt: 'auto',
        textAlign: 'center',
        borderTop: '1px solid',
        borderColor: 'divider',
      }}
    >
      <Typography variant="caption" color="text.secondary">
        ⚠️ 风险提示：历史数据回测结果不构成投资建议。投资有风险，入市需谨慎。
      </Typography>
      <Box sx={{ mt: 0.5 }}>
        <Link
          href="#"
          variant="caption"
          color="text.secondary"
          sx={{ mx: 1 }}
        >
          用户协议
        </Link>
        <Link
          href="#"
          variant="caption"
          color="text.secondary"
          sx={{ mx: 1 }}
        >
          风险告知书
        </Link>
      </Box>
      <Typography
        variant="caption"
        color="text.disabled"
        display="block"
        sx={{ mt: 0.5 }}
      >
        © 2026 发现者（Discoverer）
      </Typography>
    </Box>
  );
};

export default Footer;
