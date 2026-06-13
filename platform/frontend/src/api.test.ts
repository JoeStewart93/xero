import { describe, expect, it, vi } from 'vitest';

import {
  AUTH_SESSION_EXPIRED_EVENT,
  AUTH_STORAGE_KEY,
  writeStoredAuthSession,
} from './authStorage';
import {
  archiveTrafficProfile,
  assignBeaconTrafficProfile,
  cancelTask,
  clearBeaconTrafficProfile,
  cloneTrafficProfile,
  closeRegistrySession,
  closeShellSession,
  createScanJob,
  createBeaconBuild,
  createFileBrowserSession,
  createRegistrySession,
  createShellSession,
  createTask,
  createTrafficProfile,
  createWorkerPairingToken,
  downloadBeaconBuildArtifact,
  downloadTaskResultArtifact,
  downloadTaskResultText,
  getAsset,
  getAssets,
  getBeaconBuilds,
  getBeaconBuildTargets,
  getBeaconActivity,
  getC2Beacons,
  getC2Beacon,
  getCurrentOperator,
  getDashboardSummary,
  getModules,
  getProtocolInfo,
  getProtocolSecurityEvents,
  getShellSession,
  getScanJob,
  getScanJobs,
  getScanResultChunks,
  getTaskAuditEvents,
  getTaskResult,
  getTaskResultChunks,
  getTaskResults,
  getTasks,
  getTrafficProfiles,
  getTrafficProfileVersions,
  getTransportStatus,
  killBeacon,
  launchInfrastructureWorker,
  loginOperator,
  rollbackTrafficProfile,
  shellSessionWebSocketUrl,
  updateTrafficProfile,
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

  it('calls C2 dashboard summary endpoint with bearer auth', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          beacons: { offline: 1, online: 2, total: 3 },
          c2_health: {
            checks: {
              postgres: { status: 'healthy' },
              redis: { status: 'healthy' },
            },
            status: 'ready',
          },
          generated_at: new Date().toISOString(),
          recent_activity: [],
          recent_tasks: [],
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const summary = await getDashboardSummary('http://c2.local:8001/', 'c2-token');

    const [url] = firstFetchCall(fetchMock);
    expect(url).toBe('http://c2.local:8001/api/v1/dashboard/summary');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(summary.beacons.total).toBe(3);
  });

  it('calls C2 asset inventory endpoints with bearer auth', async () => {
    const assetPayload = {
      asset_type: 'beacon_host',
      created_at: new Date().toISOString(),
      display_name: 'alpha.corp.local',
      domain: 'corp.local',
      first_seen: new Date().toISOString(),
      hostname: 'alpha.corp.local',
      id: 'asset-one',
      last_seen: new Date().toISOString(),
      metadata: {},
      os: 'Windows 11',
      primary_ip: '10.20.0.5',
      role: 'beacon',
      source: 'beacon',
      updated_at: new Date().toISOString(),
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [assetPayload], limit: 25, offset: 0, total: 1 }), { status: 200 }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ...assetPayload,
            identifiers: [],
            linked_beacons: [],
            observations: [],
            relationships: [],
          }),
          { status: 200 },
        ),
      );
    vi.stubGlobal('fetch', fetchMock);

    await getAssets('http://c2.local:8001/', 'c2-token', {
      limit: 25,
      offset: 0,
      q: 'alpha',
      source: 'beacon',
      type: 'beacon_host',
    });
    await getAsset('http://c2.local:8001/', 'c2-token', 'asset-one');

    expect(fetchMock.mock.calls[0][0]).toBe(
      'http://c2.local:8001/api/v1/assets?type=beacon_host&source=beacon&q=alpha&limit=25&offset=0',
    );
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(fetchMock.mock.calls[1][0]).toBe('http://c2.local:8001/api/v1/assets/asset-one');
  });

  it('calls C2 module and scan job endpoints with bearer auth', async () => {
    const scanJobPayload = {
      actor_subject: 'operator-one',
      args: {
        execution_target: 'auto',
        max_threads: 8,
        port_range: '80,443',
        targets: ['127.0.0.1'],
        timeout_ms: 1000,
      },
      completed_at: null,
      created_at: new Date().toISOString(),
      error_message: null,
      execution_target_requested: 'auto',
      execution_target_resolved: 'embedded-c2',
      id: 'scan-one',
      module: 'builtin.portscan',
      progress_completed: 0,
      progress_total: 2,
      queued_at: new Date().toISOString(),
      results: [],
      started_at: null,
      state_counts: { closed: 0, filtered: 0, open: 0 },
      status: 'queued',
      summary: {},
      updated_at: new Date().toISOString(),
      worker_id: 'worker-one',
    };
    const chunkPayload = {
      created_at: new Date().toISOString(),
      emitted_at: new Date().toISOString(),
      id: 'chunk-one',
      kind: 'progress',
      payload: { results: [] },
      probes_completed: 2,
      probes_total: 2,
      scan_job_id: 'scan-one',
      sequence: 1,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ id: 'builtin.portscan', name: 'Port Scan' }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(scanJobPayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...scanJobPayload, id: 'service-enum-one', module: 'builtin.serviceenum' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [scanJobPayload] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...scanJobPayload, status: 'completed' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [chunkPayload] }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getModules('http://c2.local:8001/', 'c2-token');
    await createScanJob('http://c2.local:8001/', 'c2-token', {
      max_threads: 8,
      port_range: '80,443',
      targets: ['127.0.0.1'],
      timeout_ms: 1000,
    });
    await createScanJob('http://c2.local:8001/', 'c2-token', 'builtin.serviceenum', {
      host: '127.0.0.1',
      ports: [80],
      probe_timeout_ms: 1000,
      source_scan_job_id: 'scan-one',
    });
    await getScanJobs('http://c2.local:8001/', 'c2-token', { limit: 5, status: 'completed' });
    await getScanJob('http://c2.local:8001/', 'c2-token', 'scan-one');
    await getScanResultChunks('http://c2.local:8001/', 'c2-token', 'scan-one');

    expect(fetchMock.mock.calls[0][0]).toBe('http://c2.local:8001/api/v1/modules');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(fetchMock.mock.calls[1][0]).toBe('http://c2.local:8001/api/v1/scan-jobs');
    expect(JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string)).toEqual({
      args: {
        execution_target: 'auto',
        max_threads: 8,
        port_range: '80,443',
        targets: ['127.0.0.1'],
        timeout_ms: 1000,
      },
      module: 'builtin.portscan',
    });
    expect(fetchMock.mock.calls[2][0]).toBe('http://c2.local:8001/api/v1/scan-jobs');
    expect(JSON.parse((fetchMock.mock.calls[2][1] as RequestInit).body as string)).toEqual({
      args: {
        execution_target: 'auto',
        host: '127.0.0.1',
        ports: [80],
        probe_timeout_ms: 1000,
        source_scan_job_id: 'scan-one',
      },
      module: 'builtin.serviceenum',
    });
    expect(fetchMock.mock.calls[3][0]).toBe('http://c2.local:8001/api/v1/scan-jobs?status=completed&limit=5');
    expect(fetchMock.mock.calls[4][0]).toBe('http://c2.local:8001/api/v1/scan-jobs/scan-one');
    expect(fetchMock.mock.calls[5][0]).toBe('http://c2.local:8001/api/v1/scan-jobs/scan-one/chunks');
  });

  it('calls C2 traffic profile endpoints with bearer auth', async () => {
    const profilePayload = {
      config: {
        headers: { 'X-Profile': 'enabled' },
        jitter: 0.2,
        padding: { enabled: true, max_bytes: 24, min_bytes: 8 },
        paths: {
          frame: '/cdn-cgi/xero/{beacon_id}/frame',
          poll: '/cdn-cgi/xero/{beacon_id}/collect',
          register: '/cdn-cgi/xero/register',
          websocket: '/cdn-cgi/xero/ws',
        },
        sleep_seconds: 30,
        user_agent: 'Profile UA',
      },
      created_at: new Date().toISOString(),
      current_version: 1,
      description: 'Profile',
      id: 'profile-one',
      is_archived: false,
      is_template: false,
      name: 'Profile one',
      template: 'custom',
      updated_at: new Date().toISOString(),
    };
    const beaconPayload = {
      architecture: 'amd64',
      external_ip: null,
      first_seen: new Date().toISOString(),
      hostname: 'host-one',
      id: 'beacon-one',
      internal_ip: '10.0.0.10',
      jitter: 0.2,
      last_seen: new Date().toISOString(),
      machine_fingerprint_hash: 'fingerprint-one',
      os: 'Windows',
      pid: 1234,
      profile_id: 'profile-one',
      profile_name: 'Profile one',
      profile_template: 'custom',
      profile_version: 1,
      protocol_version: 1,
      sleep_seconds: 30,
      status: 'online',
      transport_connected: false,
      transport_last_seen: null,
      transport_mode: 'rest',
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [profilePayload] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(profilePayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...profilePayload, current_version: 2 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ ...profilePayload, version: 1, profile_id: 'profile-one', created_by: 'operator' }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...profilePayload, name: 'Clone' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...profilePayload, current_version: 3 }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...profilePayload, is_archived: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(beaconPayload), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...beaconPayload, profile_id: null, profile_name: null }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getTrafficProfiles('http://c2.local:8001/', 'c2-token');
    await createTrafficProfile('http://c2.local:8001/', 'c2-token', {
      config: profilePayload.config,
      description: 'Profile',
      name: 'Profile one',
      template: 'custom',
    });
    await updateTrafficProfile('http://c2.local:8001/', 'c2-token', 'profile-one', {
      config: profilePayload.config,
      description: 'Updated',
      name: 'Profile one',
    });
    await getTrafficProfileVersions('http://c2.local:8001/', 'c2-token', 'profile-one');
    await cloneTrafficProfile('http://c2.local:8001/', 'c2-token', 'profile-one', 'Clone');
    await rollbackTrafficProfile('http://c2.local:8001/', 'c2-token', 'profile-one', 1);
    await archiveTrafficProfile('http://c2.local:8001/', 'c2-token', 'profile-one');
    await assignBeaconTrafficProfile('http://c2.local:8001/', 'c2-token', 'beacon-one', 'profile-one');
    await clearBeaconTrafficProfile('http://c2.local:8001/', 'c2-token', 'beacon-one');

    expect(fetchMock.mock.calls[0][0]).toBe('http://c2.local:8001/api/v1/traffic-profiles');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(fetchMock.mock.calls[1][0]).toBe('http://c2.local:8001/api/v1/traffic-profiles');
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe('POST');
    expect(fetchMock.mock.calls[2][0]).toBe('http://c2.local:8001/api/v1/traffic-profiles/profile-one');
    expect((fetchMock.mock.calls[2][1] as RequestInit).method).toBe('PATCH');
    expect(fetchMock.mock.calls[3][0]).toBe('http://c2.local:8001/api/v1/traffic-profiles/profile-one/versions');
    expect(fetchMock.mock.calls[4][0]).toBe('http://c2.local:8001/api/v1/traffic-profiles/profile-one/clone');
    expect(fetchMock.mock.calls[5][0]).toBe('http://c2.local:8001/api/v1/traffic-profiles/profile-one/rollback');
    expect(fetchMock.mock.calls[6][0]).toBe('http://c2.local:8001/api/v1/traffic-profiles/profile-one');
    expect((fetchMock.mock.calls[6][1] as RequestInit).method).toBe('DELETE');
    expect(fetchMock.mock.calls[7][0]).toBe('http://c2.local:8001/api/v1/beacons/beacon-one/profile');
    expect(JSON.parse((fetchMock.mock.calls[7][1] as RequestInit).body as string)).toEqual({ profile_id: 'profile-one' });
    expect(fetchMock.mock.calls[8][0]).toBe('http://c2.local:8001/api/v1/beacons/beacon-one/profile');
    expect((fetchMock.mock.calls[8][1] as RequestInit).method).toBe('DELETE');
  });

  it('calls C2 beacon inventory endpoints with filters and lifecycle actions', async () => {
    const beaconPayload = {
      architecture: 'amd64',
      external_ip: '198.51.100.10',
      first_seen: new Date().toISOString(),
      hostname: 'host-one',
      id: 'beacon-one',
      internal_ip: '10.0.0.10',
      jitter: 0.2,
      last_seen: new Date().toISOString(),
      machine_fingerprint_hash: 'fingerprint-one',
      os: 'Windows',
      pid: 1234,
      profile_id: null,
      profile_name: null,
      profile_template: null,
      profile_version: null,
      protocol_version: 1,
      removed_at: null,
      removed_by: null,
      removed_reason: null,
      sleep_seconds: 30,
      status: 'online',
      transport_connected: true,
      transport_last_seen: new Date().toISOString(),
      transport_mode: 'websocket',
    };
    const activityPayload = {
      beacon_id: 'beacon-one',
      detail: 'operator',
      id: 'activity-one',
      label: 'Beacon removed from active inventory',
      occurred_at: new Date().toISOString(),
      session_id: null,
      status: 'removed',
      task_id: null,
      type: 'beacon.killed',
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [beaconPayload] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...beaconPayload, removed_at: new Date().toISOString() }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        beacon: { ...beaconPayload, removed_at: new Date().toISOString() },
        cancelled_tasks: 1,
        closed_sessions: 2,
        status: 'removed',
      }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [activityPayload] }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getC2Beacons('http://c2.local:8001/', 'c2-token', { includeRemoved: true, status: 'online' });
    await getC2Beacon('http://c2.local:8001/', 'c2-token', 'beacon-one', true);
    await killBeacon('http://c2.local:8001/', 'c2-token', 'beacon-one');
    await getBeaconActivity('http://c2.local:8001/', 'c2-token', 'beacon-one', 15);

    expect(fetchMock.mock.calls[0][0]).toBe('http://c2.local:8001/api/v1/beacons?include_removed=true&status=online');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(fetchMock.mock.calls[1][0]).toBe('http://c2.local:8001/api/v1/beacons/beacon-one?include_removed=true');
    expect(fetchMock.mock.calls[2][0]).toBe('http://c2.local:8001/api/v1/beacons/beacon-one/kill');
    expect((fetchMock.mock.calls[2][1] as RequestInit).method).toBe('POST');
    expect(fetchMock.mock.calls[3][0]).toBe('http://c2.local:8001/api/v1/beacons/beacon-one/activity?limit=15');
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
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(resultBlob, { status: 200 }))
      .mockResolvedValueOnce(new Response(resultBlob, { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getTasks('http://c2.local:8001/', 'c2-token', {
      beaconId: 'beacon-one',
      command: 'whoami',
      limit: 10,
      status: 'queued',
    });
    await createTask(
      'http://c2.local:8001/',
      'c2-token',
      'beacon-one',
      'shell',
      { command: 'whoami', shell_type: 'auto', timeout_seconds: 60 },
      'urgent',
    );
    await cancelTask('http://c2.local:8001/', 'c2-token', 'task-one');
    await getTaskAuditEvents('http://c2.local:8001/', 'c2-token', 'task-one', 5);
    await getTaskResult('http://c2.local:8001/', 'c2-token', 'task-one');
    await getTaskResults('http://c2.local:8001/', 'c2-token', { beaconId: 'beacon-one', limit: 5, status: 'completed' });
    await getTaskResultChunks('http://c2.local:8001/', 'c2-token', 'task-one', {
      afterSequence: 2,
      limit: 20,
      stream: 'stdout',
      uploadId: 'upload-one',
    });
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
    expect(fetchMock.mock.calls[6][0]).toBe(
      'http://c2.local:8001/api/v1/tasks/task-one/result/chunks?stream=stdout&upload_id=upload-one&after_sequence=2&limit=20',
    );
    expect(fetchMock.mock.calls[7][0]).toBe('http://c2.local:8001/api/v1/tasks/task-one/result/download?stream=stdout');
    expect(fetchMock.mock.calls[8][0]).toBe('http://c2.local:8001/api/v1/tasks/task-one/result/artifacts/artifact-one');
  });

  it('calls C2 session endpoints and builds the session websocket URL', async () => {
    const shellSession = {
      actor_subject: 'operator-one',
      beacon_id: 'beacon-one',
      close_reason: null,
      closed_at: null,
      cols: 120,
      created_at: new Date().toISOString(),
      detached_at: null,
      id: 'session-one',
      last_activity_at: new Date().toISOString(),
      opened_at: new Date().toISOString(),
      rows: 32,
      session_type: 'shell',
      shell_type: 'powershell',
      status: 'opening',
      updated_at: new Date().toISOString(),
    };
    const registrySession = {
      actor_subject: 'operator-one',
      beacon_id: 'beacon-one',
      close_reason: null,
      closed_at: null,
      created_at: new Date().toISOString(),
      detached_at: null,
      id: 'registry-session-one',
      last_activity_at: new Date().toISOString(),
      opened_at: new Date().toISOString(),
      session_type: 'registry',
      status: 'opening',
      updated_at: new Date().toISOString(),
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(shellSession), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...shellSession, status: 'open' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...shellSession, close_reason: 'operator', status: 'closed' }), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            ...shellSession,
            cols: undefined,
            rows: undefined,
            session_type: 'file_browser',
            shell_type: undefined,
          }),
          { status: 200 },
        ),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(registrySession), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...registrySession, close_reason: 'operator', status: 'closed' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await createShellSession('http://c2.local:8001/', 'c2-token', {
      beacon_id: 'beacon-one',
      cols: 120,
      rows: 32,
      shell_type: 'powershell',
    });
    await getShellSession('http://c2.local:8001/', 'c2-token', 'session-one');
    await closeShellSession('http://c2.local:8001/', 'c2-token', 'session-one');
    await createFileBrowserSession('http://c2.local:8001/', 'c2-token', {
      beacon_id: 'beacon-one',
      root_path: '/home',
    });
    await createRegistrySession('http://c2.local:8001/', 'c2-token', {
      beacon_id: 'beacon-one',
    });
    await closeRegistrySession('http://c2.local:8001/', 'c2-token', 'registry-session-one');

    expect(fetchMock.mock.calls[0][0]).toBe('http://c2.local:8001/api/v1/sessions/shell');
    expect(headersFromFirstFetchCall(fetchMock).get('Authorization')).toBe('Bearer c2-token');
    expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual({
      beacon_id: 'beacon-one',
      cols: 120,
      rows: 32,
      shell_type: 'powershell',
    });
    expect(fetchMock.mock.calls[1][0]).toBe('http://c2.local:8001/api/v1/sessions/session-one');
    expect(fetchMock.mock.calls[2][0]).toBe('http://c2.local:8001/api/v1/sessions/session-one');
    expect((fetchMock.mock.calls[2][1] as RequestInit).method).toBe('DELETE');
    expect(fetchMock.mock.calls[3][0]).toBe('http://c2.local:8001/api/v1/sessions/file-browser');
    expect(JSON.parse((fetchMock.mock.calls[3][1] as RequestInit).body as string)).toEqual({
      beacon_id: 'beacon-one',
      root_path: '/home',
    });
    expect(fetchMock.mock.calls[4][0]).toBe('http://c2.local:8001/api/v1/sessions/registry');
    expect(JSON.parse((fetchMock.mock.calls[4][1] as RequestInit).body as string)).toEqual({
      beacon_id: 'beacon-one',
    });
    expect(fetchMock.mock.calls[5][0]).toBe('http://c2.local:8001/api/v1/sessions/registry-session-one');
    expect((fetchMock.mock.calls[5][1] as RequestInit).method).toBe('DELETE');
    expect(shellSessionWebSocketUrl('https://c2.local:8001/base', 'session one')).toBe('wss://c2.local:8001/ws/sessions/session%20one');
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
