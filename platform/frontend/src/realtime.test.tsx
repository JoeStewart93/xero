import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from './api';
import type { Beacon, BeaconListResponse } from './api';
import { AuthProvider } from './auth';
import { writeStoredAuthSession } from './authStorage';
import { C2ConnectionProvider } from './c2Connection';
import { writeStoredC2Connection } from './c2ConnectionStorage';
import { RealtimeProvider } from './realtime';
import { useRealtime } from './useRealtime';

vi.mock('./api', async () => {
  const actual = await vi.importActual<typeof import('./api')>('./api');
  return {
    ...actual,
    getC2Beacons: vi.fn(),
  };
});

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  protocols: string | string[];
  readyState = FakeWebSocket.CONNECTING;
  url: string;

  constructor(url: string, protocols: string | string[]) {
    this.url = url;
    this.protocols = protocols;
    FakeWebSocket.instances.push(this);
  }

  close(code = 1000) {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code } as CloseEvent);
  }

  open() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }
}

const baseBeacon: Beacon = {
  architecture: 'x64',
  external_ip: '198.51.100.11',
  first_seen: '2026-06-08T00:00:00Z',
  hostname: 'realtime-one',
  id: 'beacon-one',
  internal_ip: '10.10.0.11',
  last_seen: '2026-06-08T00:00:00Z',
  machine_fingerprint_hash: 'fingerprint-one',
  os: 'Windows 11',
  pid: 4411,
  protocol_version: null,
  status: 'online',
  transport_connected: false,
  transport_last_seen: null,
  transport_mode: 'rest',
};

function seedAuthenticatedC2Session() {
  writeStoredAuthSession({
    accessToken: 'local-token',
    expiresAt: '2099-01-01T00:00:00Z',
    operator: {
      created_at: '2026-06-08T00:00:00Z',
      id: 'operator-1',
      is_enabled: true,
      role: 'admin',
      username: 'admin',
    },
    tokenType: 'bearer',
  });
  writeStoredC2Connection({
    accessToken: 'c2-token',
    baseUrl: 'http://localhost:8001',
    connectedAt: '2026-06-08T00:00:00Z',
    expiresAt: '2099-01-01T00:00:00Z',
    service: 'xero-c2-core',
    serviceRole: 'c2',
    status: 'connected',
    tokenType: 'bearer',
  });
}

function RealtimeProbe() {
  const realtime = useRealtime();
  return (
    <div>
      <span data-testid="status">{realtime.status}</span>
      <span data-testid="count">{realtime.beaconCount}</span>
      <span data-testid="active-count">{realtime.activeBeaconCount}</span>
      <span data-testid="offline-count">{realtime.offlineBeaconCount}</span>
      <span data-testid="first-host">{realtime.beacons[0]?.hostname ?? '-'}</span>
      <span data-testid="hosts">{realtime.beacons.map((beacon) => beacon.hostname).join(',')}</span>
    </div>
  );
}

function renderRealtimeProbe() {
  return render(
    <C2ConnectionProvider>
      <AuthProvider>
        <RealtimeProvider>
          <RealtimeProbe />
        </RealtimeProvider>
      </AuthProvider>
    </C2ConnectionProvider>,
  );
}

describe('RealtimeProvider', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeWebSocket);
    seedAuthenticatedC2Session();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('reconciles missed beacon state from REST after websocket reconnect', async () => {
    const getC2Beacons = vi.mocked(api.getC2Beacons);
    getC2Beacons
      .mockResolvedValueOnce({ items: [baseBeacon] })
      .mockResolvedValueOnce({
        items: [
          {
            ...baseBeacon,
            hostname: 'realtime-two',
            id: 'beacon-two',
            machine_fingerprint_hash: 'fingerprint-two',
            status: 'offline',
          },
          baseBeacon,
        ],
      });

    renderRealtimeProbe();

    act(() => {
      FakeWebSocket.instances[0].open();
    });

    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('1'));
    expect(screen.getByTestId('first-host').textContent).toBe('realtime-one');

    act(() => {
      FakeWebSocket.instances[0].close(1006);
    });

    await waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2));

    act(() => {
      FakeWebSocket.instances[1].open();
    });

    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('2'));
    expect(screen.getByTestId('active-count').textContent).toBe('1');
    expect(screen.getByTestId('offline-count').textContent).toBe('1');
    expect(screen.getByTestId('hosts').textContent).toContain('realtime-two');
    expect(getC2Beacons).toHaveBeenCalledTimes(2);
    expect(getC2Beacons).toHaveBeenLastCalledWith('http://localhost:8001', 'c2-token');
  });

  it('keeps realtime beacon events when an older REST reconcile resolves later', async () => {
    const getC2Beacons = vi.mocked(api.getC2Beacons);
    let resolveReconcile: ((value: BeaconListResponse | PromiseLike<BeaconListResponse>) => void) | undefined;
    getC2Beacons.mockReturnValueOnce(
      new Promise<BeaconListResponse>((resolve) => {
        resolveReconcile = resolve;
      }),
    );
    const eventBeacon = {
      ...baseBeacon,
      hostname: 'event-first',
      id: 'beacon-event',
      machine_fingerprint_hash: 'fingerprint-event',
    };

    renderRealtimeProbe();

    act(() => {
      FakeWebSocket.instances[0].open();
    });

    act(() => {
      FakeWebSocket.instances[0].onmessage?.({
        data: JSON.stringify({
          data: { beacon: eventBeacon },
          id: 'event-1',
          occurred_at: '2026-06-08T00:00:01Z',
          scope: { beacon_id: eventBeacon.id },
          source: { role: 'c2', service: 'xero-c2-core' },
          type: 'beacon.registered',
          version: 1,
        }),
      } as MessageEvent);
    });

    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('1'));
    expect(screen.getByTestId('first-host').textContent).toBe('event-first');

    act(() => {
      resolveReconcile?.({ items: [baseBeacon] });
    });

    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('2'));
    expect(screen.getByTestId('hosts').textContent).toContain('event-first');
    expect(screen.getByTestId('hosts').textContent).toContain('realtime-one');
  });
});
