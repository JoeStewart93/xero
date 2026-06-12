import { describe, expect, it, vi } from 'vitest';

import {
  AUTH_SESSION_EXPIRED_EVENT,
  AUTH_STORAGE_KEY,
  writeStoredAuthSession,
} from './authStorage';
import {
  createWorkerPairingToken,
  getCurrentOperator,
  getProtocolInfo,
  getProtocolSecurityEvents,
  getTransportStatus,
  launchInfrastructureWorker,
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

function firstFetchCall(fetchMock: ReturnType<typeof vi.fn>): [string, RequestInit] {
  return fetchMock.mock.calls[0] as [string, RequestInit];
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

  it('calls C2 worker infrastructure endpoints with C2 bearer auth', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          command: 'docker compose -f docker-compose.scanner.yml up -d --build scanner',
          expires_at: new Date(Date.now() + 60_000).toISOString(),
          id: 'pairing-one',
          kind: 'scanner',
          name: 'edge scanner',
          pairing_token: 'pair-token',
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await createWorkerPairingToken('http://c2.local:8001/', 'c2-token', 'scanner', 'edge scanner');

    const [url, init] = firstFetchCall(fetchMock);
    expect(url).toBe('http://c2.local:8001/api/v1/infrastructure/pairing-tokens');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(JSON.parse(init.body as string)).toEqual({
      kind: 'scanner',
      name: 'edge scanner',
    });
  });

  it('sends managed worker launch requests with host port', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          worker: {
            capabilities: [],
            capacity: 1,
            created_at: new Date().toISOString(),
            current_load: 0,
            endpoint: 'http://host.docker.internal:18003',
            id: 'worker-one',
            kind: 'scanner',
            last_error: null,
            last_seen: null,
            managed_host_port: 18003,
            managed_project: 'xero-managed-scanner-test',
            managed_service: 'scanner',
            name: 'managed scanner',
            origin: 'c2-managed',
            status: 'starting',
            updated_at: new Date().toISOString(),
            version: null,
          },
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await launchInfrastructureWorker('http://c2.local:8001', 'c2-token', 'scanner', 'managed scanner', 18003);

    const [url, init] = firstFetchCall(fetchMock);
    expect(url).toBe('http://c2.local:8001/api/v1/infrastructure/workers/launch');
    expect(JSON.parse(init.body as string)).toEqual({
      host_port: 18003,
      kind: 'scanner',
      name: 'managed scanner',
    });
  });

  it('calls C2 protocol metadata endpoint with bearer auth', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          c2_public_key_b64: 'public-key',
          current_version: 1,
          encryption: 'AES-256-GCM',
          frame_harness_enabled: true,
          frame_header_length: 72,
          integrity: 'HMAC-SHA256',
          key_exchange: 'X25519-HKDF-SHA256',
          max_frame_bytes: 1048576,
          supported_versions: [1],
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await getProtocolInfo('http://c2.local:8001/', 'c2-token');

    const [url] = firstFetchCall(fetchMock);
    expect(url).toBe('http://c2.local:8001/api/v1/protocol');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
  });

  it('calls C2 security events endpoint with limit', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ items: [] }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getProtocolSecurityEvents('http://c2.local:8001', 'c2-token', 10);

    const [url] = firstFetchCall(fetchMock);
    expect(url).toBe('http://c2.local:8001/api/v1/security/events?limit=10');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
  });

  it('calls C2 transport status endpoint with bearer auth', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          active_longpoll_requests: 1,
          active_websocket_connections: 2,
          longpoll_max_frame_bytes: 1048576,
          longpoll_timeout_seconds: 60,
          transport_mode_counts: { 'long-poll': 1, rest: 3, websocket: 2 },
          websocket_heartbeat_timeout_seconds: 90,
          websocket_max_message_bytes: 1048576,
          websocket_ping_interval_seconds: 30,
          websocket_ping_timeout_seconds: 30,
          websocket_registration_timeout_seconds: 5,
          websocket_send_queue_size: 32,
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await getTransportStatus('http://c2.local:8001/', 'c2-token');

    const [url] = firstFetchCall(fetchMock);
    expect(url).toBe('http://c2.local:8001/api/v1/transport');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
  });
});
