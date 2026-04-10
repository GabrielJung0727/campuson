'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { api, clearTokens, setTokens } from '@/lib/api';

interface User {
  id: string;
  email: string;
  name: string;
  department: string;
  role: string;
  status: string;
  student_no: string | null;
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: Record<string, unknown>) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // 앱 로드 시 토큰이 있으면 사용자 정보 복원
  useEffect(() => {
    const stored = localStorage.getItem('user');
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        /* ignore */
      }
    }
    // /users/me로 실제 검증
    api
      .getMe()
      .then((data: unknown) => {
        const u = data as User;
        setUser(u);
        localStorage.setItem('user', JSON.stringify(u));
      })
      .catch(() => {
        clearTokens();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = (await api.login({ email, password })) as {
      access_token: string;
      refresh_token: string;
      user: User;
    };
    setTokens(data.access_token, data.refresh_token);
    setUser(data.user);
    localStorage.setItem('user', JSON.stringify(data.user));
  }, []);

  const register = useCallback(async (body: Record<string, unknown>) => {
    const data = (await api.register(body)) as {
      access_token: string;
      refresh_token: string;
      user: User;
    };
    setTokens(data.access_token, data.refresh_token);
    setUser(data.user);
    localStorage.setItem('user', JSON.stringify(data.user));
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    window.location.href = '/login';
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
