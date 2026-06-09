import type { AuthSession } from './api';

export const AUTH_STORAGE_KEY = 'xero.auth.session';
export const AUTH_SESSION_EXPIRED_EVENT = 'xero:auth-session-expired';

export function readStoredAuthSession(): AuthSession | null {
  const raw = window.sessionStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed.accessToken || Date.parse(parsed.expiresAt) <= Date.now()) {
      clearStoredAuthSession();
      return null;
    }
    return parsed;
  } catch {
    clearStoredAuthSession();
    return null;
  }
}

export function writeStoredAuthSession(session: AuthSession): void {
  window.sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredAuthSession(): void {
  window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
}

export function emitAuthSessionExpired(): void {
  window.dispatchEvent(new CustomEvent(AUTH_SESSION_EXPIRED_EVENT));
}
