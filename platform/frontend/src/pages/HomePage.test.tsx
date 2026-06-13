import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { HomePage } from './HomePage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
  useRealtime: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  getDashboardSummary: vi.fn(),
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: mocks.useC2Connection,
}));

vi.mock('../useAuth', () => ({
  useAuth: mocks.useAuth,
}));

vi.mock('../useRealtime', () => ({
  useRealtime: mocks.useRealtime,
}));

vi.mock('../api', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  getDashboardSummary: apiMocks.getDashboardSummary,
}));

const now = '2026-06-13T06:00:00.000Z';

function dashboardSummary(overrides = {}) {
  return {
    beacons: { offline: 1, online: 2, total: 3 },
    c2_health: {
      checks: {
        artifact_store: { status: 'healthy' },
        postgres: { status: 'healthy' },
        redis: { status: 'healthy' },
      },
      status: 'ready',
    },
    generated_at: now,
    recent_activity: [
      {
        beacon_id: 'beacon-one',
        detail: 'heartbeat',
        id: 'beacon-event-one',
        label: 'host-one reported online',
        occurred_at: now,
        status: 'online',
        task_id: null,
        type: 'beacon.status',
      },
    ],
    recent_tasks: [
      {
        args: { command: 'whoami' },
        beacon_id: 'beacon-one',
        cancelled_at: null,
        completed_at: now,
        created_at: now,
        dispatched_at: null,
        id: 'task-one',
        module: 'shell',
        priority: 'normal',
        queued_at: now,
        running_at: null,
        status: 'completed',
        updated_at: now,
      },
    ],
    ...overrides,
  };
}

function realtime(overrides = {}) {
  return {
    activeBeaconCount: 0,
    beaconCount: 0,
    beacons: [],
    error: '',
    latestEvent: null,
    offlineBeaconCount: 0,
    status: 'connected',
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
}

describe('HomePage', () => {
  beforeEach(() => {
    apiMocks.getDashboardSummary.mockResolvedValue(dashboardSummary());
    mocks.useAuth.mockReturnValue({
      logout: vi.fn(),
      session: {
        accessToken: 'local-token',
        expiresAt: '2099-01-01T00:00:00Z',
        operator: { created_at: now, id: 'operator-1', is_enabled: true, role: 'admin', username: 'admin' },
        tokenType: 'bearer',
      },
    });
    mocks.useC2Connection.mockReturnValue({
      connection: {
        accessToken: 'c2-token',
        baseUrl: 'http://localhost:18001',
        connectedAt: now,
        expiresAt: '2099-01-01T00:00:00Z',
        service: 'xero-c2-core',
        serviceRole: 'c2',
        status: 'connected',
        tokenType: 'bearer',
      },
    });
    mocks.useRealtime.mockReturnValue(realtime());
  });

  it('renders dashboard counts, recent task, and activity from the summary API', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-total-beacons').textContent).toBe('3');
    });
    expect(screen.getByTestId('dashboard-online-beacons').textContent).toBe('2');
    expect(screen.getByTestId('dashboard-offline-beacons').textContent).toBe('1');
    expect(screen.getByText('whoami')).toBeTruthy();
    expect(screen.getByText('host-one reported online')).toBeTruthy();
    expect(apiMocks.getDashboardSummary).toHaveBeenCalledWith('http://localhost:18001', 'c2-token');
  });

  it('shows loading skeletons during initial dashboard fetch', () => {
    apiMocks.getDashboardSummary.mockReturnValue(new Promise(() => undefined));

    renderPage();

    expect(screen.getAllByTestId('dashboard-loading-skeleton').length).toBeGreaterThan(0);
  });

  it('renders empty state guidance when no beacons are registered', async () => {
    apiMocks.getDashboardSummary.mockResolvedValue(dashboardSummary({
      beacons: { offline: 0, online: 0, total: 0 },
      recent_activity: [],
      recent_tasks: [],
    }));

    renderPage();

    await waitFor(() => {
      expect(screen.getByText('No beacons registered')).toBeTruthy();
    });
    expect(screen.getByText('No recent tasks')).toBeTruthy();
  });

  it('updates cards and feed from realtime events without a page refresh', async () => {
    const { rerender } = renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-total-beacons').textContent).toBe('3');
    });

    mocks.useRealtime.mockReturnValue(realtime({
      activeBeaconCount: 3,
      beaconCount: 4,
      latestEvent: {
        data: {
          beacon: {
            hostname: 'new-host',
            id: 'beacon-new',
            status: 'online',
          },
        },
        id: 'event-new',
        occurred_at: now,
        scope: { beacon_id: 'beacon-new', project_id: null, scan_job_id: null, session_id: null, task_id: null },
        source: { role: 'c2', service: 'xero-c2' },
        type: 'beacon.registered',
        version: 1,
      },
      offlineBeaconCount: 1,
    }));

    rerender(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-total-beacons').textContent).toBe('4');
    });
    expect(screen.getByTestId('dashboard-online-beacons').textContent).toBe('3');
    expect(screen.getByText('new-host online')).toBeTruthy();
  });

  it('updates counts when a beacon heartbeat restores an offline beacon', async () => {
    const { rerender } = renderPage();
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-offline-beacons').textContent).toBe('1');
    });

    mocks.useRealtime.mockReturnValue(realtime({
      latestEvent: {
        data: {
          beacon: {
            hostname: 'restored-host',
            id: 'beacon-restored',
            status: 'online',
          },
        },
        id: 'event-restored',
        occurred_at: now,
        scope: { beacon_id: 'beacon-restored', project_id: null, scan_job_id: null, session_id: null, task_id: null },
        source: { role: 'c2', service: 'xero-c2' },
        type: 'beacon.status.changed',
        version: 1,
      },
    }));

    rerender(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-total-beacons').textContent).toBe('3');
    });
    expect(screen.getByTestId('dashboard-online-beacons').textContent).toBe('3');
    expect(screen.getByTestId('dashboard-offline-beacons').textContent).toBe('0');
    expect(screen.getByText('restored-host online')).toBeTruthy();
  });

  it('keeps the overview focused by omitting health and quick-action panels', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-total-beacons').textContent).toBe('3');
    });
    expect(screen.queryByRole('region', { name: 'System health' })).toBeNull();
    expect(screen.queryByRole('region', { name: 'Quick actions' })).toBeNull();
  });
});
