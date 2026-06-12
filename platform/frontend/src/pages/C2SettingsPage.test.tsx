import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { InfrastructureWorker } from '../api';
import { C2SettingsPage } from './C2SettingsPage';

const apiMocks = vi.hoisted(() => ({
  createWorkerPairingToken: vi.fn(),
  getInfrastructureWorkers: vi.fn(),
  getProtocolInfo: vi.fn(),
  getProtocolSecurityEvents: vi.fn(),
  getTransportStatus: vi.fn(),
  launchInfrastructureWorker: vi.fn(),
  stopInfrastructureWorker: vi.fn(),
}));

const hookMocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
  useRealtime: vi.fn(),
}));

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return {
    ...actual,
    createWorkerPairingToken: apiMocks.createWorkerPairingToken,
    getInfrastructureWorkers: apiMocks.getInfrastructureWorkers,
    getProtocolInfo: apiMocks.getProtocolInfo,
    getProtocolSecurityEvents: apiMocks.getProtocolSecurityEvents,
    getTransportStatus: apiMocks.getTransportStatus,
    launchInfrastructureWorker: apiMocks.launchInfrastructureWorker,
    stopInfrastructureWorker: apiMocks.stopInfrastructureWorker,
  };
});

vi.mock('../useAuth', () => ({
  useAuth: hookMocks.useAuth,
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: hookMocks.useC2Connection,
}));

vi.mock('../useRealtime', () => ({
  useRealtime: hookMocks.useRealtime,
}));

const embeddedHandler: InfrastructureWorker = {
  capabilities: ['embedded-handler', 'direct-beacon-registration'],
  capacity: 1,
  created_at: '2026-06-09T13:00:00Z',
  current_load: 0,
  endpoint: 'http://localhost:8001',
  id: '11111111-1111-1111-1111-111111111111',
  kind: 'beacon-handler',
  last_error: null,
  last_seen: '2026-06-09T13:05:00Z',
  managed_host_port: null,
  managed_project: null,
  managed_service: null,
  name: 'Embedded C2 beacon handler',
  origin: 'embedded',
  status: 'online',
  updated_at: '2026-06-09T13:05:00Z',
  version: 'embedded',
};

const embeddedScanner: InfrastructureWorker = {
  ...embeddedHandler,
  capabilities: ['embedded-scanner', 'recon-ready'],
  id: '22222222-2222-2222-2222-222222222222',
  kind: 'scanner',
  name: 'Embedded C2 scanner',
};

const externalScanner: InfrastructureWorker = {
  ...embeddedScanner,
  capabilities: ['tcp-connect', 'service-enumeration'],
  capacity: 10,
  current_load: 2,
  endpoint: 'http://scanner.local:8000',
  id: '33333333-3333-3333-3333-333333333333',
  last_seen: '2026-06-09T13:06:00Z',
  managed_host_port: null,
  name: 'external scanner one',
  origin: 'external',
  version: 'test',
};

function renderC2SettingsPage() {
  return render(
    <MemoryRouter>
      <C2SettingsPage />
    </MemoryRouter>,
  );
}

