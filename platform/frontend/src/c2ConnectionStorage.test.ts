import { describe, expect, it } from 'vitest';

import type { C2Connection } from './c2ConnectionContext';
import {
  C2_CONNECTION_STORAGE_KEY,
  readStoredC2Connection,
  removeStoredC2Connection,
  writeStoredC2Connection,
} from './c2ConnectionStorage';

function makeConnection(overrides: Partial<C2Connection> = {}): C2Connection {
  return {
    accessToken: 'c2-token',
    baseUrl: 'http://localhost:18001',
    connectedAt: new Date().toISOString(),
    expiresAt: new Date(Date.now() + 60_000).toISOString(),
    service: 'xero-c2-core',
    serviceRole: 'c2',
    status: 'connected',
    tokenType: 'bearer',
    ...overrides,
  };
}

describe('c2ConnectionStorage', () => {
  it('writes, reads, and clears a valid C2 connection', () => {
    const connection = makeConnection();

    writeStoredC2Connection(connection);

    expect(readStoredC2Connection()).toEqual(connection);

    removeStoredC2Connection();

    expect(readStoredC2Connection()).toBeNull();
  });

  it('rejects expired C2 connections and removes them from storage', () => {
    writeStoredC2Connection(makeConnection({ expiresAt: new Date(Date.now() - 1_000).toISOString() }));

    expect(readStoredC2Connection()).toBeNull();
    expect(window.localStorage.getItem(C2_CONNECTION_STORAGE_KEY)).toBeNull();
  });

  it('rejects C2 connections with invalid expiration values and removes them from storage', () => {
    writeStoredC2Connection(makeConnection({ expiresAt: 'not-a-date' }));

    expect(readStoredC2Connection()).toBeNull();
    expect(window.localStorage.getItem(C2_CONNECTION_STORAGE_KEY)).toBeNull();
  });

  it('rejects malformed C2 connections and removes them from storage', () => {
    window.localStorage.setItem(C2_CONNECTION_STORAGE_KEY, '{not-json');

    expect(readStoredC2Connection()).toBeNull();
    expect(window.localStorage.getItem(C2_CONNECTION_STORAGE_KEY)).toBeNull();
  });
});
