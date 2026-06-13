import { shellSessionWebSocketUrl } from './api';
import type { FileBrowserSession, RegistrySession, ShellSession } from './api';

export type ShellSessionConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'reconnecting';

export interface ShellSessionMessage {
  cached?: boolean;
  confirm_token?: string;
  content?: string;
  data?: string;
  data_b64?: string;
  encoding?: string;
  entries?: FileBrowserEntry[];
  error_code?: string;
  expires_at?: string;
  acked_chunks?: number;
  artifact_id?: string | null;
  chunk_size_bytes?: number;
  hive?: string;
  key_path?: string;
  message?: string;
  modified_at?: string;
  next_sequence?: number;
  ok?: boolean;
  op: string;
  path?: string;
  permissions?: string;
  progress?: number;
  request_id?: string;
  sequence?: number;
  session?: FileBrowserSession | RegistrySession | ShellSession;
  session_id?: string;
  sha256?: string | null;
  size?: number;
  size_bytes?: number;
  stream?: string;
  subkeys?: string[];
  truncated?: boolean;
  total_chunks?: number;
  transfer_id?: string;
  type?: string;
  value?: number | string | string[];
  value_name?: string;
  value_type?: string;
  values?: RegistryValueEntry[];
  writable?: boolean;
}

export interface FileBrowserEntry {
  modified_at: string;
  name: string;
  path: string;
  permissions: string;
  size: number;
  type: 'directory' | 'file' | 'other' | 'symlink';
}

export interface RegistryValueEntry {
  name: string;
  type: string;
  value?: number | string | string[];
  writable: boolean;
}

interface ShellSessionClientOptions {
  accessToken: string;
  baseUrl: string;
  onMessage: (message: ShellSessionMessage) => void;
  onStatusChange: (status: ShellSessionConnectionStatus, error?: string) => void;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
  sessionId: string;
  webSocketCtor?: typeof WebSocket;
}

const SESSION_PROTOCOL = 'xero.session.v1';
const TOKEN_PROTOCOL_PREFIX = 'bearer.';
const DEFAULT_RECONNECT_BASE_MS = 250;
const DEFAULT_RECONNECT_MAX_MS = 4_000;

export function parseShellSessionMessage(payload: string): ShellSessionMessage | null {
  try {
    const parsed = JSON.parse(payload) as ShellSessionMessage;
    if (!parsed || typeof parsed !== 'object' || typeof parsed.op !== 'string') {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function shellSessionReconnectDelayMs(
  attempt: number,
  baseMs = DEFAULT_RECONNECT_BASE_MS,
  maxMs = DEFAULT_RECONNECT_MAX_MS,
): number {
  return Math.min(maxMs, baseMs * 2 ** Math.max(0, attempt));
}

export class ShellSessionClient {
  private readonly accessToken: string;
  private readonly baseUrl: string;
  private readonly onMessage: (message: ShellSessionMessage) => void;
  private readonly onStatusChange: (status: ShellSessionConnectionStatus, error?: string) => void;
  private readonly reconnectBaseMs: number;
  private readonly reconnectMaxMs: number;
  private readonly sessionId: string;
  private readonly webSocketCtor: typeof WebSocket;
  private pendingFlushTimer: number | undefined;
  private pendingMessages: string[] = [];
  private reconnectAttempt = 0;
  private reconnectTimer: number | undefined;
  private socket: WebSocket | null = null;
  private stopped = false;

  constructor(options: ShellSessionClientOptions) {
    this.accessToken = options.accessToken;
    this.baseUrl = options.baseUrl;
    this.onMessage = options.onMessage;
    this.onStatusChange = options.onStatusChange;
    this.reconnectBaseMs = options.reconnectBaseMs ?? DEFAULT_RECONNECT_BASE_MS;
    this.reconnectMaxMs = options.reconnectMaxMs ?? DEFAULT_RECONNECT_MAX_MS;
    this.sessionId = options.sessionId;
    this.webSocketCtor = options.webSocketCtor ?? WebSocket;
  }

  start(): void {
    this.stopped = false;
    this.connect('connecting');
  }

  stop(): void {
    this.stopped = true;
    this.pendingMessages = [];
    this.clearPendingFlush();
    this.clearReconnect();
    if (this.socket) {
      this.socket.close(1000);
      this.socket = null;
    }
    this.onStatusChange('disconnected');
  }

  isOpen(): boolean {
    return this.socket?.readyState === this.webSocketCtor.OPEN;
  }

  sendInput(data: string): void {
    this.send({ data, op: 'stdin' });
  }

  resize(cols: number, rows: number): void {
    this.send({ cols, op: 'resize', rows });
  }

  closeSession(): void {
    this.send({ op: 'close' });
  }

  sendMessage(payload: Record<string, unknown>): void {
    this.send(payload);
  }

  private connect(status: ShellSessionConnectionStatus): void {
    if (this.stopped) {
      return;
    }
    this.onStatusChange(status);
    this.socket = new this.webSocketCtor(shellSessionWebSocketUrl(this.baseUrl, this.sessionId), [
      SESSION_PROTOCOL,
      `${TOKEN_PROTOCOL_PREFIX}${this.accessToken}`,
    ]);

    this.socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.onStatusChange('connected');
      this.flushPendingMessages();
    };

    this.socket.onmessage = (event) => {
      const message = parseShellSessionMessage(String(event.data));
      if (message) {
        this.onMessage(message);
      }
    };

    this.socket.onerror = () => {
      if (!this.stopped) {
        this.onStatusChange('reconnecting', 'Shell session websocket error.');
      }
    };

    this.socket.onclose = (event) => {
      if (this.stopped) {
        return;
      }
      if ([4401, 4404, 4409].includes(event.code)) {
        this.onStatusChange('disconnected', this.closeReason(event.code));
        return;
      }
      this.scheduleReconnect();
    };
  }

  private send(payload: Record<string, unknown>): void {
    const serialized = JSON.stringify(payload);
    if (!this.isOpen()) {
      if (!this.stopped) {
        this.pendingMessages.push(serialized);
        this.schedulePendingFlush();
      }
      return;
    }
    this.socket?.send(serialized);
  }

  private flushPendingMessages(): void {
    this.clearPendingFlush();
    if (!this.isOpen() || this.pendingMessages.length === 0) {
      return;
    }
    const messages = this.pendingMessages;
    this.pendingMessages = [];
    for (const message of messages) {
      this.socket?.send(message);
    }
  }

  private schedulePendingFlush(): void {
    if (this.pendingFlushTimer !== undefined) {
      return;
    }
    this.pendingFlushTimer = window.setTimeout(() => {
      this.pendingFlushTimer = undefined;
      this.flushPendingMessages();
    }, 0);
  }

  private clearPendingFlush(): void {
    if (this.pendingFlushTimer !== undefined) {
      window.clearTimeout(this.pendingFlushTimer);
      this.pendingFlushTimer = undefined;
    }
  }

  private scheduleReconnect(): void {
    this.onStatusChange('reconnecting');
    const delay = shellSessionReconnectDelayMs(this.reconnectAttempt, this.reconnectBaseMs, this.reconnectMaxMs);
    this.reconnectAttempt += 1;
    this.reconnectTimer = window.setTimeout(() => this.connect('reconnecting'), delay);
  }

  private clearReconnect(): void {
    if (this.reconnectTimer !== undefined) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
  }

  private closeReason(code: number): string {
    if (code === 4401) {
      return 'Shell session authentication failed.';
    }
    if (code === 4404) {
      return 'Shell session was not found.';
    }
    return 'Shell session already has an attached operator.';
  }
}
