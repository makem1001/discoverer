import React, { lazy, Suspense } from 'react';
import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { CircularProgress, Box, Typography, Button, Alert } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import TopNav from './components/Layout/TopNav';
import Footer from './components/Layout/Footer';
import ClassicBacktest from './pages/ClassicBacktest';
import CustomStrategy from './pages/CustomStrategy';
import StrategyDiscovery from './pages/StrategyDiscovery';
import StrategyCheckup from './pages/StrategyCheckup';
import MyStrategies from './pages/MyStrategies';
import BacktestHistory from './pages/BacktestHistory';
import Settings from './pages/Settings';
import PriceQuery from './pages/PriceQuery';
import Login from './pages/Login';
import Register from './pages/Register';
import { useAuth } from './contexts/AuthContext';

// P1 懒加载页面（T02/T04 完成实现）
const CompareBacktest = lazy(() => import('./pages/CompareBacktest'));
const PaperTrading = lazy(() => import('./pages/PaperTrading'));
const GridSearch = lazy(() => import('./pages/GridSearch'));

/**
 * ErrorBoundary — 全局错误边界
 *
 * 捕获子组件树中的未处理错误，显示友好的错误页面而非白屏。
 */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] 捕获未处理错误:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            bgcolor: '#f5f5f5',
            gap: 2,
            px: 4,
          }}
        >
          <ErrorOutlineIcon sx={{ fontSize: 64, color: '#ef4444' }} />
          <Typography variant="h5" sx={{ fontWeight: 600, color: '#1f2937' }}>
            页面出错了
          </Typography>
          <Typography variant="body2" sx={{ color: '#6b7280', textAlign: 'center', maxWidth: 400 }}>
            {this.state.error?.message || '发生了未知错误，请尝试刷新页面。'}
          </Typography>
          <Alert severity="info" variant="outlined" sx={{ maxWidth: 500, wordBreak: 'break-all' }}>
            <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
              {this.state.error?.stack?.slice(0, 300)}
            </Typography>
          </Alert>
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <Button
              variant="contained"
              onClick={() => window.location.reload()}
              sx={{ textTransform: 'none' }}
            >
              刷新页面
            </Button>
            <Button
              variant="outlined"
              onClick={this.handleReset}
              sx={{ textTransform: 'none' }}
            >
              重试
            </Button>
          </Box>
        </Box>
      );
    }

    return this.props.children;
  }
}

/**
 * 受保护布局：需要登录才能访问。
 * 未登录时显示加载中或重定向到 /login。
 *
 * P0 加固：双重认证检查。
 * AuthContext 的 React state 是主要来源，但 useApi.ts 可能异步
 * 更新 localStorage 而 AuthContext 不知情。当 user=null 时，
 * 二次检查 localStorage 中有无有效 token，防止误重定向。
 */
const ProtectedLayout: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();

  console.log('[DEBUG ProtectedLayout] 渲染, isAuthenticated=', isAuthenticated, 'isLoading=', isLoading);

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (!isAuthenticated) {
    // 二次确认：localStorage 中是否仍有 token？
    const storedToken = localStorage.getItem('access_token')
      || sessionStorage.getItem('access_token');
    if (storedToken) {
      console.warn('[ProtectedLayout] user=null 但 token 存在，等待 AuthContext 恢复');
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
          <CircularProgress />
        </Box>
      );
    }
    console.trace('[DEBUG ProtectedLayout] ⚠️ 即将重定向到 /login (user=null, 无token)');
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <TopNav />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
};

/**
 * 公开路由守卫：已登录用户访问登录/注册页时重定向到主页。
 */
const PublicOnlyRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/classic" replace />;
  }

  return <>{children}</>;
};

const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <Routes>
      {/* 公开路由：无需登录 */}
      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <Login />
          </PublicOnlyRoute>
        }
      />
      <Route
        path="/register"
        element={
          <PublicOnlyRoute>
            <Register />
          </PublicOnlyRoute>
        }
      />

      {/* 受保护路由：需要登录 */}
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<Navigate to="/classic" replace />} />
        <Route path="/classic" element={<ClassicBacktest />} />
        <Route path="/custom" element={<CustomStrategy />} />
        <Route path="/discovery" element={<StrategyDiscovery />} />
        <Route path="/checkup" element={<StrategyCheckup />} />
        <Route path="/compare" element={<Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><CircularProgress /></Box>}><CompareBacktest /></Suspense>} />
        <Route path="/paper" element={<Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><CircularProgress /></Box>}><PaperTrading /></Suspense>} />
        <Route path="/grid-search" element={<Suspense fallback={<Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}><CircularProgress /></Box>}><GridSearch /></Suspense>} />
        <Route path="/strategies" element={<MyStrategies />} />
        <Route path="/history" element={<BacktestHistory />} />
        <Route path="/query" element={<PriceQuery />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      {/* 404 兜底 */}
      <Route path="*" element={<Navigate to="/classic" replace />} />
    </Routes>
    </ErrorBoundary>
  );
};

export default App;
