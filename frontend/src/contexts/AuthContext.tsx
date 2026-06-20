/**
 * 发现者（Discoverer）— 认证上下文
 *
 * Token 存储策略（由 rememberMe 控制）：
 *   - rememberMe = true  → localStorage（浏览器关闭后保留）
 *   - rememberMe = false → sessionStorage（关闭浏览器即清）
 *
 * 页面刷新恢复流程：
 *   1. 优先读取 localStorage 中的 refresh_token
 *   2. 回退读取 sessionStorage 中的 refresh_token
 *   3. 用 refresh_token 换取新 access_token → 获取用户信息
 */
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from 'react';
import type { UserInfo, ApiResponse, TokenResponse } from '../types';

// ── 常量 ──────────────────────────────────────────────

const API_BASE = '/api';
const REFRESH_TOKEN_KEY = 'refresh_token';
const ACCESS_TOKEN_KEY = 'access_token';
const REMEMBER_ME_KEY = 'auth_remember_me';

// ── 状态类型 ──────────────────────────────────────────

interface AuthState {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (
    email: string,
    password: string,
    rememberMe: boolean,
  ) => Promise<{ success: boolean; message: string }>;
  register: (
    email: string,
    password: string,
    agreedRiskDisclosure?: boolean,
  ) => Promise<{ success: boolean; message: string }>;
  logout: () => void;
  refreshToken: () => Promise<string | null>;
  getAccessToken: () => string | null;
}

// ── Context ───────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ── 存储层工具 ────────────────────────────────────────

/** 根据 rememberMe 选择存储后端 */
function getStore(persistent: boolean): Storage {
  return persistent ? localStorage : sessionStorage;
}

/** 读取 token（优先 localStorage → sessionStorage） */
function readToken(key: string): string | null {
  return localStorage.getItem(key) || sessionStorage.getItem(key);
}

// ── 网络请求工具 ──────────────────────────────────────

async function apiPost<T = unknown>(
  path: string,
  body: unknown,
): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      return {
        code: -1,
        data: null as unknown as T,
        message: errorData?.message || `HTTP ${response.status}`,
      };
    }
    return await response.json();
  } catch (err) {
    return {
      code: -1,
      data: null as unknown as T,
      message: err instanceof Error ? err.message : '网络错误',
    };
  }
}

async function apiGet<T = unknown>(
  path: string,
  token: string,
): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => null);
      return {
        code: -1,
        data: null as unknown as T,
        message: errorData?.message || `HTTP ${response.status}`,
      };
    }
    return await response.json();
  } catch (err) {
    return {
      code: -1,
      data: null as unknown as T,
      message: err instanceof Error ? err.message : '网络错误',
    };
  }
}

// ── 清除所有 token ────────────────────────────────────

function clearAllTokens() {
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REMEMBER_ME_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}

