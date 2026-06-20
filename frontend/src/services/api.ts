/**
 * 灵犀（Lingxi）— API 服务层
 *
 * 提供与后端交互的独立 API 函数，可在组件或非组件上下文中调用。
 * 基于 fetch，统一处理 API_BASE 前缀、JWT 认证和错误响应。
 */

import { getStoredToken } from '../hooks/useApi';
import type { ApiResponse } from '../types';
import type { GridSearchRequest, GridSearchJob } from '../types/gridSearch';

const API_BASE = '/api';

async function request<T = unknown>(
  method: 'GET' | 'POST',
  path: string,
  body?: unknown,
): Promise<ApiResponse<T>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const token = getStoredToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const options: RequestInit = { method, headers };
  if (body) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${path}`, options);

  if (response.status === 401) {
    // P0修复：不再无条件跳转登录页。返回错误让调用方处理，
    // 避免绕过 useApi.ts 的 token 刷新和全局互斥锁。
    console.warn('[api] 收到 401，返回错误（不跳转，由调用方处理）');
    return {
      code: -1,
      data: null as unknown as T,
      message: '登录已过期，请刷新页面后重试',
    };
  }

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

export const api = {
  post: <T = unknown>(path: string, body?: unknown) => request<T>('POST', path, body),
  get: <T = unknown>(path: string) => request<T>('GET', path),
};

// ── 网格搜索 API ──────────────────────────────────────

export async function startGridSearch(req: GridSearchRequest): Promise<{ job_id: string }> {
  const res = await api.post<{ job_id: string }>('/backtest/grid-search', req);
  return res.data;
}

export async function getGridSearchJob(jobId: string): Promise<GridSearchJob> {
  const res = await api.get<GridSearchJob>(`/backtest/grid-search/${jobId}`);
  return res.data;
}
