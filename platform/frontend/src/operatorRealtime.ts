import type { Task, TaskResult, TaskResultChunk } from './api';

export type RealtimeStatus = 'connected' | 'connecting' | 'degraded' | 'disconnected' | 'reconnecting';

export interface OperatorRealtimeEvent {
  data: Record<string, unknown>;
  id: string;
  occurred_at: string;
  scope: {
    beacon_id?: string | null;
    project_id?: string | null;
    scan_job_id?: string | null;
    session_id?: string | null;
    task_id?: string | null;
  };
  source: {
    role: string;
    service: string;
  };
  type: string;
  version: 1;
}

interface OperatorRealtimeClientOptions {
  accessToken: string;
  baseUrl: string;
  onEvent: (event: OperatorRealtimeEvent) => void;
  onReconnect: () => void;
  onStatusChange: (status: RealtimeStatus, error?: string) => void;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
  webSocketCtor?: typeof WebSocket;
}

const REALTIME_PROTOCOL = 'xero.operator.v1';
const TOKEN_PROTOCOL_PREFIX = 'bearer.';
const DEFAULT_RECONNECT_BASE_MS = 250;
const DEFAULT_RECONNECT_MAX_MS = 5_000;
const HEARTBEAT_INTERVAL_MS = 25_000;

export function operatorWebSocketUrl(baseUrl: string): string {
  const url = new URL(baseUrl);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = '/ws/operator';
  url.search = '';
  url.hash = '';
  return url.toString();
}

export function reconnectDelayMs(attempt: number, baseMs = DEFAULT_RECONNECT_BASE_MS, maxMs = DEFAULT_RECONNECT_MAX_MS): number {
  return Math.min(maxMs, baseMs * 2 ** Math.max(0, attempt));
}

export function parseRealtimeEvent(payload: string): OperatorRealtimeEvent | null {
  try {
    const parsed = JSON.parse(payload) as OperatorRealtimeEvent;
    if (parsed.version !== 1 || !parsed.id || !parsed.type) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function eventRecordValue<T>(event: OperatorRealtimeEvent, key: string): T | null {
  const value = event.data[key];
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as T : null;
}

export function taskFromRealtimeEvent(event: OperatorRealtimeEvent): Task | null {
  return eventRecordValue<Task>(event, 'task');
}

export function taskResultFromRealtimeEvent(event: OperatorRealtimeEvent): TaskResult | null {
  return eventRecordValue<TaskResult>(event, 'task_result');
}

export function taskResultChunkFromRealtimeEvent(event: OperatorRealtimeEvent): TaskResultChunk | null {
  return event.type === 'task.result.chunk' ? eventRecordValue<TaskResultChunk>(event, 'task_result_chunk') : null;
}

export class OperatorRealtimeClient {
  private readonly accessToken: string;
  private readonly baseUrl: string;
  private readonly onEvent: (event: OperatorRealtimeEvent) => void;
  private readonly onReconnect: () => void;
  private readonly onStatusChange: (status: RealtimeStatus, error?: string) => void;
  private readonly reconnectBaseMs: number;
  private readonly reconnectMaxMs: number;
  private readonly webSocketCtor: typeof WebSocket;
  private heartbeatTimer: number | undefined;
  private reconnectAttempt = 0;
  private reconnectTimer: number | undefined;
  private socket: WebSocket | null = null;
  private stopped = false;

  constructor(options: OperatorRealtimeClientOptions) {
    this.accessToken = options.accessToken;
    this.baseUrl = options.baseUrl;
    this.onEvent = options.onEvent;
    this.onReconnect = options.onReconnect;
    this.onStatusChange = options.onStatusChange;
    this.reconnectBaseMs = options.reconnectBaseMs ?? DEFAULT_RECONNECT_BASE_MS;
    this.reconnectMaxMs = options.reconnectMaxMs ?? DEFAULT_RECONNECT_MAX_MS;
    this.webSocketCtor = options.webSocketCtor ?? WebSocket;
  }

  start(): void {
    this.stopped = false;
    this.connect('connecting');
  }

  stop(): void {
    this.stopped = true;
    this.clearTimers();
    if (this.socket) {
      this.socket.close(1000);
      this.socket = null;
    }
    this.onStatusChange('disconnected');
  }

  private connect(status: RealtimeStatus): void {
    if (this.stopped) {
      return;
    }
    this.onStatusChange(status);
    this.socket = new this.webSocketCtor(operatorWebSocketUrl(this.baseUrl), [
      REALTIME_PROTOCOL,
      `${TOKEN_PROTOCOL_PREFIX}${this.accessToken}`,
    ]);

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.onStatusChange('connected');
      this.onReconnect();
      this.heartbeatTimer = window.setInterval(() => {
        if (this.socket?.readyState === this.webSocketCtor.OPEN) {
          this.socket.send('ping');
        }
      }, HEARTBEAT_INTERVAL_MS);
    };

    this.socket.onmessage = (message) => {
      const event = parseRealtimeEvent(String(message.data));
      if (!event) {
        return;
      }
      if (event.type === 'system.realtime.degraded') {
        this.onStatusChange('degraded', 'Realtime event stream is degraded.');
      }
      if (event.type === 'system.realtime.recovered') {
        this.onStatusChange('connected');
        this.onReconnect();
      }
      this.onEvent(event);
    };

    this.socket.onerror = () => {
      if (!this.stopped) {
        this.onStatusChange('degraded', 'Realtime websocket error.');
      }
    };

    this.socket.onclose = (event) => {
      this.clearHeartbeat();
      if (this.stopped) {
        return;
      }
      if (event.code === 4401) {
        this.onStatusChange('disconnected', 'Realtime authentication failed.');
        return;
      }
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    this.onStatusChange('reconnecting');
    const delay = reconnectDelayMs(this.reconnectAttempt, this.reconnectBaseMs, this.reconnectMaxMs);
    this.reconnectAttempt += 1;
    this.reconnectTimer = window.setTimeout(() => this.connect('reconnecting'), delay);
  }

  private clearHeartbeat(): void {
    if (this.heartbeatTimer !== undefined) {
      window.clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
  }

  private clearTimers(): void {
    this.clearHeartbeat();
    if (this.reconnectTimer !== undefined) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
  }
}
