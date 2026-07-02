import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { apiFetch, clearSessionData } from '../lib/api';

export interface AuthUser {
  user_id: string;
  email: string;
  role: string;
  must_change_password: boolean;
}

interface AuthContextType {
  user: AuthUser | null;
  isLoading: boolean;
  login: (user: AuthUser) => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchMe = async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const res = await apiFetch('/api/auth/me', { signal: controller.signal });
      if (res.ok) {
        setUser(await res.json());
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      clearTimeout(timeout);
    }
  };

  // On mount: distinguish a tab refresh (sessionStorage survives) from a fresh tab
  // open (sessionStorage is cleared on tab close). Fresh tab → force logout so the
  // session cookie left over from the previous tab is revoked before showing the app.
  useEffect(() => {
    const isRefresh = !!sessionStorage.getItem('tab_alive');
    sessionStorage.setItem('tab_alive', 'true');

    if (isRefresh) {
      fetchMe().finally(() => setIsLoading(false));
    } else {
      // Fresh tab: revoke any leftover session and clear locally stored
      // results (they may contain patient details from another user).
      clearSessionData();
      apiFetch('/api/auth/logout', { method: 'POST' })
        .catch(() => {})
        .finally(() => setIsLoading(false));
    }
  }, []);

  const login = (user: AuthUser) => setUser(user);

  const logout = async () => {
    clearSessionData();
    await apiFetch('/api/auth/logout', { method: 'POST' });
    setUser(null);
  };

  const refreshUser = async () => {
    await fetchMe();
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
