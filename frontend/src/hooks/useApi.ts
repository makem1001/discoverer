/**
 * 发现者（Discoverer）— API 调用 Hook
 *
 * 封装 fetch 请求，统一处理：
 *  - 基础 URL 前缀
 *  - JWT 认证拦截（自动附加 Authorization header）
 *  - 401 自动刷新 token + 重试
 *  - JSON 解析
 *  - 错误处理
 *  - 加载状态
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { ApiResponse, TokenResponse, ProgressData } from '../types';

const API_BASE = '/api';

/**
 * 从 localStorage / sessionStorage 读取 access_token。
 * 优先 localStorage（rememberMe），回退 sessionStorage。
 */
export function getStoredToken(): string | null {
  return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
}

/** 读取 refresh_token，优先 localStorage → sessionStorage */
function getStoredRefreshToken(): string | null {
  return localStorage.getItem('refresh_token') || sessionStorage.getItem('refresh_token');
}

/**
 * refresh 结果类型
 */
type RefreshResult =
  | { status: 'success'; token: string }
  | { status: 'expired' }
  | { status: 'transient' };

// ── 全局刷新互斥锁 ──────────────────────────────────────────
// 并发竞态场景：快速切换 tab 时，多个组件同时挂载，各自获得 401，
// 各自发起 refresh 请求。第一个成功的调用会更新 refresh_token，
// 后面的调用使用的是已被替换的旧 refresh_token → 服务端返回 401/403
// → 判定为 expired → 跳转登录页。全局锁确保同一时刻只有一个刷新在飞。
// ─────────────────────────────────────────────────────────────
let _refreshPromise: Promise<RefreshResult> | null = null;

async function _executeRefresh(): Promise<RefreshResult> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) {
    return { status: 'expired' };
  }

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (response.status === 401 || response.status === 403) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      sessionStorage.removeItem('access_token');
      sessionStorage.removeItem('refresh_token');
      // 通知 AuthContext 同步清除 user 状态，防止 ProtectedLayout 仍认为已登录
      window.dispatchEvent(new CustomEvent('auth:expired'));
      return { status: 'expired' };
    }

    if (!response.ok) {
      console.warn(`[Refresh] 后端返回 ${response.status}，保留 token 待重试`);
      return { status: 'transient' };
    }

    const data: ApiResponse<TokenResponse> = await response.json();
    if (data.code === 0 && data.data) {
      const newAccessToken = data.data.access_token;
      const newRefreshToken = data.data.refresh_token;

      const isPersistent = !!localStorage.getItem('refresh_token');
      if (isPersistent) {
        localStorage.setItem('refresh_token', newRefreshToken);
        localStorage.setItem('access_token', newAccessToken);
      } else {
        sessionStorage.setItem('refresh_token', newRefreshToken);
        sessionStorage.setItem('access_token', newAccessToken);
      }
      return { status: 'success', token: newAccessToken };
    }

    return { status: 'transient' };
  } catch {
    console.warn('[Refresh] 网络异常，保留 token 待重试');
    return { status: 'transient' };
  }
}

/**
 * 尝试用 refresh_token 刷新 access_token。
 *
 * 全局互斥：多个并发 401 共享同一个飞行中的 refresh promise，
 * 避免竞态导致误判 expired → 跳转登录页。
 */
async function tryRefreshToken(): Promise<RefreshResult> {
  if (_refreshPromise) {
    return _refreshPromise;
  }
  _refreshPromise = _executeRefresh();
  try {
    return await _refreshPromise;
  } finally {
    _refreshPromise = null;
  }
}

/**
 * useApi Hook
 *
 * 提供 get / post 方法及 loading / error 状态。
 * 自动在请求头附加 JWT token，401 时自动刷新并重试。
 */
