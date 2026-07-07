/**
 * 发现者（Discoverer）— 顶部导航栏
 *
 * Logo + 功能 Tab + 用户入口
 *
 * 响应式适配：
 * - 桌面端（≥768px）：横向 Tabs 导航
 * - 移动端（<768px）：汉堡菜单 → Drawer 纵向导航
 */

import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar, Toolbar, Tabs, Tab, Typography, Box,
  Button, Menu, MenuItem, ListItemIcon, ListItemText, Divider,
  IconButton, Drawer, List, ListItemButton, ListItem, useMediaQuery, Theme,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import HistoryIcon from '@mui/icons-material/History';
import SettingsIcon from '@mui/icons-material/Settings';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import SearchIcon from '@mui/icons-material/Search';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import LogoutIcon from '@mui/icons-material/Logout';
import LoginIcon from '@mui/icons-material/Login';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import GridOnIcon from '@mui/icons-material/GridOn';
import { useAuth } from '../../contexts/AuthContext';

const TAB_CONFIG: {
  label: string;
  path: string;
  icon?: React.ReactElement;
  mobileIcon?: React.ReactElement;
}[] = [
  { label: '经典回测', path: '/classic' },
  { label: '自由定制', path: '/custom' },
  { label: '策略发现', path: '/discovery' },
  { label: '策略体检', path: '/checkup' },
  { label: '策略对比', path: '/compare', icon: <CompareArrowsIcon /> },
  { label: '模拟交易', path: '/paper', icon: <AccountBalanceIcon /> },
  { label: '网格搜索', path: '/grid-search', icon: <GridOnIcon /> },
  { label: '我的策略', path: '/strategies' },
  { label: '回测历史', path: '/history' },
  { label: '价格查询', path: '/query' },
];

