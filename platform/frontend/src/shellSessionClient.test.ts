import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  ShellSessionClient,
  parseShellSessionMessage,
  shellSessionReconnectDelayMs,
} from './shellSessionClient';

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

describe('shell session client', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('parses valid shell messages and drops invalid payloads', () => {
    expect(parseShellSessionMessage(JSON.stringify({ data: 'ok', op: 'stdout' }))).toEqual({ data: 'ok', op: 'stdout' });
    expect(parseShellSessionMessage(JSON.stringify({ data: 'missing-op' }))).toBeNull();
    expect(parseShellSessionMessage('not-json')).toBeNull();
    expect(shellSessionReconnectDelayMs(3, 100, 500)).toBe(500);
  });

  it('connects with session protocols and sends terminal operations', () => {
    const messages = vi.fn();
    const statuses = vi.fn();
    const client = new ShellSessionClient({
      accessToken: 'token-one',
      baseUrl: 'http://localhost:8001',
      onMessage: messages,
      onStatusChange: statuses,
      sessionId: 'session-one',
      webSocketCtor: FakeWebSocket as unknown as typeof WebSocket,
    });

    client.start();
    expect(FakeWebSocket.instances[0].url).toBe('ws://localhost:8001/ws/sessions/session-one');
    expect(FakeWebSocket.instances[0].protocols).toEqual(['xero.session.v1', 'bearer.token-one']);

    FakeWebSocket.instances[0].open();
    client.sendInput('whoami\r');
    client.resize(100, 30);
    client.closeSession();
    FakeWebSocket.instances[0].receive(JSON.stringify({ data: 'output', op: 'stdout' }));

    expect(statuses).toHaveBeenCalledWith('connecting');
    expect(statuses).toHaveBeenCalledWith('connected');
    expect(FakeWebSocket.instances[0].sent.map((item) => JSON.parse(item))).toEqual([
      { data: 'whoami\r', op: 'stdin' },
      { cols: 100, op: 'resize', rows: 30 },
      { op: 'close' },
    ]);
    expect(messages).toHaveBeenCalledWith({ data: 'output', op: 'stdout' });
  });

  it('reconnects unexpected closes and stops cleanly', async () => {
    const statuses = vi.fn();
    const client = new ShellSessionClient({
      accessToken: 'token-one',
      baseUrl: 'http://localhost:8001',
      onMessage: vi.fn(),
      onStatusChange: statuses,
      reconnectBaseMs: 100,
      sessionId: 'session-one',
      webSocketCtor: FakeWebSocket as unknown as typeof WebSocket,
    });

    client.start();
    FakeWebSocket.instances[0].close(1006);
    expect(statuses).toHaveBeenLastCalledWith('reconnecting');

    await vi.advanceTimersByTimeAsync(100);
    expect(FakeWebSocket.instances).toHaveLength(2);

    client.stop();
    expect(statuses).toHaveBeenLastCalledWith('disconnected');
  });
});
