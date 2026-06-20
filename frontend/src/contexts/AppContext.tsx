/**
 * 发现者（Discoverer）— 全局应用状态 Context
 *
 * 管理：
 *  - 当前活跃 Tab
 *  - 回测历史记录
 *  - 系统状态
 *  - 全局加载/错误状态
 */

import React, { createContext, useContext, useReducer, useCallback, ReactNode } from 'react';
import type { BacktestHistoryItem, SystemStatus } from '../types';

// ── 状态类型 ──────────────────────────────────────────

interface AppState {
  /** 当前活跃 Tab 索引 */
  activeTab: number;
  /** 回测历史（最多保留50条） */
  history: BacktestHistoryItem[];
  /** 系统状态 */
  systemStatus: SystemStatus | null;
  /** 全局加载 */
  isLoading: boolean;
  /** 全局错误 */
  error: string | null;
}

type AppAction =
  | { type: 'SET_ACTIVE_TAB'; payload: number }
  | { type: 'ADD_HISTORY'; payload: BacktestHistoryItem }
  | { type: 'CLEAR_HISTORY' }
  | { type: 'SET_SYSTEM_STATUS'; payload: SystemStatus }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null };

// ── 初始状态 ──────────────────────────────────────────

const initialState: AppState = {
  activeTab: 0,
  history: [],
  systemStatus: null,
  isLoading: false,
  error: null,
};

// ── Reducer ───────────────────────────────────────────

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_ACTIVE_TAB':
      return { ...state, activeTab: action.payload };
    case 'ADD_HISTORY': {
      const newHistory = [action.payload, ...state.history].slice(0, 50);
      return { ...state, history: newHistory };
    }
    case 'CLEAR_HISTORY':
      return { ...state, history: [] };
    case 'SET_SYSTEM_STATUS':
      return { ...state, systemStatus: action.payload };
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    default:
      return state;
  }
}

// ── Context ───────────────────────────────────────────

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
  setActiveTab: (tab: number) => void;
  addHistory: (item: BacktestHistoryItem) => void;
  clearHistory: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

// ── Provider ──────────────────────────────────────────

export const AppProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialState);

  const setActiveTab = useCallback((tab: number) => {
    dispatch({ type: 'SET_ACTIVE_TAB', payload: tab });
  }, []);

  const addHistory = useCallback((item: BacktestHistoryItem) => {
    dispatch({ type: 'ADD_HISTORY', payload: item });
  }, []);

  const clearHistory = useCallback(() => {
    dispatch({ type: 'CLEAR_HISTORY' });
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    dispatch({ type: 'SET_LOADING', payload: loading });
  }, []);

  const setError = useCallback((error: string | null) => {
    dispatch({ type: 'SET_ERROR', payload: error });
  }, []);

  return (
    <AppContext.Provider
      value={{ state, dispatch, setActiveTab, addHistory, clearHistory, setLoading, setError }}
    >
      {children}
    </AppContext.Provider>
  );
};

// ── Hook ──────────────────────────────────────────────

export const useAppContext = (): AppContextType => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};
