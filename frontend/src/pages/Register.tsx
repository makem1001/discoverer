/**
 * 发现者（Discoverer）— 注册页面
 *
 * 居中卡片布局，支持邮箱+密码+确认密码注册，自动登录后跳转。
 */
import React, { useState } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Link,
  InputAdornment,
  IconButton,
  Checkbox,
  FormControlLabel,
} from '@mui/material';
import { Visibility, VisibilityOff } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import RiskDisclosure from '../components/Common/RiskDisclosure';

const Register: React.FC = () => {
  const navigate = useNavigate();
  const { register, login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [agreedRisk, setAgreedRisk] = useState(false);
  const [riskDialogOpen, setRiskDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // 前端校验
    if (!email.trim()) {
      setError('请输入邮箱地址');
      return;
    }
    if (!password) {
      setError('请输入密码');
      return;
    }
    if (password.length < 6) {
      setError('密码至少需要 6 位');
      return;
    }
    if (password !== confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }
    if (!agreedRisk) {
      setError('请阅读并同意《风险告知书》');
      return;
    }

    setLoading(true);
    try {
      // 先注册
      const regResult = await register(email.trim(), password, true);
      if (!regResult.success) {
        setError(regResult.message);
        setLoading(false);
        return;
      }

      // 注册成功，自动登录
      const loginResult = await login(email.trim(), password, false);
      if (loginResult.success) {
        window.location.href = '/classic';
      } else {
        setError('注册成功！请前往登录');
        setTimeout(() => navigate('/login', { replace: true }), 1500);
        setLoading(false);
      }
    } catch {
      setError('注册失败，请检查网络连接');
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        minHeight: '100vh',
        bgcolor: '#f5f5f5',
        px: 2,
      }}
    >
      <Card sx={{ maxWidth: 400, width: '100%', boxShadow: 3 }}>
        <CardContent sx={{ p: 4 }}>
          {/* 品牌标题 */}
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <Typography variant="h4" color="primary" sx={{ fontWeight: 700 }}>
              发现者
            </Typography>
            <Typography variant="body2" color="text.secondary">
              创建您的账号
            </Typography>
          </Box>

          {/* 错误提示 */}
          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          {/* 注册表单 */}
          <Box component="form" onSubmit={handleSubmit} noValidate>
            <TextField
              fullWidth
              label="邮箱"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              autoComplete="email"
              autoFocus
              disabled={loading}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="密码"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="至少 6 位密码"
              autoComplete="new-password"
              disabled={loading}
              sx={{ mb: 2 }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                      size="small"
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              fullWidth
              label="确认密码"
              type={showConfirm ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="再次输入密码"
              autoComplete="new-password"
              disabled={loading}
              sx={{ mb: 3 }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowConfirm(!showConfirm)}
                      edge="end"
                      size="small"
                    >
                      {showConfirm ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            {/* 风险告知书确认 */}
            <FormControlLabel
              control={
                <Checkbox
                  checked={agreedRisk}
                  onChange={(e) => setAgreedRisk(e.target.checked)}
                  size="small"
                />
              }
              label={
                <Typography variant="body2">
                  我已阅读并同意
                  <Link
                    component="button"
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      setRiskDialogOpen(true);
                    }}
                    underline="hover"
                    sx={{ mx: 0.5 }}
                  >
                    《风险告知书》
                  </Link>
                </Typography>
              }
              sx={{ mb: 2 }}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={loading || !agreedRisk}
              sx={{ mb: 2, py: 1.2 }}
            >
              {loading ? (
                <CircularProgress size={24} color="inherit" />
              ) : (
                '注册'
              )}
            </Button>
          </Box>

          {/* 底部链接 */}
          <Box sx={{ textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              已有账号？{' '}
              <Link component={RouterLink} to="/login" underline="hover">
                去登录
              </Link>
            </Typography>
          </Box>
        </CardContent>
      </Card>

      {/* 风险告知书弹窗 */}
      <RiskDisclosure
        open={riskDialogOpen}
        onAgree={() => {
          setAgreedRisk(true);
          setRiskDialogOpen(false);
        }}
        onClose={() => setRiskDialogOpen(false)}
      />
    </Box>
  );
};

export default Register;
