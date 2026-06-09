import { describe, expect, it } from 'vitest';

import {
  AUTH_STORAGE_KEY,
  clearStoredAuthSession,
  readStoredAuthSession,
  writeStoredAuthSession,
} from './authStorage';
import type { AuthSession } from './api';

function makeSession(overrides: Partial<AuthSession> = {}): AuthSession {
  return {
    accessToken: 'test-token',
    expiresAt: new Date(Date.now() + 60_000).toISOString(),
    operator: {
      created_at: new Date().toISOString(),
      id: '00000000-0000-0000-0000-000000000001',
      is_enabled: true,
      role: 'admin',
      username: 'admin',
    },
    tokenType: 'bearer',
    ...overrides,
  };
}

describe('authStorage', () => {
  it('writes, reads, and clears a valid session', () => {
    const session = makeSession();

    writeStoredAuthSession(session);

    expect(readStoredAuthSession()).toEqual(session);

    clearStoredAuthSession();

    expect(readStoredAuthSession()).toBeNull();
  });

  it('rejects expired sessions and removes them from storage', () => {
    writeStoredAuthSession(makeSession({ expiresAt: new Date(Date.now() - 1_000).toISOString() }));

    expect(readStoredAuthSession()).toBeNull();
    expect(window.sessionStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });

  it('rejects malformed sessions and removes them from storage', () => {
    window.sessionStorage.setItem(AUTH_STORAGE_KEY, '{not-json');

    expect(readStoredAuthSession()).toBeNull();
    expect(window.sessionStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });
});
