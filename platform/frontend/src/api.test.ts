import { describe, expect, it, vi } from 'vitest';

import {
  AUTH_SESSION_EXPIRED_EVENT,
  AUTH_STORAGE_KEY,
  writeStoredAuthSession,
} from './authStorage';
import {
  getCurrentOperator,
  loginOperator,
} from './api';
import type {
  AuthSession,
  Operator,
} from './api';

const operator: Operator = {
  created_at: new Date().toISOString(),
  id: '00000000-0000-0000-0000-000000000001',
  is_enabled: true,
  role: 'admin',
  username: 'admin',
};

function makeSession(): AuthSession {
  return {
    accessToken: 'stored-token',
    expiresAt: new Date(Date.now() + 60_000).toISOString(),
    operator,
    tokenType: 'bearer',
  };
}

function headersFromFirstFetchCall(fetchMock: ReturnType<typeof vi.fn>): Headers {
  const init = fetchMock.mock.calls[0][1] as RequestInit;
  return new Headers(init.headers);
}

describe('api client', () => {
  it('attaches a stored Bearer token to authenticated API calls', async () => {
    writeStoredAuthSession(makeSession());
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(operator), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getCurrentOperator();

    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer stored-token');
  });

  it('does not attach Authorization to login requests', async () => {
    writeStoredAuthSession(makeSession());
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          access_token: 'new-token',
          expires_at: new Date(Date.now() + 60_000).toISOString(),
          operator,
          token_type: 'bearer',
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await loginOperator('admin', 'admin');

    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBeNull();
  });

  it('clears stored auth and emits an expiry event for authenticated 401 responses', async () => {
    writeStoredAuthSession(makeSession());
    const listener = vi.fn();
    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, listener);
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ detail: 'Token expired' }), { status: 401 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getCurrentOperator()).rejects.toThrow('Token expired');

    expect(window.sessionStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, listener);
  });

  it('keeps login 401 responses in the invalid credentials flow', async () => {
    writeStoredAuthSession(makeSession());
    const listener = vi.fn();
    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, listener);
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ detail: 'Invalid username or password' }), { status: 401 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(loginOperator('admin', 'wrong')).rejects.toThrow('Invalid username or password');

    expect(window.sessionStorage.getItem(AUTH_STORAGE_KEY)).not.toBeNull();
    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, listener);
  });
});
