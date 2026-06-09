import { useCallback, useEffect, useMemo, useState } from 'react';
import { ReactNode } from 'react';

import { loginOperator } from './api';
import { AuthContext } from './authContext';
import {
  AUTH_SESSION_EXPIRED_EVENT,
  clearStoredAuthSession,
  readStoredAuthSession,
  writeStoredAuthSession,
} from './authStorage';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState(() => readStoredAuthSession());

  useEffect(() => {
    const handleSessionExpired = () => {
      setSession(null);
    };

    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => {
      window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const nextSession = await loginOperator(username, password);
    writeStoredAuthSession(nextSession);
    setSession(nextSession);
  }, []);

  const logout = useCallback(() => {
    clearStoredAuthSession();
    setSession(null);
  }, []);

  const value = useMemo(() => ({ session, login, logout }), [login, logout, session]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