export function useApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 通用请求方法
   *
   * @param method    HTTP 方法
   * @param path      API 路径（不含 /api 前缀）
   * @param body      请求体（POST 时）
   * @param retry     是否已重试过（内部使用，防止无限重试）
   */
  const request = useCallback(async <T = unknown>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    path: string,
    body?: unknown,
    retry: boolean = false,
  ): Promise<ApiResponse<T>> => {
    setLoading(true);
    setError(null);

    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      // JWT 认证拦截：从 localStorage 读取 token
      const token = getStoredToken();
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const options: RequestInit = {
        method,
        headers,
      };

      if (body && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(body);
      }

      const response = await fetch(`${API_BASE}${path}`, options);

      // 401 自动刷新 token 并重试（仅重试一次）
      if (response.status === 401 && !retry) {
        console.log('[DEBUG useApi] 收到 401, path=', path, '开始刷新token');
        const refreshResult = await tryRefreshToken();
        console.log('[DEBUG useApi] refresh结果:', refreshResult.status);
        if (refreshResult.status === 'success') {
          console.log('[DEBUG useApi] 刷新成功，重试请求');
          return request<T>(method, path, body, true);
        }
        if (refreshResult.status === 'expired') {
          // refresh_token 本身过期，需要重新登录
          console.trace('[DEBUG useApi] ⚠️ 即将跳转 /login (expired), path=', path);
          window.location.href = '/login';
          return {
            code: -1,
            data: null as unknown as T,
            message: '登录已过期，请重新登录',
          };
        }
        console.log('[DEBUG useApi] 瞬态错误，不跳转, path=', path);
        // transient：网络/后端临时故障，不跳转登录，返回错误让用户重试
        setError('服务暂时不可用，请稍后重试');
        return {
          code: -1,
          data: null as unknown as T,
          message: '服务暂时不可用，请稍后重试',
        };
      }

      if (!response.ok) {
        // 尝试解析后端返回的详细错误信息
        let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorBody = await response.json();
          if (errorBody?.message) errorMsg = errorBody.message;
          else if (errorBody?.detail) errorMsg = errorBody.detail;
        } catch {
          // JSON 解析失败，使用默认消息
        }
        throw new Error(errorMsg);
      }

      const data: ApiResponse<T> = await response.json();
      return data;
    } catch (err) {
      const msg = err instanceof Error ? err.message : '未知错误';
      setError(msg);
      return { code: -1, data: null as unknown as T, message: msg };
    } finally {
      setLoading(false);
    }
  }, []);

  const get = useCallback(
    <T = unknown>(path: string): Promise<ApiResponse<T>> => request<T>('GET', path),
    [request],
  );

  const post = useCallback(
    <T = unknown>(path: string, body?: unknown): Promise<ApiResponse<T>> =>
      request<T>('POST', path, body),
    [request],
  );

  const put = useCallback(
    <T = unknown>(path: string, body?: unknown): Promise<ApiResponse<T>> =>
      request<T>('PUT', path, body),
    [request],
  );

  const del = useCallback(
    <T = unknown>(path: string): Promise<ApiResponse<T>> => request<T>('DELETE', path),
    [request],
  );

  return { get, post, put, del, loading, error, setError };
}

/**
 * useProgressPoll — 进度轮询/模拟 Hook
 *
 * 前端模拟线性增长：isRunning=true 时从0%向90%逼近，
 * isRunning=false 时重置。调用方在收到结果后手动 setProgress(100)。
 *
 * @param taskId     任务标识符（变化时重置进度）
 * @param isRunning  是否正在执行异步任务
 * @param intervalMs 更新间隔（毫秒），默认 500
 * @returns {{ progress, setProgress, status }}
 */
export function useProgressPoll(
  taskId: string,
  isRunning: boolean,
  intervalMs: number = 500,
): {
  progress: number;
  setProgress: React.Dispatch<React.SetStateAction<number>>;
  status: 'idle' | 'running' | 'completed' | 'failed';
} {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle');
  const startTimeRef = useRef<number>(0);

  // 重置当 taskId 或 isRunning 变化
  useEffect(() => {
    if (isRunning) {
      setProgress(0);
      setStatus('running');
      startTimeRef.current = Date.now();

      const timer = setInterval(() => {
        setProgress((prev) => {
          const elapsed = Date.now() - startTimeRef.current;
          const estimated = Math.min(30 + (elapsed / 1000) * 5, 90);
          return Math.max(prev, Math.floor(estimated));
        });
      }, intervalMs);

      return () => clearInterval(timer);
    }
  }, [taskId, isRunning, intervalMs]);

  return { progress, setProgress, status };
}
