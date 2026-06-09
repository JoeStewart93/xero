import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  OperatorRealtimeClient,
  operatorWebSocketUrl,
  parseRealtimeEvent,
  reconnectDelayMs,
} from './operatorRealtime';

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
  sent: string[] = [];
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

  receive(data: string) {
    this.onmessage?.({ data } as MessageEvent);
  }

  send(data: string) {
    this.sent.push(data);
  }
}

const eventPayload = {
  data: {},
  id: 'event-1',
  occurred_at: '2026-06-08T00:00:00Z',
  scope: {},
  source: { role: 'c2', service: 'xero-c2-core' },
  type: 'beacon.registered',
  version: 1,
};

describe('operatorRealtime', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('derives websocket URLs from C2 backend URLs', () => {
    expect(operatorWebSocketUrl('http://localhost:8001')).toBe('ws://localhost:8001/ws/operator');
    expect(operatorWebSocketUrl('https://c2.example.test/api')).toBe('wss://c2.example.test/ws/operator');
  });

  it('parses valid realtime events and drops invalid payloads', () => {
    expect(parseRealtimeEvent(JSON.stringify(eventPayload))?.type).toBe('beacon.registered');
    expect(
      parseRealtimeEvent(
        JSON.stringify({
          ...eventPayload,
          id: 'event-task',
          scope: { task_id: 'task-1' },
          type: 'task.result.completed',
        }),
      )?.scope.task_id,
    ).toBe('task-1');
    expect(
      parseRealtimeEvent(
        JSON.stringify({
          ...eventPayload,
          id: 'event-session',
          scope: { session_id: 'session-1' },
          type: 'session.output.received',
        }),
      )?.scope.session_id,
    ).toBe('session-1');
    expect(parseRealtimeEvent('not-json')).toBeNull();
    expect(parseRealtimeEvent(JSON.stringify({ version: 1 }))).toBeNull();
  });

  it('calculates capped exponential reconnect delays', () => {
    expect(reconnectDelayMs(0, 100, 1_000)).toBe(100);
    expect(reconnectDelayMs(1, 100, 1_000)).toBe(200);
    expect(reconnectDelayMs(10, 100, 1_000)).toBe(1_000);
  });

  it('connects with C2 token subprotocol and reconnects after an abnormal close', () => {
    const statuses: string[] = [];
    const reconnect = vi.fn();
    const client = new OperatorRealtimeClient({
      accessToken: 'token-1',
      baseUrl: 'http://localhost:8001',
      onEvent: vi.fn(),
      onReconnect: reconnect,
      onStatusChange: (status) => statuses.push(status),
      reconnectBaseMs: 100,
      reconnectMaxMs: 1_000,
      webSocketCtor: FakeWebSocket as unknown as typeof WebSocket,
    });

    client.start();
    expect(FakeWebSocket.instances[0].url).toBe('ws://localhost:8001/ws/operator');
    expect(FakeWebSocket.instances[0].protocols).toEqual(['xero.operator.v1', 'bearer.token-1']);

    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].close(1006);
    vi.advanceTimersByTime(100);

    expect(statuses).toEqual(['connecting', 'connected', 'reconnecting', 'reconnecting']);
    expect(reconnect).toHaveBeenCalledTimes(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    client.stop();
  });

  it('surfaces degraded and recovered system events', () => {
    const statuses: string[] = [];
    const reconnect = vi.fn();
    const events = vi.fn();
    const client = new OperatorRealtimeClient({
      accessToken: 'token-1',
      baseUrl: 'http://localhost:8001',
      onEvent: events,
      onReconnect: reconnect,
      onStatusChange: (status) => statuses.push(status),
      webSocketCtor: FakeWebSocket as unknown as typeof WebSocket,
    });

    client.start();
    FakeWebSocket.instances[0].open();
    FakeWebSocket.instances[0].receive(JSON.stringify({ ...eventPayload, id: 'event-2', type: 'system.realtime.degraded' }));
    FakeWebSocket.instances[0].receive(JSON.stringify({ ...eventPayload, id: 'event-3', type: 'system.realtime.recovered' }));

    expect(statuses).toContain('degraded');
    expect(statuses.at(-1)).toBe('connected');
    expect(reconnect).toHaveBeenCalledTimes(2);
    expect(events).toHaveBeenCalledTimes(2);

    client.stop();
  });
});
