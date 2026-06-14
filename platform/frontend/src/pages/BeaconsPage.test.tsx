import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Beacon } from '../api';
import { encodeLaunchArgs } from '../modules/moduleCatalog';
import type { OperatorRealtimeEvent } from '../operatorRealtime';
import { BeaconWorkspacePage } from './BeaconWorkspacePage';
import { BeaconsPage } from './BeaconsPage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
  useRealtime: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  assignBeaconTrafficProfile: vi.fn(),
  cancelTask: vi.fn(),
  clearBeaconTrafficProfile: vi.fn(),
  closeFileBrowserSession: vi.fn(),
  closeRegistrySession: vi.fn(),
  closeShellSession: vi.fn(),
  createFileBrowserSession: vi.fn(),
  createFileTransferUpload: vi.fn(),
  createRegistrySession: vi.fn(),
  createShellSession: vi.fn(),
  createTask: vi.fn(),
  downloadFileTransferArtifact: vi.fn(),
  downloadTaskResultText: vi.fn(),
  getFileTransfer: vi.fn(),
  getBeaconActivity: vi.fn(),
  getModules: vi.fn(),
  getTaskResult: vi.fn(),
  getTaskResultChunks: vi.fn(),
  getTasks: vi.fn(),
  getTrafficProfiles: vi.fn(),
  killBeacon: vi.fn(),
  uploadFileTransferChunk: vi.fn(),
}));

const terminalMocks = vi.hoisted(() => ({
  terminals: [] as Array<{ emitData: (data: string) => void }>,
  writes: [] as string[],
}));

vi.mock('../api', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  assignBeaconTrafficProfile: apiMocks.assignBeaconTrafficProfile,
  cancelTask: apiMocks.cancelTask,
  clearBeaconTrafficProfile: apiMocks.clearBeaconTrafficProfile,
  closeFileBrowserSession: apiMocks.closeFileBrowserSession,
  closeRegistrySession: apiMocks.closeRegistrySession,
  closeShellSession: apiMocks.closeShellSession,
  createFileBrowserSession: apiMocks.createFileBrowserSession,
  createFileTransferUpload: apiMocks.createFileTransferUpload,
  createRegistrySession: apiMocks.createRegistrySession,
  createShellSession: apiMocks.createShellSession,
  createTask: apiMocks.createTask,
  downloadFileTransferArtifact: apiMocks.downloadFileTransferArtifact,
  downloadTaskResultText: apiMocks.downloadTaskResultText,
  getFileTransfer: apiMocks.getFileTransfer,
  getBeaconActivity: apiMocks.getBeaconActivity,
  getModules: apiMocks.getModules,
  getTaskResult: apiMocks.getTaskResult,
  getTaskResultChunks: apiMocks.getTaskResultChunks,
  getTasks: apiMocks.getTasks,
  getTrafficProfiles: apiMocks.getTrafficProfiles,
  killBeacon: apiMocks.killBeacon,
  uploadFileTransferChunk: apiMocks.uploadFileTransferChunk,
}));

vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 120;
    rows = 32;
    private onDataCallback: ((data: string) => void) | null = null;

    constructor() {
      terminalMocks.terminals.push(this);
    }

    dispose() {}
    loadAddon() {}
    open() {}
    reset() {
      terminalMocks.writes = [];
    }
    write(value: string) {
      terminalMocks.writes.push(value);
    }
    onData(callback: (data: string) => void) {
      this.onDataCallback = callback;
      return { dispose() {} };
    }
    emitData(data: string) {
      this.onDataCallback?.(data);
    }
  },
}));

vi.mock('@xterm/addon-fit', () => ({
  FitAddon: class {
    fit() {}
  },
}));

vi.mock('../useAuth', () => ({
  useAuth: mocks.useAuth,
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: mocks.useC2Connection,
}));

vi.mock('../useRealtime', () => ({
  useRealtime: mocks.useRealtime,
}));

const beaconOne: Beacon = {
  architecture: 'x64',
  external_ip: '198.51.100.45',
  first_seen: '2026-06-08T14:00:00Z',
  hostname: 'beacon-alpha',
  id: '11111111-1111-1111-1111-111111111111',
  internal_ip: '10.40.0.8',
  last_seen: '2026-06-08T14:05:00Z',
  machine_fingerprint_hash: 'fingerprint-alpha',
  os: 'Windows 11',
  pid: 4488,
  protocol_version: 1,
  status: 'online',
  transport_connected: true,
  transport_last_seen: '2026-06-08T14:05:30Z',
  transport_mode: 'websocket',
};

const beaconTwo: Beacon = {
  architecture: 'arm64',
  external_ip: null,
  first_seen: '2026-06-08T13:00:00Z',
  hostname: 'beacon-bravo',
  id: '22222222-2222-2222-2222-222222222222',
  internal_ip: '10.40.0.9',
  last_seen: '2026-06-08T13:05:00Z',
  machine_fingerprint_hash: 'fingerprint-bravo',
  os: 'Ubuntu 24.04',
  pid: 9001,
  protocol_version: null,
  status: 'offline',
  transport_connected: false,
  transport_last_seen: '2026-06-08T13:05:00Z',
  transport_mode: 'rest',
};

const beaconThree: Beacon = {
  ...beaconOne,
  hostname: 'beacon-charlie',
  id: '33333333-3333-3333-3333-333333333333',
  internal_ip: '10.40.0.10',
  last_seen: '2026-06-08T14:04:00Z',
  machine_fingerprint_hash: 'fingerprint-charlie',
  protocol_version: 1,
  status: 'offline',
  transport_connected: false,
  transport_last_seen: '2026-06-08T14:04:30Z',
  transport_mode: 'long-poll',
};

const cloudfrontProfile = {
  config: {
    headers: { 'X-Profile': 'enabled' },
    jitter: 0.25,
    padding: { enabled: true, max_bytes: 96, min_bytes: 16 },
    paths: {
      frame: '/cdn-cgi/xero/{beacon_id}/frame',
      poll: '/cdn-cgi/xero/{beacon_id}/collect',
      register: '/cdn-cgi/xero/register',
      websocket: '/cdn-cgi/xero/ws',
    },
    sleep_seconds: 30,
    user_agent: 'Amazon CloudFront',
  },
  created_at: '2026-06-08T14:00:00Z',
  current_version: 1,
  description: 'CloudFront-like lab profile',
  id: 'profile-cloudfront',
  is_archived: false,
  is_template: true,
  name: 'CloudFront CDN',
  template: 'cloudfront',
  updated_at: '2026-06-08T14:00:00Z',
};

