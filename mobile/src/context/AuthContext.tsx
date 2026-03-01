import React, { createContext, useContext, useEffect, useState } from 'react';
import { login as apiLogin, tokenStorage } from '../api/client';

type AuthContextValue = {
  token: string | null;
  loading: boolean;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    tokenStorage.get().then((value) => {
      setToken(value);
      setLoading(false);
    });
  }, []);

  const signIn = async (username: string, password: string) => {
    const t = await apiLogin(username, password);
    await tokenStorage.set(t);
    setToken(t);
  };

  const signOut = async () => {
    await tokenStorage.remove();
    setToken(null);
  };

  return (
    <AuthContext.Provider value={{ token, loading, signIn, signOut }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
