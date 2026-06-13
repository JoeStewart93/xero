import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Beacon } from '../api';
import type { OperatorRealtimeEvent } from '../operatorRealtime';
import { BeaconsPage } from './BeaconsPage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
  useRealtime: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  cancelTask: vi.fn(),
  closeFileBrowserSession: vi.fn(),
  closeShellSession: vi.fn(),
  createFileBrowserSession: vi.fn(),
  createShellSession: vi.fn(),
  createShellTask: vi.fn(),
  downloadTaskResultText: vi.fn(),
  getTaskResult: vi.fn(),
  getTasks: vi.fn(),
}));

const terminalMocks = vi.hoisted(() => ({
  terminals: [] as Array<{ emitData: (data: string) => void }>,
  writes: [] as string[],
}));

vi.mock('../api', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  cancelTask: apiMocks.cancelTask,
  closeFileBrowserSession: apiMocks.closeFileBrowserSession,
  closeShellSession: apiMocks.closeShellSession,
  createFileBrowserSession: apiMocks.createFileBrowserSession,
  createShellSession: apiMocks.createShellSession,
  createShellTask: apiMocks.createShellTask,
  downloadTaskResultText: apiMocks.downloadTaskResultText,
  getTaskResult: apiMocks.getTaskResult,
  getTasks: apiMocks.getTasks,
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

function renderBeaconsPage() {
  return render(
    <MemoryRouter>
      <BeaconsPage />
    </MemoryRouter>,
  );
}

describe('BeaconsPage', () => {
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-06-08T14:10:00Z').getTime());
    FakeWebSocket.instances = [];
    terminalMocks.terminals = [];
    terminalMocks.writes = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
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
    apiMocks.createFileBrowserSession.mockResolvedValue(fileBrowserSession);
    apiMocks.closeFileBrowserSession.mockResolvedValue({ ...fileBrowserSession, close_reason: 'operator', closed_at: '2026-06-08T14:13:00Z', status: 'closed' });
    apiMocks.createShellSession.mockResolvedValue(shellSession);
    apiMocks.closeShellSession.mockResolvedValue({ ...shellSession, close_reason: 'operator', closed_at: '2026-06-08T14:11:00Z', status: 'closed' });
    apiMocks.createShellTask.mockResolvedValue(queuedTask);
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
    apiMocks.downloadTaskResultText.mockResolvedValue(new Blob(['output line\n'], { type: 'text/plain' }));
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

    expect(screen.getByRole('heading', { name: 'Beacon overview' })).toBeTruthy();
    expect(screen.getByTestId('beacons-empty-state').textContent).toContain('No beacons registered.');
  });

  it('renders beacon roster and selected metadata detail', () => {
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
    expect(within(roster).getByText('10.40.0.8')).toBeTruthy();
    expect(within(roster).getByText('WebSocket')).toBeTruthy();
    expect(within(roster).getByText('Long-poll')).toBeTruthy();
    expect(within(roster).getByText('Connected')).toBeTruthy();
    expect(screen.getByTestId('beacons-online-count').textContent).toBe('1');
    expect(screen.getByTestId('beacons-offline-count').textContent).toBe('2');
    expect(screen.getByTestId(`beacon-relative-${beaconOne.id}`).textContent).toBe('5m ago');
    expect(screen.getByTestId('beacon-detail-hostname').textContent).toBe('beacon-alpha');
    expect(screen.getByTestId('beacon-detail-os').textContent).toBe('Windows 11');
    expect(screen.getByText('Protocol version').parentElement?.textContent).toContain('v1');
    expect(screen.getByTestId('beacon-detail-transport-mode').textContent).toBe('WebSocket');
    expect(screen.getByTestId('beacon-detail-transport-state').textContent).toBe('Connected');

    fireEvent.click(screen.getByTestId(`beacon-row-${beaconTwo.id}`));

    expect(screen.getByTestId('beacon-detail-hostname').textContent).toBe('beacon-bravo');
    expect(screen.getByTestId('beacon-detail-os').textContent).toBe('Ubuntu 24.04');
    expect(screen.getByTestId('beacon-detail-transport-mode').textContent).toBe('REST');
    expect(screen.getByTestId('beacon-detail-transport-state').textContent).toBe('Disconnected');

    fireEvent.click(screen.getByTestId(`beacon-row-${beaconThree.id}`));

    expect(screen.getByTestId('beacon-detail-hostname').textContent).toBe('beacon-charlie');
    expect(screen.getByTestId('beacon-detail-transport-mode').textContent).toBe('Long-poll');
    expect(screen.getByTestId('beacon-detail-transport-state').textContent).toBe('Disconnected');
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

  it('opens host operations from a beacon row double-click', () => {
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

    fireEvent.doubleClick(screen.getByTestId(`beacon-row-${beaconOne.id}`));

    expect(screen.getByRole('dialog', { name: 'Host operations for beacon-alpha' })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Command queue/ })).toBeTruthy();
    expect(screen.getByTestId('beacon-operation-detail').textContent).toContain('Prepare a scoped command');

    fireEvent.click(screen.getByRole('button', { name: /Credentials/ }));

    expect(screen.getByTestId('beacon-operation-detail').textContent).toContain('Review credential material');

    fireEvent.click(screen.getByRole('button', { name: 'Close host operations' }));

    expect(screen.queryByRole('dialog', { name: 'Host operations for beacon-alpha' })).toBeNull();
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

    renderBeaconsPage();

    fireEvent.doubleClick(screen.getByTestId(`beacon-row-${beaconOne.id}`));
    fireEvent.click(screen.getByRole('button', { name: /Interactive session/ }));
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

    renderBeaconsPage();

    fireEvent.doubleClick(screen.getByTestId(`beacon-row-${beaconOne.id}`));
    fireEvent.click(screen.getByRole('button', { name: /Files/ }));
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
    fireEvent.click(screen.getByRole('button', { name: /notes.txt/ }));
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

  it('queues a shell task from the command queue modal', async () => {
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

    fireEvent.doubleClick(screen.getByTestId(`beacon-row-${beaconOne.id}`));
    expect(await screen.findByText('No tasks queued for this beacon.')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Shell command'), { target: { value: 'whoami' } });
    fireEvent.change(screen.getByLabelText('Task priority'), { target: { value: 'urgent' } });
    fireEvent.click(screen.getByRole('button', { name: /Queue/ }));

    await waitFor(() => {
      expect(apiMocks.createShellTask).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        beaconOne.id,
        { command: 'whoami', shell_type: 'auto', timeout_seconds: 60 },
        'urgent',
      );
    });
    expect(await screen.findByText('whoami')).toBeTruthy();
    expect(screen.getByText('urgent')).toBeTruthy();
  });

  it('filters command history from the command queue modal', async () => {
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

    fireEvent.doubleClick(screen.getByTestId(`beacon-row-${beaconOne.id}`));
    expect(await screen.findByText('hostname')).toBeTruthy();

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

    fireEvent.doubleClick(screen.getByTestId(`beacon-row-${beaconOne.id}`));
    expect(await screen.findByText('hostname')).toBeTruthy();
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

    fireEvent.doubleClick(screen.getByTestId(`beacon-row-${beaconOne.id}`));
    expect(await screen.findByText('hostname')).toBeTruthy();
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
    rendered.rerender(
      <MemoryRouter>
        <BeaconsPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText('updated output')).toBeTruthy();
    expect(apiMocks.getTaskResult.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('cancels a queued task from the command queue modal', async () => {
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

    fireEvent.doubleClick(screen.getByTestId(`beacon-row-${beaconOne.id}`));
    expect(await screen.findByText('whoami')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Cancel task whoami/ }));

    await waitFor(() => {
      expect(apiMocks.cancelTask).toHaveBeenCalledWith('http://localhost:18001', 'c2-token', queuedTask.id);
    });
    expect((await screen.findAllByText('cancelled')).length).toBeGreaterThan(0);
  });
});
