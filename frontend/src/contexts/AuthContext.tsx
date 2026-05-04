// =============================================================================
// FGA CRM - Auth Provider (composant React seul — useAuth/AuthContext dans useAuth.ts)
// =============================================================================

import { useEffect, useState, useCallback, ReactNode } from 'react';
import { getMe, login as apiLogin } from '../api/client';
import type { User } from '../types';
import { AuthContext } from './useAuth';

const TOKEN_KEY = 'access_token';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    const verify = async () => {
      // Mode dev : tenter de charger le profil sans token (backend AUTH_BYPASS)
      try {
        const userData = await getMe();
        setUser(userData);
        if (!token) {
          localStorage.setItem(TOKEN_KEY, 'dev-bypass');
          setToken('dev-bypass');
        }
      } catch {
        if (token) logout();
      } finally {
        setIsLoading(false);
      }
    };
    verify();
  }, [token, logout]);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await getMe();
      setUser(userData);
    } catch {
      // Silencieux — l'utilisateur reste avec les donnees actuelles
    }
  }, []);

  const login = async (email: string, password: string) => {
    const { access_token } = await apiLogin(email, password);
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    const userData = await getMe();
    setUser(userData);
  };

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}