const moduleCatalog = {
  items: [
    {
      args_schema: {
        properties: {
          command: { minLength: 1, type: 'string' },
          shell_type: { default: 'auto', enum: ['auto', 'bash', 'cmd', 'powershell'], type: 'string' },
          timeout_seconds: { minimum: 1, type: 'integer' },
        },
        required: ['command'],
        type: 'object',
      },
      category: 'utility',
      description: 'Queue a shell command for an active beacon.',
      example: { args: { command: 'whoami', shell_type: 'auto' }, module: 'shell' },
      execution_kind: 'beacon-task',
      id: 'shell',
      name: 'Shell Command',
      required_capabilities: [],
      result_schema: {},
      source: 'builtin',
      supported_execution_targets: ['beacon'],
      version: '1.0.0',
    },
    {
      args_schema: { properties: {}, type: 'object' },
      category: 'scanning',
      description: 'Scan ports.',
      example: {},
      execution_kind: 'scan-job',
      id: 'builtin.portscan',
      name: 'Port Scan',
      required_capabilities: ['tcp-connect'],
      result_schema: {},
      source: 'builtin',
      supported_execution_targets: ['auto'],
      version: '1.0.0',
    },
  ],
};

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  readyState = FakeWebSocket.CONNECTING;
  sent: string[] = [];

  constructor(
    public readonly url: string,
    public readonly protocols?: string | string[],
  ) {
    FakeWebSocket.instances.push(this);
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.(new Event('open'));
  }

  send(payload: string): void {
    this.sent.push(payload);
  }

  receive(payload: string): void {
    this.onmessage?.({ data: payload } as MessageEvent);
  }

  close(code = 1000): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code } as CloseEvent);
  }
}

const queuedTask = {
  args: { command: 'whoami', shell_type: 'auto', timeout_seconds: 60 },
  beacon_id: beaconOne.id,
  cancelled_at: null,
  completed_at: null,
  created_at: '2026-06-08T14:08:00Z',
  dispatched_at: null,
  id: '44444444-4444-4444-4444-444444444444',
  module: 'shell',
  priority: 'urgent',
  queued_at: '2026-06-08T14:08:00Z',
  running_at: null,
  status: 'queued',
  updated_at: '2026-06-08T14:08:00Z',
} as const;

function taskResultChunk(taskId: string, value: string, sequence = 0) {
  return {
    beacon_id: beaconOne.id,
    chunk: value,
    chunk_sha256: `chunk-sha-${sequence}`,
    created_at: '2026-06-08T14:09:00Z',
    id: `chunk-${sequence}`,
    received_at: '2026-06-08T14:09:00Z',
    sequence,
    stream: 'stdout',
    stream_sha256: null,
    stream_size_bytes: null,
    task_id: taskId,
    task_result_id: '77777777-7777-7777-7777-777777777777',
    total_chunks: 2,
    upload_id: 'upload-one',
  };
}

const shellSession = {
  actor_subject: 'operator-1',
  beacon_id: beaconOne.id,
  close_reason: null,
  closed_at: null,
  cols: 120,
  created_at: '2026-06-08T14:10:00Z',
  detached_at: null,
  id: '99999999-9999-9999-9999-999999999999',
  last_activity_at: '2026-06-08T14:10:00Z',
  opened_at: '2026-06-08T14:10:00Z',
  rows: 32,
  session_type: 'shell',
  shell_type: 'powershell',
  status: 'opening',
  updated_at: '2026-06-08T14:10:00Z',
} as const;

const fileBrowserSession = {
  actor_subject: 'operator-1',
  beacon_id: beaconOne.id,
  close_reason: null,
  closed_at: null,
  created_at: '2026-06-08T14:12:00Z',
  detached_at: null,
  id: '88888888-8888-8888-8888-888888888888',
  last_activity_at: '2026-06-08T14:12:00Z',
  opened_at: '2026-06-08T14:12:00Z',
  session_type: 'file_browser',
  status: 'opening',
  updated_at: '2026-06-08T14:12:00Z',
} as const;

const registrySession = {
  actor_subject: 'operator-1',
  beacon_id: beaconOne.id,
  close_reason: null,
  closed_at: null,
  created_at: '2026-06-08T14:14:00Z',
  detached_at: null,
  id: '77777777-7777-7777-7777-777777777777',
  last_activity_at: '2026-06-08T14:14:00Z',
  opened_at: '2026-06-08T14:14:00Z',
  session_type: 'registry',
  status: 'opening',
  updated_at: '2026-06-08T14:14:00Z',
} as const;