// ── Provider ──────────────────────────────────────────

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [accessToken, setAccessToken] = useState<string | null>(null);

  // ── 初始化：从 localStorage / sessionStorage 恢复认证状态 ──
  useEffect(() => {
    let cancelled = false;

    console.log('[DEBUG AuthContext] useEffect初始化开始, 当前user:', user ? user.email : 'null');

    const initAuth = async () => {
      const storedRefreshToken = readToken(REFRESH_TOKEN_KEY);
      const storedAccessToken = readToken(ACCESS_TOKEN_KEY);

      if (!storedRefreshToken) {
        // 没有任何 token，干净的首次访问
        console.log('[DEBUG AuthContext] 无 refresh_token，跳过初始化');
        setIsLoading(false);
        return;
      }

      console.log('[DEBUG AuthContext] 发现 refresh_token，开始恢复...');

      // 方案 A：用已有的 access_token 验证身份
      if (storedAccessToken) {
        console.log('[DEBUG AuthContext] 方案A：用 access_token 验证 /auth/me');
        setAccessToken(storedAccessToken);
        try {
          const meResp = await apiGet<{ id: number; email: string; created_at: string | null }>(
            '/auth/me',
            storedAccessToken,
          );
          if (!cancelled && meResp.code === 0) {
            console.log('[DEBUG AuthContext] 方案A成功，用户已恢复');
            setUser({
              id: meResp.data.id,
              email: meResp.data.email,
              created_at: meResp.data.created_at || '',
            });
            setIsLoading(false);
            return;
          }
          console.log('[DEBUG AuthContext] 方案A失败，code:', meResp.code, 'msg:', meResp.message);
        } catch (err) {
          console.error('[Auth] /auth/me 请求异常:', err);
        }
        // access_token 过期或无效，fall through 到 refresh
      }

      // 方案 B：用 refresh_token 换取新 token
      console.log('[DEBUG AuthContext] 方案B：用 refresh_token 刷新');
      try {
        const refreshResp = await apiPost<TokenResponse>('/auth/refresh', {
          refresh_token: storedRefreshToken,
        });

        if (!cancelled && refreshResp.code === 0 && refreshResp.data) {
          console.log('[DEBUG AuthContext] 方案B刷新成功');
          const newAccessToken = refreshResp.data.access_token;
          const newRefreshToken = refreshResp.data.refresh_token;

          setAccessToken(newAccessToken);

          // 写回原来的存储后端（localStorage 或 sessionStorage）
          const isPersistent = !!localStorage.getItem(REMEMBER_ME_KEY) ||
                               !!localStorage.getItem(REFRESH_TOKEN_KEY);
          const store = getStore(isPersistent);
          store.setItem(REFRESH_TOKEN_KEY, newRefreshToken);
          store.setItem(ACCESS_TOKEN_KEY, newAccessToken);

          // 获取用户信息
          try {
            const meResp = await apiGet<{ id: number; email: string; created_at: string | null }>(
              '/auth/me',
              newAccessToken,
            );
            if (!cancelled && meResp.code === 0) {
              console.log('[DEBUG AuthContext] 方案B /auth/me 成功，设置 user');
              setUser({
                id: meResp.data.id,
                email: meResp.data.email,
                created_at: meResp.data.created_at || '',
              });
            } else {
              console.error('[Auth] refresh 后 /auth/me 失败:', meResp.message);
            }
          } catch (err) {
            console.error('[Auth] refresh 后 /auth/me 异常:', err);
          }
        } else {
          // refresh token 也过期了
          console.warn('[DEBUG AuthContext] ⚠️ 方案B刷新失败，code:', refreshResp.code, '清除所有 token');
          clearAllTokens();
        }
      } catch (err) {
        console.error('[Auth] /auth/refresh 请求异常:', err);
        // 网络异常时不立即清除 token，给一次重试机会
        // 仅在所有重试都失败后才清除
      }

      if (!cancelled) {
        setIsLoading(false);
      }
    };

    initAuth();

    return () => {
      cancelled = true;
    };
  }, []);

  // ── 监听 useApi 发出的 auth:expired 事件 ───────────────
  // useApi.ts 的 _executeRefresh() 在检测到 refresh_token 过期时
  // 会清除 localStorage 并发送此事件，AuthContext 需要同步清除
  // React state，否则 ProtectedLayout 的 isAuthenticated 仍然为 true。
  useEffect(() => {
    const handleExpired = () => {
      console.trace('[DEBUG AuthContext] ⚠️ 收到 auth:expired 事件，清除认证状态');
      setUser(null);
      setAccessToken(null);
    };
    window.addEventListener('auth:expired', handleExpired);
    return () => window.removeEventListener('auth:expired', handleExpired);
  }, []);

  // ── 登录 ────────────────────────────────────────────
  const login = useCallback(
    async (
      email: string,
      password: string,
      rememberMe: boolean,
    ): Promise<{ success: boolean; message: string }> => {
      try {
        const resp = await apiPost<{
          access_token: string;
          refresh_token: string;
          token_type: string;
          user: { id: number; email: string; created_at: string | null };
        }>('/auth/login', { email, password });

        if (resp.code === 0 && resp.data) {
          const { access_token, refresh_token, user: loginUser } = resp.data;

          // 根据 rememberMe 选择存储后端
          const store = getStore(rememberMe);
          store.setItem(REFRESH_TOKEN_KEY, refresh_token);
          store.setItem(ACCESS_TOKEN_KEY, access_token);

          // 记录 rememberMe 选择，供 init 阶段判断
          if (rememberMe) {
            localStorage.setItem(REMEMBER_ME_KEY, '1');
          } else {
            localStorage.removeItem(REMEMBER_ME_KEY);
          }

          setAccessToken(access_token);
          setUser({
            id: loginUser.id,
            email: loginUser.email,
            created_at: loginUser.created_at || '',
          });
          return { success: true, message: resp.message };
        }
        return { success: false, message: resp.message || '登录失败' };
      } catch (err) {
        console.error('[Auth] 登录异常:', err);
        return { success: false, message: '网络错误，请检查连接' };
      }
    },
    [],
  );

  // ── 注册 ────────────────────────────────────────────
  const register = useCallback(
    async (
      email: string,
      password: string,
      agreedRiskDisclosure: boolean = false,
    ): Promise<{ success: boolean; message: string }> => {
      const resp = await apiPost<{ user_id: number; email: string }>(
        '/auth/register',
        { email, password, agreed_risk_disclosure: agreedRiskDisclosure },
      );

      if (resp.code === 0 && resp.data) {
        return { success: true, message: resp.message };
      }
      return { success: false, message: resp.message || '注册失败' };
    },
    [],
  );

  // ── 登出 ────────────────────────────────────────────
  const logout = useCallback(() => {
    setUser(null);
    setAccessToken(null);
    clearAllTokens();
  }, []);

  // ── 刷新 token ──────────────────────────────────────
  const refreshToken = useCallback(async (): Promise<string | null> => {
    const storedRefreshToken = readToken(REFRESH_TOKEN_KEY);
    if (!storedRefreshToken) {
      return null;
    }

    try {
      const resp = await apiPost<TokenResponse>('/auth/refresh', {
        refresh_token: storedRefreshToken,
      });

      if (resp.code === 0 && resp.data) {
        const newAccessToken = resp.data.access_token;
        const newRefreshToken = resp.data.refresh_token;

        setAccessToken(newAccessToken);

        // 写回存储
        const isPersistent = !!localStorage.getItem(REMEMBER_ME_KEY) ||
                             !!localStorage.getItem(REFRESH_TOKEN_KEY);
        const store = getStore(isPersistent);
        store.setItem(REFRESH_TOKEN_KEY, newRefreshToken);
        store.setItem(ACCESS_TOKEN_KEY, newAccessToken);

        return newAccessToken;
      }

      // refresh 失败，清除所有 token
      console.warn('[Auth] refresh_token 刷新失败，清除认证状态');
      clearAllTokens();
      setAccessToken(null);
      setUser(null);
      return null;
    } catch (err) {
      console.error('[Auth] refresh_token 刷新异常:', err);
      return null;
    }
  }, []);

  // ── 获取当前 access_token（供 useApi 等使用）─────────
  const getAccessToken = useCallback((): string | null => {
    return accessToken || readToken(ACCESS_TOKEN_KEY);
  }, [accessToken]);

  // ── Context value ───────────────────────────────────
  const value: AuthContextValue = {
    user,
    isAuthenticated: user !== null,
    isLoading,
    login,
    register,
    logout,
    refreshToken,
    getAccessToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// ── Hook ──────────────────────────────────────────────

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// ── 导出独立函数供非 hook 场景使用 ─────────────────────

export function getStoredToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY) || sessionStorage.getItem(ACCESS_TOKEN_KEY);
}
