import { ReactNode, useCallback, useEffect, useMemo, useState } from 'react';

import { C2Connection, C2ConnectionContext } from './c2ConnectionContext';
import {
  readStoredC2Connection,
  removeStoredC2Connection,
  writeStoredC2Connection,
} from './c2ConnectionStorage';

interface HealthPayload {
  access_token?: string;
  expires_at?: string;
  service?: string;
  service_role?: string;
  status?: string;
  token_type?: 'bearer';
}

const MAX_BROWSER_TIMEOUT_MS = 2_147_483_647;

function normalizeBaseUrl(value: string): string {
  const trimmed = value.trim().replace(/\/+$/, '');
  if (!trimmed) {
    throw new Error('C2 backend URL is required.');
  }
  const parsed = new URL(trimmed);
  if (!['http:', 'https:'].includes(parsed.protocol)) {
    throw new Error('C2 backend URL must use http or https.');
  }
  return parsed.toString().replace(/\/+$/, '');
}

export function C2ConnectionProvider({ children }: { children: ReactNode }) {
  const [connection, setConnection] = useState<C2Connection | null>(() => readStoredC2Connection());
  const [error, setError] = useState('');
  const [isChecking, setIsChecking] = useState(false);

  const checkConnection = useCallback(async (baseUrl: string, password: string) => {
    const normalizedUrl = normalizeBaseUrl(baseUrl);
    if (!password.trim()) {
      const message = 'C2 connection password is required.';
      setError(message);
      throw new Error(message);
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 5_000);
    setError('');
    setIsChecking(true);

    try {
      const response = await fetch(`${normalizedUrl}/api/v1/c2/connect`, {
        body: JSON.stringify({ password }),
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        method: 'POST',
        signal: controller.signal,
      });

      let payload: HealthPayload = {};
      try {
        payload = (await response.json()) as HealthPayload;
      } catch {
        payload = {};
      }
      if (!response.ok) {
        const detail = typeof payload === 'object' && payload !== null && 'detail' in payload ? String(payload.detail) : '';
        throw new Error(detail || `C2 authentication failed with HTTP ${response.status}.`);
      }
      if (!payload.access_token || !payload.expires_at) {
        throw new Error('C2 backend did not return a session token.');
      }

      const nextConnection: C2Connection = {
        accessToken: payload.access_token,
        baseUrl: normalizedUrl,
        connectedAt: new Date().toISOString(),
        expiresAt: payload.expires_at,
        service: payload.service,
        serviceRole: payload.service_role,
        status: payload.status,
        tokenType: payload.token_type ?? 'bearer',
      };
      writeStoredC2Connection(nextConnection);
      setConnection(nextConnection);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to connect to C2 backend.';
      setError(message);
      throw caught;
    } finally {
      window.clearTimeout(timeout);
      setIsChecking(false);
    }
  }, []);

  const disconnect = useCallback(() => {
    removeStoredC2Connection();
    setConnection(null);
    setError('');
  }, []);

  useEffect(() => {
    if (!connection) {
      return undefined;
    }

    const expiresInMs = Date.parse(connection.expiresAt) - Date.now();
    if (expiresInMs > MAX_BROWSER_TIMEOUT_MS) {
      return undefined;
    }

    const expiryTimer = window.setTimeout(disconnect, Math.max(0, expiresInMs));
    return () => window.clearTimeout(expiryTimer);
  }, [connection, disconnect]);

  const value = useMemo(
    () => ({ checkConnection, connection, disconnect, error, isChecking }),
    [checkConnection, connection, disconnect, error, isChecking],
  );

  return <C2ConnectionContext.Provider value={value}>{children}</C2ConnectionContext.Provider>;
}
