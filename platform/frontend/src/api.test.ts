import { describe, expect, it, vi } from 'vitest';

import {
  AUTH_SESSION_EXPIRED_EVENT,
  AUTH_STORAGE_KEY,
  writeStoredAuthSession,
} from './authStorage';
import {
  cancelTask,
  createBeaconBuild,
  createShellTask,
  createWorkerPairingToken,
  downloadBeaconBuildArtifact,
  downloadTaskResultArtifact,
  downloadTaskResultText,
  getBeaconBuilds,
  getBeaconBuildTargets,
  getCurrentOperator,
  getProtocolInfo,
  getProtocolSecurityEvents,
  getTaskAuditEvents,
  getTaskResult,
  getTaskResults,
  getTasks,
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

  it('calls C2 task endpoints with bearer auth', async () => {
    const taskPayload = {
      args: { command: 'whoami', shell_type: 'auto', timeout_seconds: 60 },
      beacon_id: 'beacon-one',
      cancelled_at: null,
      completed_at: null,
      created_at: new Date().toISOString(),
      dispatched_at: null,
      id: 'task-one',
      module: 'shell',
      priority: 'urgent',
      queued_at: new Date().toISOString(),
      running_at: null,
      status: 'queued',
      updated_at: new Date().toISOString(),
    };
    const taskAuditPayload = {
      actor_subject: 'operator-one',
      beacon_id: 'beacon-one',
      command: 'whoami',
      created_at: new Date().toISOString(),
      event_type: 'task.queued',
      id: 'audit-one',
      message: 'Operator queued shell task.',
      metadata: {},
      module: 'shell',
      occurred_at: new Date().toISOString(),
      task_id: 'task-one',
      task_status: 'queued',
      updated_at: new Date().toISOString(),
    };
    const taskResultPayload = {
      artifacts: [{ available: true, content_type: 'text/plain', filename: 'task-one-stdout.txt', id: 'artifact-one', role: 'stdout', sha256: 'def456', size_bytes: 7 }],
      beacon_id: 'beacon-one',
      completed_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      error_message: null,
      exit_code: 0,
      expires_at: new Date().toISOString(),
      id: 'result-one',
      metadata: {},
      output_sha256: 'def456',
      output_size_bytes: 7,
      status: 'completed',
      stderr: '',
      stderr_sha256: 'empty-sha',
      stderr_size_bytes: 0,
      stdout: 'whoami',
      stdout_sha256: 'def456',
      stdout_size_bytes: 7,
      task_id: 'task-one',
      timed_out: false,
      truncated: false,
      updated_at: new Date().toISOString(),
    };
    const resultBlob = new Blob(['whoami']);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [taskPayload] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(taskPayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...taskPayload, status: 'cancelled' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [taskAuditPayload] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(taskResultPayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [taskResultPayload], next_cursor: null }), { status: 200 }))
      .mockResolvedValueOnce(new Response(resultBlob, { status: 200 }))
      .mockResolvedValueOnce(new Response(resultBlob, { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getTasks('http://c2.local:8001/', 'c2-token', {
      beaconId: 'beacon-one',
      command: 'whoami',
      limit: 10,
      status: 'queued',
    });
    await createShellTask(
      'http://c2.local:8001/',
      'c2-token',
      'beacon-one',
      { command: 'whoami', shell_type: 'auto', timeout_seconds: 60 },
      'urgent',
    );
    await cancelTask('http://c2.local:8001/', 'c2-token', 'task-one');
    await getTaskAuditEvents('http://c2.local:8001/', 'c2-token', 'task-one', 5);
    await getTaskResult('http://c2.local:8001/', 'c2-token', 'task-one');
    await getTaskResults('http://c2.local:8001/', 'c2-token', { beaconId: 'beacon-one', limit: 5, status: 'completed' });
    await downloadTaskResultText('http://c2.local:8001/', 'c2-token', 'task-one', 'stdout');
    await downloadTaskResultArtifact('http://c2.local:8001/', 'c2-token', 'task-one', 'artifact-one');

    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://c2.local:8001/api/v1/tasks?beacon_id=beacon-one&command=whoami&status=queued&limit=10',
    );
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(fetchMock.mock.calls[1][0]).toBe('http://c2.local:8001/api/v1/tasks');
    expect(JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string)).toEqual({
      args: { command: 'whoami', shell_type: 'auto', timeout_seconds: 60 },
      beacon_id: 'beacon-one',
      module: 'shell',
      priority: 'urgent',
    });
    expect(fetchMock.mock.calls[2][0]).toBe('http://c2.local:8001/api/v1/tasks/task-one');
    expect((fetchMock.mock.calls[2][1] as RequestInit).method).toBe('DELETE');
    expect(fetchMock.mock.calls[3][0]).toBe('http://c2.local:8001/api/v1/tasks/task-one/audit?limit=5');
    expect(fetchMock.mock.calls[4][0]).toBe('http://c2.local:8001/api/v1/tasks/task-one/result');
    expect(fetchMock.mock.calls[5][0]).toBe(
      'http://c2.local:8001/api/v1/task-results?beacon_id=beacon-one&status=completed&limit=5',
    );
    expect(fetchMock.mock.calls[6][0]).toBe('http://c2.local:8001/api/v1/tasks/task-one/result/download?stream=stdout');
    expect(fetchMock.mock.calls[7][0]).toBe('http://c2.local:8001/api/v1/tasks/task-one/result/artifacts/artifact-one');
  });

  it('calls C2 beacon build endpoints and downloads artifacts with bearer auth', async () => {
    const buildPayload = {
      artifact_available: true,
      artifact_filename: 'xero-beacon-linux-amd64.bin',
      artifact_sha256: 'abc123',
      artifact_size: 42,
      completed_at: new Date().toISOString(),
      config: { c2_url: 'http://c2.local:8001' },
      created_at: new Date().toISOString(),
      error_message: null,
      id: 'build-one',
      logs_tail: 'ok',
      profile_name: 'default',
      started_at: new Date().toISOString(),
      status: 'succeeded',
      target_arch: 'amd64',
      target_os: 'linux',
      updated_at: new Date().toISOString(),
    };
    const artifact = new Blob(['artifact']);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ arch: 'amd64', extension: '.bin', label: 'Linux amd64', os: 'linux' }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [buildPayload] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(buildPayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(artifact, { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getBeaconBuildTargets('http://c2.local:8001/', 'c2-token');
    await getBeaconBuilds('http://c2.local:8001/', 'c2-token', 5);
    await createBeaconBuild('http://c2.local:8001/', 'c2-token', {
      c2_url: 'http://c2.local:8001',
      target_arch: 'amd64',
      target_os: 'linux',
    });
    await downloadBeaconBuildArtifact('http://c2.local:8001/', 'c2-token', 'build-one');

    expect(fetchMock.mock.calls[0][0]).toBe('http://c2.local:8001/api/v1/beacon-builds/targets');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(fetchMock.mock.calls[1][0]).toBe('http://c2.local:8001/api/v1/beacon-builds?limit=5');
    expect(fetchMock.mock.calls[2][0]).toBe('http://c2.local:8001/api/v1/beacon-builds');
    expect(JSON.parse((fetchMock.mock.calls[2][1] as RequestInit).body as string)).toEqual({
      c2_url: 'http://c2.local:8001',
      target_arch: 'amd64',
      target_os: 'linux',
    });
    expect(fetchMock.mock.calls[3][0]).toBe('http://c2.local:8001/api/v1/beacon-builds/build-one/artifact');
  });
});
