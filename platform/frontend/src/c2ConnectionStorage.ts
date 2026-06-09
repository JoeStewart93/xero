import { C2Connection } from './c2ConnectionContext';

export const C2_CONNECTION_STORAGE_KEY = 'xero.c2.connection';

export function isStoredC2ConnectionExpired(connection: C2Connection): boolean {
  const expiresAtMs = Date.parse(connection.expiresAt);
  return Number.isNaN(expiresAtMs) || expiresAtMs <= Date.now();
}

export function readStoredC2Connection(): C2Connection | null {
  const raw = window.localStorage.getItem(C2_CONNECTION_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as C2Connection;
    if (!parsed.accessToken || !parsed.baseUrl || !parsed.connectedAt || !parsed.expiresAt || isStoredC2ConnectionExpired(parsed)) {
      window.localStorage.removeItem(C2_CONNECTION_STORAGE_KEY);
      return null;
    }
    return parsed;
  } catch {
    window.localStorage.removeItem(C2_CONNECTION_STORAGE_KEY);
    return null;
  }
}

export function writeStoredC2Connection(connection: C2Connection): void {
  window.localStorage.setItem(C2_CONNECTION_STORAGE_KEY, JSON.stringify(connection));
}

export function removeStoredC2Connection(): void {
  window.localStorage.removeItem(C2_CONNECTION_STORAGE_KEY);
}