describe('C2SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.getInfrastructureWorkers.mockResolvedValue({ items: [embeddedHandler, embeddedScanner, externalScanner] });
    apiMocks.getProtocolInfo.mockResolvedValue({
      c2_public_key_b64: 'public-key',
      current_version: 1,
      encryption: 'AES-256-GCM',
      frame_harness_enabled: true,
      frame_header_length: 72,
      integrity: 'HMAC-SHA256',
      key_exchange: 'X25519-HKDF-SHA256',
      max_frame_bytes: 1048576,
      supported_versions: [1],
    });
    apiMocks.getProtocolSecurityEvents.mockResolvedValue({
      items: [
        {
          beacon_id: null,
          event_type: 'protocol.hmac_mismatch',
          id: 'event-one',
          message: 'Frame HMAC verification failed',
          nonce: '0102030405060708090a0b0c',
          occurred_at: '2026-06-09T13:07:00Z',
          session_id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
          severity: 'high',
        },
      ],
    });
    apiMocks.getTransportStatus.mockResolvedValue({
      active_longpoll_requests: 1,
      active_websocket_connections: 1,
      longpoll_max_frame_bytes: 1048576,
      longpoll_timeout_seconds: 60,
      transport_mode_counts: { 'long-poll': 2, rest: 3, websocket: 1 },
      websocket_heartbeat_timeout_seconds: 90,
      websocket_max_message_bytes: 1048576,
      websocket_ping_interval_seconds: 30,
      websocket_ping_timeout_seconds: 30,
      websocket_registration_timeout_seconds: 5,
      websocket_send_queue_size: 32,
    });
    apiMocks.createWorkerPairingToken.mockResolvedValue({
      command: 'C2_BASE_URL=http://localhost:8001 WORKER_PAIRING_TOKEN=pair-token docker compose -f docker-compose.scanner.yml up -d --build scanner',
      expires_at: '2026-06-09T14:00:00Z',
      id: 'pairing-one',
      kind: 'scanner',
      name: 'external scanner',
      pairing_token: 'pair-token',
    });
    apiMocks.launchInfrastructureWorker.mockResolvedValue({ worker: externalScanner });
    apiMocks.stopInfrastructureWorker.mockResolvedValue({ status: 'offline', worker: { ...externalScanner, status: 'offline' } });
    hookMocks.useAuth.mockReturnValue({
      logout: vi.fn(),
      session: {
        accessToken: 'local-token',
        expiresAt: '2099-01-01T00:00:00Z',
        operator: { created_at: '2026-06-09T00:00:00Z', id: 'operator-1', is_enabled: true, role: 'admin', username: 'admin' },
        tokenType: 'bearer',
      },
    });
    hookMocks.useC2Connection.mockReturnValue({
      checkConnection: vi.fn(),
      connection: {
        accessToken: 'c2-token',
        baseUrl: 'http://localhost:8001',
        connectedAt: '2026-06-09T00:00:00Z',
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
    hookMocks.useRealtime.mockReturnValue({
      activeBeaconCount: 0,
      beaconCount: 0,
      beacons: [],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });
  });

  it('shows the C2 required panel while disconnected', () => {
    hookMocks.useC2Connection.mockReturnValue({
      checkConnection: vi.fn(),
      connection: null,
      disconnect: vi.fn(),
      error: '',
      isChecking: false,
    });

    renderC2SettingsPage();

    expect(screen.getByRole('heading', { name: 'Xero C2 backend required' })).toBeTruthy();
    expect(apiMocks.getInfrastructureWorkers).not.toHaveBeenCalled();
    expect(apiMocks.getProtocolInfo).not.toHaveBeenCalled();
    expect(apiMocks.getTransportStatus).not.toHaveBeenCalled();
  });

  it('loads protocol status, transport status, security events, and worker inventory', async () => {
    renderC2SettingsPage();

    await waitFor(() => expect(apiMocks.getInfrastructureWorkers).toHaveBeenCalledWith('http://localhost:8001', 'c2-token'));
    await waitFor(() => expect(apiMocks.getProtocolInfo).toHaveBeenCalledWith('http://localhost:8001', 'c2-token'));
    expect(apiMocks.getProtocolSecurityEvents).toHaveBeenCalledWith('http://localhost:8001', 'c2-token');
    expect(apiMocks.getTransportStatus).toHaveBeenCalledWith('http://localhost:8001', 'c2-token');

    const handlers = screen.getByRole('region', { name: 'Beacon handlers' });
    const scanners = screen.getByRole('region', { name: 'Scanners' });
    const protocol = screen.getByTestId('protocol-status-panel');
    const transport = screen.getByTestId('transport-status-panel');
    const events = screen.getByTestId('protocol-security-events');
    expect(within(protocol).getAllByText('v1')).toHaveLength(2);
    expect(within(protocol).getByText('X25519-HKDF-SHA256')).toBeTruthy();
    expect(within(transport).getByText('Active WebSockets')).toBeTruthy();
    expect(within(transport).getByTestId('transport-active-websockets').textContent).toBe('1');
    expect(within(transport).getByText('Active long-polls')).toBeTruthy();
    expect(within(transport).getByTestId('transport-active-longpolls').textContent).toBe('1');
    expect(within(transport).getByText('WS 1 / LP 2 / REST 3')).toBeTruthy();
    expect(within(transport).getByText('Long-poll timeout')).toBeTruthy();
    expect(within(transport).getAllByText('1 MB')).toHaveLength(2);
    expect(within(events).getByText('protocol.hmac_mismatch')).toBeTruthy();
    expect(within(events).getByText('Frame HMAC verification failed')).toBeTruthy();
    expect(within(handlers).getByText('Embedded C2 beacon handler')).toBeTruthy();
    expect(within(scanners).getByText('Embedded C2 scanner')).toBeTruthy();
    expect(within(scanners).getByText('external scanner one')).toBeTruthy();
    expect(screen.getByText('Total workers').parentElement?.textContent).toContain('3');
  });

  it('renders transport status errors without hiding protocol state', async () => {
    apiMocks.getTransportStatus.mockRejectedValue(new Error('transport unavailable'));

    renderC2SettingsPage();

    await screen.findByText('transport unavailable');
    expect(screen.getByTestId('transport-active-websockets').textContent).toBe('-');
    expect(screen.getByTestId('transport-active-longpolls').textContent).toBe('-');
    expect(screen.getByTestId('protocol-status-panel').textContent).toContain('X25519-HKDF-SHA256');
  });

  it('creates a one-time pairing token for an external worker', async () => {
    renderC2SettingsPage();

    await screen.findByText('external scanner one');
    const scannerPanel = screen.getByRole('region', { name: 'Scanners' });
    fireEvent.click(within(scannerPanel).getByRole('button', { name: 'Add external' }));
    fireEvent.change(screen.getByLabelText('Worker name'), { target: { value: 'edge scanner' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create token' }));

    await waitFor(() =>
      expect(apiMocks.createWorkerPairingToken).toHaveBeenCalledWith('http://localhost:8001', 'c2-token', 'scanner', 'edge scanner'),
    );
    expect(screen.getByTestId('pairing-result').textContent).toContain('pair-token');
    expect(screen.getByTestId('pairing-result').textContent).toContain('docker-compose.scanner.yml');
  });

  it('launches and stops managed C2 workers', async () => {
    const managedHandler: InfrastructureWorker = {
      ...embeddedHandler,
      id: '44444444-4444-4444-4444-444444444444',
      managed_host_port: 8002,
      managed_project: 'xero-managed-handler-test',
      managed_service: 'beacon-handler',
      name: 'managed handler',
      origin: 'c2-managed',
      status: 'online',
    };
    apiMocks.getInfrastructureWorkers
      .mockResolvedValueOnce({ items: [embeddedHandler, embeddedScanner] })
      .mockResolvedValueOnce({ items: [embeddedHandler, embeddedScanner, managedHandler] })
      .mockResolvedValueOnce({ items: [embeddedHandler, embeddedScanner, { ...managedHandler, status: 'offline' }] });
    apiMocks.launchInfrastructureWorker.mockResolvedValue({ worker: managedHandler });
    apiMocks.stopInfrastructureWorker.mockResolvedValue({ status: 'offline', worker: { ...managedHandler, status: 'offline' } });

    renderC2SettingsPage();

    await screen.findByText('Embedded C2 beacon handler');
    const handlerPanel = screen.getByRole('region', { name: 'Beacon handlers' });
    fireEvent.click(within(handlerPanel).getByRole('button', { name: 'Launch on C2 host' }));
    fireEvent.change(screen.getByLabelText('Worker name'), { target: { value: 'managed handler' } });
    fireEvent.change(screen.getByLabelText('Host port'), { target: { value: '18002' } });
    fireEvent.click(screen.getByRole('button', { name: 'Launch worker' }));

    await waitFor(() =>
      expect(apiMocks.launchInfrastructureWorker).toHaveBeenCalledWith(
        'http://localhost:8001',
        'c2-token',
        'beacon-handler',
        'managed handler',
        18002,
      ),
    );

    await screen.findByText('managed handler');
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }));

    await waitFor(() =>
      expect(apiMocks.stopInfrastructureWorker).toHaveBeenCalledWith(
        'http://localhost:8001',
        'c2-token',
        '44444444-4444-4444-4444-444444444444',
      ),
    );
  });
});