const TopNav: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isAuthenticated, logout } = useAuth();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const isMobile = useMediaQuery((theme: Theme) => theme.breakpoints.down('md'));

  const currentTab = TAB_CONFIG.findIndex((t) => t.path === location.pathname);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    navigate(TAB_CONFIG[newValue].path);
  };

  const handleNavClick = (path: string) => {
    navigate(path);
    setDrawerOpen(false);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
    setDrawerOpen(false);
    setAnchorEl(null);
  };

  // ── 桌面端 Tab 导航 ──
  const desktopTabs = (
    <Tabs
      value={currentTab >= 0 ? currentTab : 0}
      onChange={handleTabChange}
      variant="scrollable"
      scrollButtons="auto"
      sx={{
        minHeight: 56,
        width: '100%',
        '& .MuiTab-root': {
          minHeight: 56,
          textTransform: 'none',
          fontSize: '0.9rem',
          fontWeight: 500,
          px: 2.5,
        },
        '& .Mui-selected': {
          color: '#1a73e8',
        },
        '& .MuiTabs-indicator': {
          backgroundColor: '#1a73e8',
          height: 3,
        },
      }}
    >
      {TAB_CONFIG.map((tab) => (
        <Tab key={tab.path} label={tab.label} />
      ))}
    </Tabs>
  );

  // ── 移动端 Drawer ──
  const mobileDrawer = (
    <Drawer
      anchor="left"
      open={drawerOpen}
      onClose={() => setDrawerOpen(false)}
      PaperProps={{
        sx: { width: 260 },
      }}
    >
      {/* Drawer 头部 */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          p: 2,
          borderBottom: '1px solid #e5e7eb',
        }}
      >
        <ShowChartIcon sx={{ color: '#1a73e8', fontSize: 24 }} />
        <Box>
          <Typography sx={{ fontWeight: 700, color: '#1a73e8', fontSize: '1.1rem' }}>
            发现者
          </Typography>
          <Typography variant="caption" sx={{ color: '#9ca3af' }}>
            A股量化回测
          </Typography>
        </Box>
      </Box>

      {/* 导航列表 */}
      <List sx={{ pt: 1 }}>
        {TAB_CONFIG.map((tab) => {
          const isActive = location.pathname === tab.path;
          return (
            <ListItemButton
              key={tab.path}
              selected={isActive}
              onClick={() => handleNavClick(tab.path)}
              sx={{
                mx: 0.5,
                borderRadius: 1,
                '&.Mui-selected': {
                  bgcolor: '#e8f0fe',
                  color: '#1a73e8',
                  '&:hover': { bgcolor: '#d2e3fc' },
                },
              }}
            >
              <ListItemText
                primary={tab.label}
                primaryTypographyProps={{
                  fontSize: '0.9rem',
                  fontWeight: isActive ? 600 : 400,
                }}
              />
            </ListItemButton>
          );
        })}
      </List>

      <Divider />

      {/* Drawer 底部：用户操作 */}
      <Box sx={{ p: 1.5 }}>
        {isAuthenticated ? (
          <>
            <ListItemButton onClick={() => handleNavClick('/strategies')} sx={{ borderRadius: 1 }}>
              <ListItemIcon><BookmarkIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="我的策略" primaryTypographyProps={{ fontSize: '0.85rem' }} />
            </ListItemButton>
            <ListItemButton onClick={() => handleNavClick('/history')} sx={{ borderRadius: 1 }}>
              <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="回测历史" primaryTypographyProps={{ fontSize: '0.85rem' }} />
            </ListItemButton>
            <ListItemButton onClick={() => handleNavClick('/query')} sx={{ borderRadius: 1 }}>
              <ListItemIcon><SearchIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="价格查询" primaryTypographyProps={{ fontSize: '0.85rem' }} />
            </ListItemButton>
            <ListItemButton onClick={() => handleNavClick('/settings')} sx={{ borderRadius: 1 }}>
              <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>
              <ListItemText primary="设置" primaryTypographyProps={{ fontSize: '0.85rem' }} />
            </ListItemButton>
            <Divider sx={{ my: 1 }} />
            <ListItemButton onClick={handleLogout} sx={{ borderRadius: 1 }}>
              <ListItemIcon><LogoutIcon fontSize="small" sx={{ color: '#ef4444' }} /></ListItemIcon>
              <ListItemText
                primary="退出登录"
                primaryTypographyProps={{ color: '#ef4444', fontSize: '0.85rem' }}
              />
            </ListItemButton>
          </>
        ) : (
          <Button
            variant="outlined"
            fullWidth
            startIcon={<LoginIcon />}
            onClick={() => { handleNavClick('/login'); }}
            sx={{ textTransform: 'none' }}
          >
            登录
          </Button>
        )}
      </Box>
    </Drawer>
  );

  // ── 用户菜单（桌面端） ──
  const userMenu = (
    <>
      {isAuthenticated ? (
        <>
          <Button
            onClick={(e) => setAnchorEl(e.currentTarget)}
            startIcon={<AccountCircleIcon />}
            size="small"
            sx={{
              color: '#374151',
              textTransform: 'none',
              fontWeight: 500,
              fontSize: '0.875rem',
            }}
          >
            {user?.email?.split('@')[0] || '用户'}
          </Button>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            PaperProps={{ sx: { minWidth: 180, mt: 0.5 } }}
          >
            <MenuItem onClick={() => { navigate('/strategies'); setAnchorEl(null); }}>
              <ListItemIcon><BookmarkIcon fontSize="small" /></ListItemIcon>
              <ListItemText>我的策略</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => { navigate('/history'); setAnchorEl(null); }}>
              <ListItemIcon><HistoryIcon fontSize="small" /></ListItemIcon>
              <ListItemText>回测历史</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => { navigate('/query'); setAnchorEl(null); }}>
              <ListItemIcon><SearchIcon fontSize="small" /></ListItemIcon>
              <ListItemText>价格查询</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => { navigate('/settings'); setAnchorEl(null); }}>
              <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>
              <ListItemText>设置</ListItemText>
            </MenuItem>
            <Divider />
            <MenuItem onClick={() => { logout(); navigate('/login'); setAnchorEl(null); }}>
              <ListItemIcon><LogoutIcon fontSize="small" sx={{ color: '#ef4444' }} /></ListItemIcon>
              <ListItemText primary="退出登录" primaryTypographyProps={{ color: '#ef4444' }} />
            </MenuItem>
          </Menu>
        </>
      ) : (
        <Button
          variant="outlined"
          size="small"
          startIcon={<LoginIcon />}
          onClick={() => navigate('/login')}
          sx={{ textTransform: 'none', borderColor: '#d1d5db', color: '#374151' }}
        >
          登录
        </Button>
      )}
    </>
  );

  return (
    <>
      <AppBar
        position="static"
        elevation={0}
        sx={{
          bgcolor: '#ffffff',
          borderBottom: '1px solid #e5e7eb',
          color: '#1f2937',
        }}
      >
        <Toolbar sx={{ minHeight: '56px !important', px: 2 }}>
          {/* 移动端汉堡菜单 */}
          {isMobile && (
            <IconButton
              edge="start"
              onClick={() => setDrawerOpen(true)}
              aria-label="打开菜单"
              sx={{ mr: 1, color: '#374151' }}
            >
              <MenuIcon />
            </IconButton>
          )}

          {/* Logo */}
          <Box sx={{ display: 'flex', alignItems: 'center', mr: 3 }}>
            <ShowChartIcon sx={{ color: '#1a73e8', mr: 1, fontSize: 28 }} />
            <Typography
              variant="h6"
              sx={{
                fontWeight: 700,
                fontSize: '1.25rem',
                color: '#1a73e8',
                letterSpacing: '-0.5px',
              }}
            >
              发现者
            </Typography>
            {!isMobile && (
              <Typography
                variant="body2"
                sx={{ ml: 1, color: '#9ca3af', fontSize: '0.75rem' }}
              >
                A股量化回测
              </Typography>
            )}
          </Box>

          {/* 桌面端 Tabs：占满剩余宽度，防止被右侧用户菜单挤占 */}
          {!isMobile && (
            <Box sx={{ flex: 1, minWidth: 0, overflow: 'hidden', display: 'flex', mx: 1 }}>
              {desktopTabs}
            </Box>
          )}

          {/* 右侧操作：用户菜单 */}
          <Box sx={{ ml: 'auto', display: 'flex', gap: 0.5, alignItems: 'center' }}>
            {userMenu}
          </Box>
        </Toolbar>
      </AppBar>

      {/* 移动端 Drawer */}
      {isMobile && mobileDrawer}
    </>
  );
};

export default TopNav;
