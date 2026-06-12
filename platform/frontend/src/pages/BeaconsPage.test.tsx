import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Beacon } from '../api';
import { BeaconsPage } from './BeaconsPage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
  useRealtime: vi.fn(),
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
  });

  afterEach(() => {
    vi.restoreAllMocks();
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
});