function renderBeaconsPage(initialEntries = ['/beacons']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/beacons" element={<BeaconsPage />} />
        <Route path="/beacons/:beaconId/:operation" element={<BeaconWorkspacePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function beaconRoutesTree(initialEntries = ['/beacons']) {
  return (
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/beacons" element={<BeaconsPage />} />
        <Route path="/beacons/:beaconId/:operation" element={<BeaconWorkspacePage />} />
      </Routes>
    </MemoryRouter>
  );
}

async function openTaskingPanel(beaconId = beaconOne.id) {
  fireEvent.click(screen.getByTestId(`beacon-row-${beaconId}`));
  return screen.findByTestId('task-execution-panel');
}

function makeDataTransfer(): DataTransfer {
  const store = new Map<string, string>();
  return {
    dropEffect: 'copy',
    effectAllowed: 'copy',
    getData: (format: string) => store.get(format) ?? '',
    setData: (format: string, value: string) => {
      store.set(format, value);
    },
  } as DataTransfer;
}

describe('BeaconsPage', () => {
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-06-08T14:10:00Z').getTime());
    FakeWebSocket.instances = [];
    terminalMocks.terminals = [];
    terminalMocks.writes = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.stubGlobal('crypto', {
      subtle: {
        digest: vi.fn(async (_algorithm: string, buffer: ArrayBuffer) => {
          const digest = new Uint8Array(32);
          digest[0] = new Uint8Array(buffer).length;
          return digest.buffer;
        }),
      },
    });
    mocks.useAuth.mockReturnValue({
      logout: vi.fn(),
      session: {
        accessToken: 'local-token',
        expiresAt: '2099-01-01T00:00:00Z',
        operator: { created_at: '2026-06-08T00:00:00Z', id: 'operator-1', is_enabled: true, role: 'admin', username: 'admin' },
        tokenType: 'bearer',
      },
    });
    mocks.useC2Connection.mockReturnValue({
      checkConnection: vi.fn(),
      connection: {
        accessToken: 'c2-token',
        baseUrl: 'http://localhost:18001',
        connectedAt: '2026-06-08T00:00:00Z',
        expiresAt: '2099-01-01T00:00:00Z',
        service: 'xero-c2-core',
        serviceRole: 'c2',
        status: 'connected',
        tokenType: 'bearer',
      },
      disconnect: vi.fn(),
      error: '',
      isChecking: false,
    });
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 0,
      beaconCount: 0,
      beacons: [],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });
    apiMocks.getTasks.mockResolvedValue({ items: [] });
    apiMocks.getModules.mockResolvedValue(moduleCatalog);
    apiMocks.createFileBrowserSession.mockResolvedValue(fileBrowserSession);
    apiMocks.closeFileBrowserSession.mockResolvedValue({ ...fileBrowserSession, close_reason: 'operator', closed_at: '2026-06-08T14:13:00Z', status: 'closed' });
    apiMocks.createRegistrySession.mockResolvedValue(registrySession);
    apiMocks.closeRegistrySession.mockResolvedValue({ ...registrySession, close_reason: 'operator', closed_at: '2026-06-08T14:15:00Z', status: 'closed' });
    apiMocks.createShellSession.mockResolvedValue(shellSession);
    apiMocks.closeShellSession.mockResolvedValue({ ...shellSession, close_reason: 'operator', closed_at: '2026-06-08T14:11:00Z', status: 'closed' });
    apiMocks.createTask.mockResolvedValue(queuedTask);
    apiMocks.cancelTask.mockResolvedValue({ ...queuedTask, cancelled_at: '2026-06-08T14:09:00Z', status: 'cancelled' });
    apiMocks.getTaskResult.mockResolvedValue({
      artifacts: [],
      beacon_id: beaconOne.id,
      completed_at: '2026-06-08T14:09:00Z',
      created_at: '2026-06-08T14:08:00Z',
      error_message: null,
      exit_code: 0,
      expires_at: '2026-06-15T14:09:00Z',
      id: '77777777-7777-7777-7777-777777777777',
      metadata: {},
      output_sha256: 'output-sha',
      output_size_bytes: 12,
      status: 'completed',
      stderr: '',
      stderr_sha256: 'stderr-sha',
      stderr_size_bytes: 0,
      stdout: 'output line\n',
      stdout_sha256: 'stdout-sha',
      stdout_size_bytes: 12,
      task_id: '55555555-5555-5555-5555-555555555555',
      timed_out: false,
      truncated: false,
      updated_at: '2026-06-08T14:09:00Z',
    });
    apiMocks.getTaskResultChunks.mockResolvedValue({ items: [] });
    apiMocks.downloadTaskResultText.mockResolvedValue(new Blob(['output line\n'], { type: 'text/plain' }));
    apiMocks.createFileTransferUpload.mockResolvedValue({
      acked_chunks: 0,
      artifact_id: null,
      beacon_id: beaconOne.id,
      chunk_size_bytes: 4,
      completed_at: null,
      created_at: '2026-06-08T14:16:00Z',
      direction: 'upload',
      error_message: null,
      filename: 'payload.bin',
      id: '99999999-9999-9999-9999-999999999999',
      remote_path: 'payload.bin',
      session_id: fileBrowserSession.id,
      sha256: 'sha',
      size_bytes: 7,
      staged_chunks: 0,
      started_at: null,
      status: 'staged',
      total_chunks: 2,
      updated_at: '2026-06-08T14:16:00Z',
    });
    apiMocks.uploadFileTransferChunk.mockResolvedValue({
      acked_chunks: 0,
      artifact_id: null,
      beacon_id: beaconOne.id,
      chunk_size_bytes: 4,
      completed_at: null,
      created_at: '2026-06-08T14:16:00Z',
      direction: 'upload',
      error_message: null,
      filename: 'payload.bin',
      id: '99999999-9999-9999-9999-999999999999',
      remote_path: 'payload.bin',
      session_id: fileBrowserSession.id,
      sha256: 'sha',
      size_bytes: 7,
      staged_chunks: 1,
      started_at: null,
      status: 'staged',
      total_chunks: 2,
      updated_at: '2026-06-08T14:16:00Z',
    });
    apiMocks.getFileTransfer.mockResolvedValue({
      acked_chunks: 2,
      artifact_id: 'artifact-one',
      beacon_id: beaconOne.id,
      chunk_size_bytes: 4,
      completed_at: '2026-06-08T14:17:00Z',
      created_at: '2026-06-08T14:16:00Z',
      direction: 'download',
      error_message: null,
      filename: 'report.bin',
      id: '88888888-8888-8888-8888-888888888888',
      remote_path: 'report.bin',
      session_id: fileBrowserSession.id,
      sha256: 'sha',
      size_bytes: 8,
      staged_chunks: 2,
      started_at: '2026-06-08T14:16:00Z',
      status: 'completed',
      total_chunks: 2,
      updated_at: '2026-06-08T14:17:00Z',
    });
    apiMocks.downloadFileTransferArtifact.mockResolvedValue(new Blob(['downloaded'], { type: 'application/octet-stream' }));
    apiMocks.getBeaconActivity.mockResolvedValue({
      items: [
        {
          beacon_id: beaconOne.id,
          detail: 'Operator queued shell task.',
          id: 'activity-one',
          label: 'Task whoami queued',
          occurred_at: '2026-06-08T14:09:00Z',
          session_id: null,
          status: 'queued',
          task_id: queuedTask.id,
          type: 'task.queued',
        },
      ],
    });
    apiMocks.getTrafficProfiles.mockResolvedValue({ items: [cloudfrontProfile] });
    apiMocks.killBeacon.mockResolvedValue({
      beacon: {
        ...beaconOne,
        removed_at: '2026-06-08T14:11:00Z',
        removed_by: 'xero-ui-client',
        removed_reason: 'operator',
        status: 'offline',
        transport_connected: false,
      },
      cancelled_tasks: 1,
      closed_sessions: 0,
      status: 'removed',
    });
    apiMocks.assignBeaconTrafficProfile.mockResolvedValue({
      ...beaconOne,
      applied_profile_version: 1,
      jitter: 0.25,
      profile_applied_at: null,
      profile_id: cloudfrontProfile.id,
      profile_name: cloudfrontProfile.name,
      profile_template: cloudfrontProfile.template,
      profile_version: 1,
      sleep_seconds: 30,
    });
    apiMocks.clearBeaconTrafficProfile.mockResolvedValue({ ...beaconOne, profile_id: null, profile_name: null });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('shows the C2 required panel while disconnected', () => {
    mocks.useC2Connection.mockReturnValue({
      checkConnection: vi.fn(),
      connection: null,
      disconnect: vi.fn(),
      error: '',
      isChecking: false,
    });

    renderBeaconsPage();

    expect(screen.getByRole('heading', { name: 'Xero C2 backend required' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Open Settings' })).toBeTruthy();
  });

  it('shows an empty overview when connected without beacons', () => {
    renderBeaconsPage();

    expect(screen.getByTestId('beacons-empty-state').textContent).toContain('No beacons registered.');
  });

  it('renders beacon roster counts in the toolbar', () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 3,
      beacons: [beaconTwo, beaconThree, beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 2,
      status: 'connected',
    });

    renderBeaconsPage();

    const roster = screen.getByTestId('beacon-roster');
    expect(within(roster).getByText('Last Heartbeat')).toBeTruthy();
    expect(within(roster).getByText('beacon-alpha')).toBeTruthy();
    expect(within(roster).getAllByText('Windows 11')).toHaveLength(2);
    expect(screen.getByTestId('beacons-online-count').textContent).toBe('1 online');
    expect(screen.getByTestId(`beacon-relative-${beaconOne.id}`).textContent).toBe('5m ago');
  });

  it('assigns a traffic profile from the beacon operations modal', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage([`/beacons/${beaconOne.id}/controls`]);

    await waitFor(() => {
      expect(apiMocks.getTrafficProfiles).toHaveBeenCalledWith('http://localhost:18001', 'c2-token');
    });

    fireEvent.change(screen.getByLabelText('Beacon traffic profile'), { target: { value: cloudfrontProfile.id } });

    await waitFor(() => {
      expect(apiMocks.assignBeaconTrafficProfile).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        beaconOne.id,
        cloudfrontProfile.id,
      );
    });
    expect(screen.getByText('Assigned CloudFront CDN.')).toBeTruthy();
    expect(screen.getAllByText('CloudFront CDN / v1').length).toBeGreaterThan(0);
  });

  it('filters and sorts beacon rows', () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 2,
      beacons: [beaconTwo, beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 1,
      status: 'connected',
    });

    renderBeaconsPage();

    fireEvent.change(screen.getByLabelText('Search beacons'), { target: { value: 'websocket' } });

    expect(screen.getByTestId(`beacon-row-${beaconOne.id}`)).toBeTruthy();
    expect(screen.queryByTestId(`beacon-row-${beaconTwo.id}`)).toBeNull();

    fireEvent.change(screen.getByLabelText('Search beacons'), { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sort beacons by Host' }));
    fireEvent.click(screen.getByRole('button', { name: 'Sort beacons by Host' }));

    const roster = screen.getByTestId('beacon-roster');
    let rows = within(roster).getAllByRole('row').slice(1);
    expect(rows[0].textContent).toContain('beacon-bravo');
    expect(rows[1].textContent).toContain('beacon-alpha');

    fireEvent.click(screen.getByRole('button', { name: 'Reset beacon sorting' }));

    rows = within(roster).getAllByRole('row').slice(1);
    expect(rows[0].textContent).toContain('beacon-alpha');
    expect(rows[1].textContent).toContain('beacon-bravo');
    expect(screen.getByRole('button', { name: 'Toggle beacon sort direction' }).textContent).toContain('Desc');
    expect(screen.getByRole('button', { name: 'Sort beacons by Last Heartbeat' }).textContent).toContain('Descending');
  });

  it('filters beacon rows by URL-seeded and operator-selected status', () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 2,
      beacons: [beaconOne, beaconTwo],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 1,
      status: 'connected',
    });

    renderBeaconsPage(['/beacons?status=offline']);

    expect(screen.queryByTestId(`beacon-row-${beaconOne.id}`)).toBeNull();
    expect(screen.getByTestId(`beacon-row-${beaconTwo.id}`)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Online' }));
    expect(screen.getByTestId(`beacon-row-${beaconOne.id}`)).toBeTruthy();
    expect(screen.queryByTestId(`beacon-row-${beaconTwo.id}`)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'All' }));
    expect(screen.getByTestId(`beacon-row-${beaconOne.id}`)).toBeTruthy();
    expect(screen.getByTestId(`beacon-row-${beaconTwo.id}`)).toBeTruthy();
  });

  it('exports only the visible beacon rows as CSV', async () => {
    const createObjectURL = vi.fn((object: Blob | MediaSource) => {
      expect(object).toBeInstanceOf(Blob);
      return 'blob:xero-beacons';
    });
    const revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL }));
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 2,
      beacons: [beaconOne, beaconTwo],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 1,
      status: 'connected',
    });

    renderBeaconsPage();

    fireEvent.click(screen.getByRole('button', { name: 'Offline' }));
    fireEvent.click(screen.getByRole('button', { name: 'Export visible beacons' }));

    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:xero-beacons');
    const blob = createObjectURL.mock.calls[0]?.[0];
    expect(blob).toBeInstanceOf(Blob);
    const csv = await (blob as Blob).text();
    expect(csv).toContain('hostname,os,status,last_seen,transport');
    expect(csv).toContain('beacon-bravo,Ubuntu 24.04,offline');
    expect(csv).not.toContain('beacon-alpha');
  });

  it('navigates to the beacon workspace when a roster row is clicked', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage();

    fireEvent.click(screen.getByTestId(`beacon-row-${beaconOne.id}`));

    expect(await screen.findByTestId('task-execution-panel')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'beacon-alpha' })).toBeTruthy();
  });

  it('kills a beacon after confirmation and removes it from the active list', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 2,
      beacons: [beaconOne, beaconTwo],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 1,
      status: 'connected',
    });

    renderBeaconsPage([`/beacons/${beaconOne.id}/controls`]);

    fireEvent.click(screen.getByRole('button', { name: 'Kill beacon' }));

    let dialog = screen.getByRole('dialog', { name: 'Kill beacon confirmation' });
    expect(dialog.textContent).toContain('Remove beacon-alpha from active inventory');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(screen.getByRole('button', { name: 'Kill beacon' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Kill beacon' }));
    dialog = screen.getByRole('dialog', { name: 'Kill beacon confirmation' });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Kill beacon' }));

    await waitFor(() => {
      expect(apiMocks.killBeacon).toHaveBeenCalledWith('http://localhost:18001', 'c2-token', beaconOne.id);
    });
    await waitFor(() => {
      expect(screen.getByText('Beacon not found')).toBeTruthy();
    });
  });

  it('opens host operations from a beacon row click', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 2,
      beacons: [beaconTwo, beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 1,
      status: 'connected',
    });

    renderBeaconsPage();

    fireEvent.click(screen.getByTestId(`beacon-row-${beaconOne.id}`));

    expect(await screen.findByTestId('beacon-operation-detail')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Command queue/ })).toBeTruthy();
    expect(screen.getByTestId('beacon-operation-detail').textContent).toContain('Prepare a scoped command');

    fireEvent.click(screen.getByRole('link', { name: /Interactive session/ }));

    expect(screen.getByTestId('beacon-operation-detail').textContent).toContain('Attach to a live shell');
  });

  it('opens an interactive shell session and streams terminal data', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage([`/beacons/${beaconOne.id}/session`]);
    fireEvent.change(screen.getByLabelText('Interactive shell type'), { target: { value: 'powershell' } });
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));

    await waitFor(() => {
      expect(apiMocks.createShellSession).toHaveBeenCalledWith('http://localhost:18001', 'c2-token', {
        beacon_id: beaconOne.id,
        cols: 120,
        rows: 32,
        shell_type: 'powershell',
      });
    });

    expect(FakeWebSocket.instances[0].url).toBe(`ws://localhost:18001/ws/sessions/${shellSession.id}`);
    expect(FakeWebSocket.instances[0].protocols).toEqual(['xero.session.v1', 'bearer.c2-token']);

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'attached', session: shellSession }));
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'opened', session: { ...shellSession, status: 'open' } }));
    FakeWebSocket.instances[0].receive(JSON.stringify({ data: 'PS> whoami\r\nadmin\r\n', op: 'stdout' }));

    expect(await screen.findByText('open')).toBeTruthy();
    expect(screen.getByTestId('shell-session-transcript').textContent).toContain('admin');
    expect(terminalMocks.writes.join('')).toContain('PS> whoami');

    terminalMocks.terminals[0].emitData('whoami\r');
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({ data: 'whoami\r', op: 'stdin' });

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({ op: 'close' });
  });

  it('opens a file browser session, navigates folders, and previews text files', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage([`/beacons/${beaconOne.id}/files`]);
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));

    await waitFor(() => {
      expect(apiMocks.createFileBrowserSession).toHaveBeenCalledWith('http://localhost:18001', 'c2-token', {
        beacon_id: beaconOne.id,
      });
    });

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'attached', session: fileBrowserSession }));
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'opened', session: { ...fileBrowserSession, status: 'open' } }));

    await waitFor(() => {
      expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
        op: 'list_dir',
        path: '',
        refresh: false,
        request_id: 'file-1',
      });
    });

    FakeWebSocket.instances[0].receive(JSON.stringify({
      entries: [
        { modified_at: '2026-06-08T14:00:00Z', name: 'Documents', path: 'Documents', permissions: 'drwxr-xr-x', size: 0, type: 'directory' },
        { modified_at: '2026-06-08T14:01:00Z', name: 'readme.txt', path: 'readme.txt', permissions: '-rw-r--r--', size: 14, type: 'file' },
      ],
      ok: true,
      op: 'list_dir',
      path: '',
      request_id: 'file-1',
    }));

    expect(await screen.findByText('Documents')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Documents/ }));
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
      op: 'list_dir',
      path: 'Documents',
      refresh: false,
      request_id: 'file-2',
    });

    FakeWebSocket.instances[0].receive(JSON.stringify({
      entries: [
        { modified_at: '2026-06-08T14:02:00Z', name: 'notes.txt', path: 'Documents/notes.txt', permissions: '-rw-r--r--', size: 18, type: 'file' },
      ],
      ok: true,
      op: 'list_dir',
      path: 'Documents',
      request_id: 'file-2',
    }));

    expect(await screen.findByText('notes.txt')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'notes.txt' }));
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
      op: 'read_file',
      path: 'Documents/notes.txt',
      refresh: false,
      request_id: 'file-3',
    });

    FakeWebSocket.instances[0].receive(JSON.stringify({
      content: 'hello from preview',
      encoding: 'utf-8',
      ok: true,
      op: 'read_file',
      path: 'Documents/notes.txt',
      request_id: 'file-3',
      size: 18,
      truncated: false,
    }));

    expect((await screen.findByTestId('file-preview-output')).textContent).toContain('hello from preview');
  });

  it('uploads a file through staged transfer chunks and beacon ACKs', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });
    renderBeaconsPage([`/beacons/${beaconOne.id}/files`]);
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    await waitFor(() => {
      expect(apiMocks.createFileBrowserSession).toHaveBeenCalled();
    });
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'attached', session: fileBrowserSession }));
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'opened', session: { ...fileBrowserSession, status: 'open' } }));
    FakeWebSocket.instances[0].receive(JSON.stringify({
      entries: [],
      ok: true,
      op: 'list_dir',
      path: '',
      request_id: 'file-1',
    }));

    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).toBeTruthy();
    fireEvent.change(input!, { target: { files: [new File(['payload'], 'payload.bin')] } });

    await waitFor(() => {
      expect(apiMocks.createFileTransferUpload).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        expect.objectContaining({
          beacon_id: beaconOne.id,
          filename: 'payload.bin',
          remote_path: 'payload.bin',
          session_id: fileBrowserSession.id,
          size_bytes: 7,
        }),
      );
    });
    await waitFor(() => {
      expect(apiMocks.uploadFileTransferChunk).toHaveBeenCalledTimes(2);
    });
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual(expect.objectContaining({
      op: 'upload_start',
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));

    FakeWebSocket.instances[0].receive(JSON.stringify({
      next_sequence: 0,
      ok: true,
      op: 'upload_ready',
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual(expect.objectContaining({
      op: 'upload_chunk',
      sequence: 0,
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));

    FakeWebSocket.instances[0].receive(JSON.stringify({
      acked_chunks: 0,
      next_sequence: 0,
      ok: false,
      op: 'upload_nack',
      sequence: 0,
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));
    expect(FakeWebSocket.instances[0].sent
      .map((item) => JSON.parse(item))
      .filter((item) => item.op === 'upload_chunk' && item.sequence === 0)).toHaveLength(2);

    FakeWebSocket.instances[0].receive(JSON.stringify({
      message: 'Network interrupted',
      ok: false,
      op: 'transfer_error',
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));
    fireEvent.click(await screen.findByRole('button', { name: 'Retry upload transfer' }));
    expect(FakeWebSocket.instances[0].sent
      .map((item) => JSON.parse(item))
      .filter((item) => item.op === 'upload_start' && item.transfer_id === '99999999-9999-9999-9999-999999999999'))
      .toHaveLength(2);

    FakeWebSocket.instances[0].receive(JSON.stringify({
      acked_chunks: 1,
      next_sequence: 1,
      ok: true,
      op: 'upload_ack',
      total_chunks: 2,
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));
    FakeWebSocket.instances[0].receive(JSON.stringify({
      acked_chunks: 2,
      next_sequence: null,
      ok: true,
      op: 'upload_ack',
      total_chunks: 2,
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));

    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual(expect.objectContaining({
      op: 'upload_complete',
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));

    FakeWebSocket.instances[0].receive(JSON.stringify({
      ok: true,
      op: 'upload_complete',
      transfer_id: '99999999-9999-9999-9999-999999999999',
    }));
    await waitFor(() => {
      expect(screen.getByTestId('file-transfer-progress').textContent).toContain('100%');
    });
  });

  it('downloads a file through beacon chunks and saves the assembled artifact', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });
    const createObjectURL = vi.fn(() => 'blob:file-transfer');
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL });
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    renderBeaconsPage([`/beacons/${beaconOne.id}/files`]);
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));
    await waitFor(() => {
      expect(apiMocks.createFileBrowserSession).toHaveBeenCalled();
    });
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'attached', session: fileBrowserSession }));
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'opened', session: { ...fileBrowserSession, status: 'open' } }));
    FakeWebSocket.instances[0].receive(JSON.stringify({
      entries: [
        { modified_at: '2026-06-08T14:02:00Z', name: 'report.bin', path: 'report.bin', permissions: '-rw-r--r--', size: 8, type: 'file' },
      ],
      ok: true,
      op: 'list_dir',
      path: '',
      request_id: 'file-1',
    }));

    fireEvent.click(await screen.findByRole('button', { name: 'Download report.bin' }));
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual(expect.objectContaining({
      op: 'download_init',
      path: 'report.bin',
    }));

    FakeWebSocket.instances[0].receive(JSON.stringify({
      ok: true,
      op: 'download_ready',
      path: 'report.bin',
      total_chunks: 2,
      transfer_id: '88888888-8888-8888-8888-888888888888',
    }));
    FakeWebSocket.instances[0].receive(JSON.stringify({
      acked_chunks: 1,
      next_sequence: 1,
      ok: true,
      op: 'download_chunk',
      total_chunks: 2,
      transfer_id: '88888888-8888-8888-8888-888888888888',
    }));
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual(expect.objectContaining({
      op: 'download_chunk_request',
      sequence: 1,
      transfer_id: '88888888-8888-8888-8888-888888888888',
    }));

    FakeWebSocket.instances[0].receive(JSON.stringify({
      artifact_id: 'artifact-one',
      ok: true,
      op: 'download_complete',
      transfer_id: '88888888-8888-8888-8888-888888888888',
    }));

    await waitFor(() => {
      expect(apiMocks.downloadFileTransferArtifact).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        '88888888-8888-8888-8888-888888888888',
      );
    });
    expect(anchorClick).toHaveBeenCalled();
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:file-transfer');
    expect(screen.getByTestId('file-transfer-progress').textContent).toContain('Download complete');
  });

  it('opens a registry session and confirms value write and delete before applying them', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage([`/beacons/${beaconOne.id}/registry`]);
    fireEvent.click(screen.getByRole('button', { name: 'Open' }));

    await waitFor(() => {
      expect(apiMocks.createRegistrySession).toHaveBeenCalledWith('http://localhost:18001', 'c2-token', {
        beacon_id: beaconOne.id,
      });
    });

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'attached', session: registrySession }));
    FakeWebSocket.instances[0].receive(JSON.stringify({ op: 'opened', session: { ...registrySession, status: 'open' } }));

    await waitFor(() => {
      expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
        hive: 'HKLM',
        key_path: 'Software',
        op: 'reg_list_key',
        request_id: 'reg-1',
      });
    });

    FakeWebSocket.instances[0].receive(JSON.stringify({
      hive: 'HKLM',
      key_path: 'Software',
      ok: true,
      op: 'reg_list_key',
      request_id: 'reg-1',
      subkeys: ['Vendor'],
      values: [{ name: 'TestValue', type: 'REG_SZ', value: 'initial', writable: true }],
    }));

    expect(await screen.findByText('TestValue')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /TestValue/ }));

    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
      hive: 'HKLM',
      key_path: 'Software',
      op: 'reg_read_value',
      request_id: 'reg-2',
      value_name: 'TestValue',
    });

    FakeWebSocket.instances[0].receive(JSON.stringify({
      hive: 'HKLM',
      key_path: 'Software',
      ok: true,
      op: 'reg_read_value',
      request_id: 'reg-2',
      value: 'initial',
      value_name: 'TestValue',
      value_type: 'REG_SZ',
      writable: true,
    }));

    fireEvent.change(await screen.findByLabelText('Registry value data'), { target: { value: 'changed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('dialog', { name: 'Confirm registry operation' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
      hive: 'HKLM',
      key_path: 'Software',
      op: 'reg_prepare_write_value',
      request_id: 'reg-3',
      value: 'changed',
      value_name: 'TestValue',
      value_type: 'REG_SZ',
    });

    FakeWebSocket.instances[0].receive(JSON.stringify({
      confirm_token: 'confirm-one',
      hive: 'HKLM',
      key_path: 'Software',
      ok: true,
      op: 'reg_confirm_token',
      request_id: 'reg-3',
      value_name: 'TestValue',
      value_type: 'REG_SZ',
    }));

    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
      confirm_token: 'confirm-one',
      hive: 'HKLM',
      key_path: 'Software',
      op: 'reg_write_value',
      request_id: 'reg-4',
      value: 'changed',
      value_name: 'TestValue',
      value_type: 'REG_SZ',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(await screen.findByRole('dialog', { name: 'Confirm registry operation' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
      hive: 'HKLM',
      key_path: 'Software',
      op: 'reg_prepare_delete_value',
      request_id: 'reg-5',
      value_name: 'TestValue',
    });

    FakeWebSocket.instances[0].receive(JSON.stringify({
      action: 'delete_value',
      confirm_token: 'confirm-delete',
      hive: 'HKLM',
      key_path: 'Software',
      ok: true,
      op: 'reg_confirm_token',
      request_id: 'reg-5',
      value_name: 'TestValue',
    }));

    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toContainEqual({
      confirm_token: 'confirm-delete',
      hive: 'HKLM',
      key_path: 'Software',
      op: 'reg_delete_value',
      request_id: 'reg-6',
      value_name: 'TestValue',
    });
  });

  it('shows registry unavailable for non-Windows beacons', () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 2,
      beacons: [beaconTwo, beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 1,
      status: 'connected',
    });

    renderBeaconsPage([`/beacons/${beaconTwo.id}/registry`]);

    expect(screen.getByText('Registry unavailable.')).toBeTruthy();
    expect(screen.getByText('Windows registry sessions require a Windows beacon.')).toBeTruthy();
  });

  it('renders module args and queues a shell task from the task execution panel', async () => {
    apiMocks.getTasks.mockResolvedValueOnce({ items: [] }).mockResolvedValueOnce({ items: [queuedTask] });
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage();
    await openTaskingPanel();

    expect(await screen.findByText('No tasks queued for this beacon.')).toBeTruthy();
    expect(await screen.findByRole('option', { name: 'Shell Command' })).toBeTruthy();
    expect(screen.queryByRole('option', { name: 'Port Scan' })).toBeNull();
    expect((screen.getByRole('button', { name: /^Queue$/ }) as HTMLButtonElement).disabled).toBe(true);

    fireEvent.change(await screen.findByLabelText('Shell command'), { target: { value: 'whoami' } });
    fireEvent.change(screen.getByLabelText('Task priority'), { target: { value: 'urgent' } });
    fireEvent.click(screen.getByRole('button', { name: /Queue/ }));

    await waitFor(() => {
      expect(apiMocks.createTask).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        beaconOne.id,
        'shell',
        { command: 'whoami', shell_type: 'auto', timeout_seconds: 60 },
        'urgent',
      );
    });
    expect(await screen.findByText('whoami')).toBeTruthy();
    expect(screen.getByText('urgent')).toBeTruthy();
  });

  it('prefills task modules launched from Inventory', async () => {
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });
    const args = encodeLaunchArgs({ command: 'hostname', shell_type: 'powershell', timeout_seconds: 15 });

    renderBeaconsPage([`/beacons/${beaconOne.id}/commands?module=shell&args=${args}`]);

    expect(await screen.findByRole('option', { name: 'Shell Command' })).toBeTruthy();
    expect(((await screen.findByLabelText('Shell command')) as HTMLInputElement).value).toBe('hostname');
    expect((screen.getByLabelText('Shell type') as HTMLSelectElement).value).toBe('powershell');
    expect((screen.getByLabelText('Timeout seconds') as HTMLInputElement).value).toBe('15');
    expect(screen.getByTestId('beacon-task-target-chip').textContent).toContain('beacon-alpha');
  });

  it('keeps workspace tasking locked to the opened beacon', async () => {
    apiMocks.getTasks.mockResolvedValueOnce({ items: [] }).mockResolvedValueOnce({ items: [queuedTask] });
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 2,
      beacons: [beaconOne, beaconTwo],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 1,
      status: 'connected',
    });

    renderBeaconsPage([`/beacons/${beaconOne.id}/commands`]);
    await screen.findByTestId('task-execution-panel');

    expect(await screen.findByRole('option', { name: 'Shell Command' })).toBeTruthy();
    const dataTransfer = makeDataTransfer();
    dataTransfer.setData('application/x-xero-beacon-id', beaconTwo.id);
    fireEvent.drop(screen.getByTestId('beacon-task-drop-target'), { dataTransfer });

    expect(screen.getByTestId('beacon-task-target-chip').textContent).toContain('beacon-alpha');
    expect(await screen.findByText('This command queue is locked to the open beacon.')).toBeTruthy();
    fireEvent.change(await screen.findByLabelText('Shell command'), { target: { value: 'hostname' } });
    fireEvent.click(screen.getByRole('button', { name: /^Queue$/ }));

    await waitFor(() => {
      expect(apiMocks.createTask).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        beaconOne.id,
        'shell',
        { command: 'hostname', shell_type: 'auto', timeout_seconds: 60 },
        'normal',
      );
    });

    const invalidTransfer = makeDataTransfer();
    fireEvent.drop(screen.getByTestId('beacon-task-drop-target'), { dataTransfer: invalidTransfer });
    expect(await screen.findByText('This command queue is locked to the open beacon.')).toBeTruthy();
  });

  it('filters command history from the task execution panel', async () => {
    const completedTask = {
      ...queuedTask,
      args: { command: 'hostname', shell_type: 'auto', timeout_seconds: 60 },
      completed_at: '2026-06-08T14:09:00Z',
      id: '55555555-5555-5555-5555-555555555555',
      status: 'completed',
    };
    apiMocks.getTasks.mockResolvedValue({ items: [completedTask] });
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage();
    await openTaskingPanel();

    expect(await screen.findByTestId('task-row-55555555-5555-5555-5555-555555555555')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Search command history'), { target: { value: 'host' } });
    fireEvent.change(screen.getByLabelText('Filter task status'), { target: { value: 'completed' } });

    await waitFor(() => {
      expect(apiMocks.getTasks).toHaveBeenLastCalledWith('http://localhost:18001', 'c2-token', {
        beaconId: beaconOne.id,
        command: 'host',
        limit: 20,
        status: 'completed',
      });
    });
    expect(screen.getAllByText('completed').length).toBeGreaterThan(0);
    expect(screen.getByText('completed 1m ago')).toBeTruthy();
  });

  it('filters failed tasks and shows the failed result reason', async () => {
    const completedTask = {
      ...queuedTask,
      args: { command: 'hostname', shell_type: 'auto', timeout_seconds: 60 },
      completed_at: '2026-06-08T14:09:00Z',
      id: '55555555-5555-5555-5555-555555555555',
      status: 'completed',
    };
    const failedTask = {
      ...queuedTask,
      args: { command: 'bad-command', shell_type: 'auto', timeout_seconds: 60 },
      completed_at: '2026-06-08T14:09:30Z',
      id: '66666666-6666-6666-6666-666666666666',
      status: 'failed',
    };
    apiMocks.getTasks
      .mockResolvedValueOnce({ items: [completedTask, failedTask] })
      .mockResolvedValueOnce({ items: [failedTask] });
    apiMocks.getTaskResult.mockResolvedValue({
      artifacts: [],
      beacon_id: beaconOne.id,
      completed_at: '2026-06-08T14:09:30Z',
      created_at: '2026-06-08T14:08:00Z',
      error_message: 'Process exited with status 1.',
      exit_code: 1,
      expires_at: '2026-06-15T14:09:30Z',
      id: '88888888-8888-8888-8888-888888888888',
      metadata: {},
      output_sha256: 'failed-sha',
      output_size_bytes: 6,
      status: 'failed',
      stderr: 'denied',
      stderr_sha256: 'stderr-sha',
      stderr_size_bytes: 6,
      stdout: '',
      stdout_sha256: 'stdout-sha',
      stdout_size_bytes: 0,
      task_id: failedTask.id,
      timed_out: false,
      truncated: false,
      updated_at: '2026-06-08T14:09:30Z',
    });
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage();
    await openTaskingPanel();

    expect(await screen.findByTestId('task-row-66666666-6666-6666-6666-666666666666')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Filter task status'), { target: { value: 'failed' } });

    await waitFor(() => {
      expect(apiMocks.getTasks).toHaveBeenLastCalledWith('http://localhost:18001', 'c2-token', {
        beaconId: beaconOne.id,
        command: undefined,
        limit: 20,
        status: 'failed',
      });
    });
    expect(await screen.findByTestId('task-row-66666666-6666-6666-6666-666666666666')).toBeTruthy();
    expect(screen.queryByText('hostname')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'View result for bad-command' }));
    expect(await screen.findByTestId('task-failure-reason')).toBeTruthy();
    expect(screen.getByText('Process exited with status 1.')).toBeTruthy();
    expect(screen.getByText('denied')).toBeTruthy();
  });

  it('loads and downloads durable task results from command history', async () => {
    const completedTask = {
      ...queuedTask,
      args: { command: 'hostname', shell_type: 'auto', timeout_seconds: 60 },
      completed_at: '2026-06-08T14:09:00Z',
      id: '55555555-5555-5555-5555-555555555555',
      status: 'completed',
    };
    const createObjectURL = vi.fn(() => 'blob:task-result');
    const revokeObjectURL = vi.fn();
    const clickAnchor = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL });
    apiMocks.getTasks.mockResolvedValue({ items: [completedTask] });
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage();
    await openTaskingPanel();

    expect(await screen.findByTestId('task-row-55555555-5555-5555-5555-555555555555')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'View result for hostname' }));

    expect(await screen.findByTestId('task-result-panel')).toBeTruthy();
    await waitFor(() => {
      expect(apiMocks.getTaskResult).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        '55555555-5555-5555-5555-555555555555',
      );
    });
    expect(screen.getByText('output line')).toBeTruthy();
    expect(screen.getByText('Exit 0')).toBeTruthy();
    expect(screen.getAllByText('12 B').length).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getByRole('button', { name: 'Download combined result' }));

    await waitFor(() => {
      expect(apiMocks.downloadTaskResultText).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        '55555555-5555-5555-5555-555555555555',
        'combined',
      );
    });
    expect(createObjectURL).toHaveBeenCalled();
    expect(clickAnchor).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:task-result');
  });

  it('refreshes the selected durable result when a completion event arrives', async () => {
    const completedTask = {
      ...queuedTask,
      args: { command: 'hostname', shell_type: 'auto', timeout_seconds: 60 },
      completed_at: '2026-06-08T14:09:00Z',
      id: '55555555-5555-5555-5555-555555555555',
      status: 'completed',
    };
    let latestEvent: OperatorRealtimeEvent | null = null;
    const realtimeState = {
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      offlineBeaconCount: 0,
      status: 'connected',
    };
    apiMocks.getTasks.mockResolvedValue({ items: [completedTask] });
    apiMocks.getTaskResult
      .mockResolvedValueOnce({
        artifacts: [],
        beacon_id: beaconOne.id,
        completed_at: '2026-06-08T14:09:00Z',
        created_at: '2026-06-08T14:08:00Z',
        error_message: null,
        exit_code: 0,
        expires_at: '2026-06-15T14:09:00Z',
        id: '77777777-7777-7777-7777-777777777777',
        metadata: {},
        output_sha256: 'output-sha',
        output_size_bytes: 15,
        status: 'completed',
        stderr: '',
        stderr_sha256: 'stderr-sha',
        stderr_size_bytes: 0,
        stdout: 'initial output',
        stdout_sha256: 'stdout-sha',
        stdout_size_bytes: 15,
        task_id: completedTask.id,
        timed_out: false,
        truncated: false,
        updated_at: '2026-06-08T14:09:00Z',
      })
      .mockResolvedValueOnce({
        artifacts: [],
        beacon_id: beaconOne.id,
        completed_at: '2026-06-08T14:10:00Z',
        created_at: '2026-06-08T14:08:00Z',
        error_message: null,
        exit_code: 0,
        expires_at: '2026-06-15T14:10:00Z',
        id: '77777777-7777-7777-7777-777777777777',
        metadata: {},
        output_sha256: 'updated-sha',
        output_size_bytes: 14,
        status: 'completed',
        stderr: '',
        stderr_sha256: 'stderr-sha',
        stderr_size_bytes: 0,
        stdout: 'updated output',
        stdout_sha256: 'updated-sha',
        stdout_size_bytes: 14,
        task_id: completedTask.id,
        timed_out: false,
        truncated: false,
        updated_at: '2026-06-08T14:10:00Z',
      });
    mocks.useRealtime.mockImplementation(() => ({ ...realtimeState, latestEvent }));

    const rendered = renderBeaconsPage();
    await openTaskingPanel();

    expect(await screen.findByTestId('task-row-55555555-5555-5555-5555-555555555555')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'View result for hostname' }));
    expect(await screen.findByText('initial output')).toBeTruthy();

    latestEvent = {
      data: {},
      id: 'event-one',
      occurred_at: '2026-06-08T14:10:00Z',
      scope: { beacon_id: beaconOne.id, task_id: completedTask.id },
      source: { role: 'c2', service: 'xero-c2-core' },
      type: 'task.result.completed',
      version: 1,
    };
    rendered.rerender(beaconRoutesTree([`/beacons/${beaconOne.id}/commands`]));

    expect(await screen.findByText('updated output')).toBeTruthy();
    expect(apiMocks.getTaskResult.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('renders realtime task result chunks for the selected running task and clears the buffer', async () => {
    const runningTask = {
      ...queuedTask,
      dispatched_at: '2026-06-08T14:08:30Z',
      running_at: '2026-06-08T14:08:45Z',
      status: 'running',
    };
    let latestEvent: OperatorRealtimeEvent | null = null;
    const realtimeState = {
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      offlineBeaconCount: 0,
      status: 'connected',
    };
    apiMocks.getTasks.mockResolvedValue({ items: [runningTask] });
    mocks.useRealtime.mockImplementation(() => ({ ...realtimeState, latestEvent }));

    const rendered = renderBeaconsPage();
    await openTaskingPanel();

    const taskRow = await screen.findByTestId(`task-row-${runningTask.id}`);
    fireEvent.click(taskRow);
    expect(await screen.findByTestId('stream-output-panel')).toBeTruthy();

    latestEvent = {
      data: { task_result_chunk: taskResultChunk(runningTask.id, 'line one\n') },
      id: 'chunk-event-one',
      occurred_at: '2026-06-08T14:09:00Z',
      scope: { beacon_id: beaconOne.id, task_id: runningTask.id },
      source: { role: 'c2', service: 'xero-c2-core' },
      type: 'task.result.chunk',
      version: 1,
    };
    rendered.rerender(beaconRoutesTree([`/beacons/${beaconOne.id}/commands`]));

    expect(await screen.findByText('line one')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear stream buffer' }));
    expect(screen.getByTestId('stream-output-buffer').textContent).toContain('(waiting for streamed output)');
  });

  it('cancels a queued task from the task execution panel', async () => {
    apiMocks.getTasks.mockResolvedValueOnce({ items: [queuedTask] }).mockResolvedValueOnce({
      items: [{ ...queuedTask, cancelled_at: '2026-06-08T14:09:00Z', status: 'cancelled' }],
    });
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [beaconOne],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });

    renderBeaconsPage();
    await openTaskingPanel();

    expect(await screen.findByText('whoami')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Cancel task whoami/ }));

    await waitFor(() => {
      expect(apiMocks.cancelTask).toHaveBeenCalledWith('http://localhost:18001', 'c2-token', queuedTask.id);
    });
    expect((await screen.findAllByText('cancelled')).length).toBeGreaterThan(0);
  });
});
