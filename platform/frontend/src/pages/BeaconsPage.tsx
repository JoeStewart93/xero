import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import { KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDownUp,
  Boxes,
  Cpu,
  Crosshair,
  Download,
  Eye,
  File,
  FileArchive,
  FileText,
  Fingerprint,
  Folder,
  KeyRound,
  Network,
  RadioTower,
  RefreshCw,
  RotateCcw,
  Search,
  Server,
  ShieldCheck,
  TerminalSquare,
  Trash2,
  X,
} from 'lucide-react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';

import {
  assignBeaconTrafficProfile,
  clearBeaconTrafficProfile,
  closeFileBrowserSession,
  closeShellSession,
  createFileBrowserSession,
  createShellSession,
  getBeaconActivity,
  getTrafficProfiles,
  killBeacon,
} from '../api';
import type {
  Beacon,
  BeaconActivityItem,
  FileBrowserSession,
  ShellSession,
  ShellType,
  TrafficProfile,
} from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { ModalShell } from '../components/ModalShell';
import type { C2Connection } from '../c2ConnectionContext';
import type { OperatorRealtimeEvent } from '../operatorRealtime';
import { decodeLaunchArgs } from '../modules/moduleCatalog';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';
import { ShellSessionClient } from '../shellSessionClient';
import type { FileBrowserEntry, ShellSessionConnectionStatus, ShellSessionMessage } from '../shellSessionClient';
import { RegistrySessionPanel } from './RegistrySessionPanel';
import { TaskExecutionPanel } from './TaskExecutionPanel';
import { writeBeaconDragData } from './taskDrag';
import {
  DEFAULT_BEACON_SORT_DIRECTION,
  DEFAULT_BEACON_SORT_KEY,
  BeaconSortDirection,
  BeaconSortKey,
  compactDateTime,
  formatDateTime,
  formatRelativeTime,
  searchBeacon,
  sortBeacons,
  statusClass,
  transportLabel,
  transportState,
} from './beaconDisplay';
import '@xterm/xterm/css/xterm.css';

function DetailRow({ label, testId, value }: { label: string; testId?: string; value: string | number | null }) {
  return (
    <div className="beacon-detail-row">
      <span>{label}</span>
      <strong data-testid={testId}>{value ?? '-'}</strong>
    </div>
  );
}

function BeaconActivityTimeline({
  error,
  isLoading,
  items,
}: {
  error: string;
  isLoading: boolean;
  items: BeaconActivityItem[];
}) {
  if (isLoading) {
    return <div className="beacon-activity-empty">Loading activity.</div>;
  }
  if (error) {
    return <p className="task-queue-error" role="alert">{error}</p>;
  }
  if (items.length === 0) {
    return <div className="beacon-activity-empty">No recent activity for this beacon.</div>;
  }
  return (
    <div className="beacon-activity-list" data-testid="beacon-activity-list">
      {items.map((item) => (
        <div className="beacon-activity-item" key={item.id}>
          <div>
            <strong>{item.label}</strong>
            <span>{item.detail ?? item.type}</span>
          </div>
          <time dateTime={item.occurred_at}>{formatRelativeTime(item.occurred_at)}</time>
        </div>
      ))}
    </div>
  );
}

function KillBeaconModal({
  beacon,
  error,
  isKilling,
  onCancel,
  onConfirm,
}: {
  beacon: Beacon;
  error: string;
  isKilling: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <ModalShell ariaLabel="Kill beacon confirmation" onClose={onCancel} title="Kill beacon?">
      <div className="beacon-kill-modal-body">
        <p>
          Remove <strong>{beacon.hostname}</strong> from active inventory, close active sessions, and cancel queued tasks.
          This does not delete historical task or session records.
        </p>
        <div className="beacon-kill-facts">
          <DetailRow label="Beacon ID" value={beacon.id} />
          <DetailRow label="Fingerprint" value={beacon.machine_fingerprint_hash} />
          <DetailRow label="Last seen" value={formatDateTime(beacon.last_seen)} />
        </div>
        {error ? <p className="task-queue-error" role="alert">{error}</p> : null}
        <div className="beacon-kill-actions">
          <button className="secondary-button" disabled={isKilling} onClick={onCancel} type="button">
            Cancel
          </button>
          <button className="danger-button" disabled={isKilling} onClick={onConfirm} type="button">
            <Trash2 aria-hidden="true" size={15} strokeWidth={2.1} />
            <span>{isKilling ? 'Killing' : 'Kill beacon'}</span>
          </button>
        </div>
      </div>
    </ModalShell>
  );
}

const hostOperations = [
  {
    description: 'Prepare a scoped command or module task for this beacon.',
    icon: TerminalSquare,
    key: 'commands',
    label: 'Command queue',
    status: 'Ready',
  },
  {
    description: 'Attach to a live shell with streaming stdin and stdout.',
    icon: Crosshair,
    key: 'session',
    label: 'Interactive session',
    status: 'Ready',
  },
  {
    description: 'Browse host files and preview safe text output.',
    icon: FileArchive,
    key: 'files',
    label: 'Files',
    status: 'Ready',
  },
  {
    description: 'Browse and edit Windows registry values with confirmation safeguards.',
    icon: KeyRound,
    key: 'registry',
    label: 'Registry',
    status: 'Ready',
  },
  {
    description: 'Review credential material associated with this host.',
    icon: KeyRound,
    key: 'credentials',
    label: 'Credentials',
    status: 'Planned',
  },
  {
    description: 'Pivot into inventory records, modules, and post-exploitation actions.',
    icon: Boxes,
    key: 'inventory',
    label: 'Inventory actions',
    status: 'Planned',
  },
] as const;

type HostOperationKey = (typeof hostOperations)[number]['key'];
type BeaconStatusFilter = 'all' | 'offline' | 'online';

const shellTypes: ShellType[] = ['auto', 'cmd', 'powershell', 'bash'];
const beaconStatusFilters: BeaconStatusFilter[] = ['all', 'online', 'offline'];

function initialBeaconStatusFilter(search: string): BeaconStatusFilter {
  const status = new URLSearchParams(search).get('status');
  return status === 'online' || status === 'offline' ? status : 'all';
}

function statusFilterLabel(statusFilter: BeaconStatusFilter): string {
  return statusFilter === 'all' ? 'All' : statusFilter[0].toUpperCase() + statusFilter.slice(1);
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function escapeCsvField(value: string | number | null | undefined): string {
  const text = value == null ? '' : String(value);
  if (!/[",\r\n]/.test(text)) {
    return text;
  }
  return `"${text.replace(/"/g, '""')}"`;
}

function beaconCsv(beacons: Beacon[]): string {
  const columns: Array<[string, (beacon: Beacon) => string | number | null | undefined]> = [
    ['hostname', (beacon) => beacon.hostname],
    ['os', (beacon) => beacon.os],
    ['status', (beacon) => beacon.status],
    ['last_seen', (beacon) => beacon.last_seen],
    ['transport', (beacon) => transportLabel(beacon.transport_mode)],
    ['transport_state', (beacon) => transportState(beacon)],
    ['profile', (beacon) => beacon.profile_name ?? 'Default bootstrap'],
    ['internal_ip', (beacon) => beacon.internal_ip],
    ['external_ip', (beacon) => beacon.external_ip],
    ['pid', (beacon) => beacon.pid],
    ['architecture', (beacon) => beacon.architecture],
    ['id', (beacon) => beacon.id],
    ['machine_fingerprint_hash', (beacon) => beacon.machine_fingerprint_hash],
  ];
  const header = columns.map(([label]) => label).join(',');
  const rows = beacons.map((beacon) => columns.map(([, value]) => escapeCsvField(value(beacon))).join(','));
  return [header, ...rows].join('\r\n');
}

function downloadBeaconCsv(beacons: Beacon[]): void {
  const blob = new Blob([beaconCsv(beacons)], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `xero-beacons-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function filePathLabel(path: string): string {
  return path || '/';
}

function fileBreadcrumbs(path: string): Array<{ label: string; path: string }> {
  const parts = path.split('/').filter(Boolean);
  const crumbs = [{ label: '/', path: '' }];
  parts.forEach((part, index) => {
    crumbs.push({ label: part, path: parts.slice(0, index + 1).join('/') });
  });
  return crumbs;
}

function fileErrorMessage(message: ShellSessionMessage): string {
  if (message.message) {
    return message.message;
  }
  if (message.error_code) {
    return message.error_code.replace(/_/g, ' ');
  }
  return 'File browser operation failed.';
}

function isTerminalSessionActive(session: ShellSession | null): boolean {
  return Boolean(session && !['closed', 'failed'].includes(session.status));
}

function decodeTerminalData(message: ShellSessionMessage): string {
  if (typeof message.data === 'string') {
    return message.data;
  }
  if (!message.data_b64) {
    return '';
  }
  try {
    const raw = window.atob(message.data_b64);
    const bytes = Uint8Array.from(raw, (char) => char.charCodeAt(0));
    return new TextDecoder().decode(bytes);
  } catch {
    return '';
  }
}

function ShellSessionPanel({
  beacon,
  connection,
}: {
  beacon: Beacon;
  connection: C2Connection;
}) {
  const terminalElementRef = useRef<HTMLDivElement | null>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const clientRef = useRef<ShellSessionClient | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ShellSessionConnectionStatus>('disconnected');
  const [error, setError] = useState('');
  const [isClosingSession, setIsClosingSession] = useState(false);
  const [isOpeningSession, setIsOpeningSession] = useState(false);
  const [session, setSession] = useState<ShellSession | null>(null);
  const [sessionShellType, setSessionShellType] = useState<ShellType>('auto');
  const [terminalTranscript, setTerminalTranscript] = useState('');
  const activeSession = isTerminalSessionActive(session);

  const appendTerminal = useCallback((text: string) => {
    if (!text) {
      return;
    }
    terminalRef.current?.write(text);
    setTerminalTranscript((current) => `${current}${text}`.slice(-20_000));
  }, []);

  const handleSessionStatus = useCallback((status: ShellSessionConnectionStatus, message?: string) => {
    setConnectionStatus(status);
    if (message) {
      setError(message);
    } else if (status === 'connected') {
      setError('');
    }
  }, []);

  const handleSessionMessage = useCallback((message: ShellSessionMessage) => {
    if (message.session?.session_type === 'shell') {
      setSession(message.session);
    }
    if (message.op === 'attached') {
      appendTerminal(`\r\nAttached to session ${message.session?.id ?? ''}\r\n`);
      return;
    }
    if (message.op === 'opened') {
      appendTerminal('\r\nSession opened.\r\n');
      setError('');
      return;
    }
    if (message.op === 'stdout' || message.op === 'stderr') {
      appendTerminal(decodeTerminalData(message));
      return;
    }
    if (message.op === 'closed') {
      appendTerminal('\r\nSession closed.\r\n');
      clientRef.current?.stop();
      return;
    }
    if (message.op === 'error') {
      const messageText = message.message ?? message.session?.close_reason ?? 'Shell session error.';
      setError(messageText);
      appendTerminal(`\r\n${messageText}\r\n`);
    }
  }, [appendTerminal]);

  useEffect(() => {
    if (!terminalElementRef.current || terminalRef.current) {
      return;
    }
    const terminal = new Terminal({
      convertEol: true,
      cursorBlink: true,
      fontFamily: '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
      fontSize: 12,
      rows: 32,
      theme: {
        background: '#010509',
        cursor: '#00e7ff',
        foreground: '#d7f7ff',
        selectionBackground: '#214a55',
      },
    });
    const fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(terminalElementRef.current);
    fitAddon.fit();
    const inputSubscription = terminal.onData((data) => {
      clientRef.current?.sendInput(data);
    });
    terminalRef.current = terminal;
    fitAddonRef.current = fitAddon;

    function handleResize(): void {
      fitAddon.fit();
      clientRef.current?.resize(terminal.cols, terminal.rows);
    }

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      inputSubscription.dispose();
      clientRef.current?.stop();
      terminal.dispose();
      terminalRef.current = null;
      fitAddonRef.current = null;
    };
  }, []);

  async function handleOpenSession(): Promise<void> {
    setIsOpeningSession(true);
    setError('');
    terminalRef.current?.reset();
    setTerminalTranscript('');
    appendTerminal(`Opening ${sessionShellType} shell on ${beacon.hostname}\r\n`);
    try {
      const created = await createShellSession(connection.baseUrl, connection.accessToken, {
        beacon_id: beacon.id,
        cols: 120,
        rows: 32,
        shell_type: sessionShellType,
      });
      setSession(created);
      clientRef.current?.stop();
      const client = new ShellSessionClient({
        accessToken: connection.accessToken,
        baseUrl: connection.baseUrl,
        onMessage: handleSessionMessage,
        onStatusChange: handleSessionStatus,
        sessionId: created.id,
      });
      clientRef.current = client;
      client.start();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to open shell session.';
      setError(message);
      appendTerminal(`${message}\r\n`);
    } finally {
      setIsOpeningSession(false);
    }
  }

  async function handleCloseSession(): Promise<void> {
    if (!session) {
      return;
    }
    setIsClosingSession(true);
    setError('');
    try {
      if (clientRef.current?.isOpen()) {
        clientRef.current.closeSession();
      } else {
        const closed = await closeShellSession(connection.baseUrl, connection.accessToken, session.id);
        setSession(closed);
        appendTerminal('\r\nSession closed.\r\n');
      }
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to close shell session.';
      setError(message);
    } finally {
      setIsClosingSession(false);
    }
  }

  return (
    <div className="shell-session-panel">
      <div className="shell-session-toolbar">
        <label>
          <span>Shell</span>
          <select
            aria-label="Interactive shell type"
            disabled={activeSession || isOpeningSession}
            onChange={(event) => setSessionShellType(event.target.value as ShellType)}
            value={sessionShellType}
          >
            {shellTypes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary-button shell-session-action"
          disabled={activeSession || isOpeningSession || !beacon.transport_connected}
          onClick={() => void handleOpenSession()}
          type="button"
        >
          <TerminalSquare aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>{isOpeningSession ? 'Opening' : 'Open'}</span>
        </button>
        <button
          className="secondary-button shell-session-action"
          disabled={!activeSession || isClosingSession}
          onClick={() => void handleCloseSession()}
          type="button"
        >
          <X aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>{isClosingSession ? 'Closing' : 'Close'}</span>
        </button>
      </div>

      <div className="shell-session-status-strip">
        <span data-testid="shell-session-status">{session?.status ?? connectionStatus}</span>
        <span>{connectionStatus}</span>
        <span>{beacon.transport_connected ? 'Transport online' : 'Transport offline'}</span>
      </div>

      {error ? <p className="task-queue-error" role="alert">{error}</p> : null}

      <div className="shell-session-terminal-frame" data-testid="shell-session-terminal-frame">
        <div aria-label="Interactive shell terminal" className="shell-session-terminal" ref={terminalElementRef} />
      </div>
      <pre aria-hidden="true" className="shell-session-transcript" data-testid="shell-session-transcript">
        {terminalTranscript}
      </pre>
    </div>
  );
}

function FileBrowserPanel({
  beacon,
  connection,
}: {
  beacon: Beacon;
  connection: C2Connection;
}) {
  const clientRef = useRef<ShellSessionClient | null>(null);
  const hasRequestedRootRef = useRef(false);
  const requestCounterRef = useRef(0);
  const [connectionStatus, setConnectionStatus] = useState<ShellSessionConnectionStatus>('disconnected');
  const [currentPath, setCurrentPath] = useState('');
  const [entries, setEntries] = useState<FileBrowserEntry[]>([]);
  const [error, setError] = useState('');
  const [isClosingSession, setIsClosingSession] = useState(false);
  const [isLoadingPath, setIsLoadingPath] = useState(false);
  const [isOpeningSession, setIsOpeningSession] = useState(false);
  const [preview, setPreview] = useState<{
    content: string;
    encoding: string;
    path: string;
    size: number;
    truncated: boolean;
  } | null>(null);
  const [session, setSession] = useState<FileBrowserSession | null>(null);
  const activeSession = Boolean(session && !['closed', 'failed'].includes(session.status));

  const sendFileRequest = useCallback((op: 'list_dir' | 'read_file' | 'stat', path: string, refresh = false) => {
    requestCounterRef.current += 1;
    const requestId = `file-${requestCounterRef.current}`;
    clientRef.current?.sendMessage({
      op,
      path,
      refresh,
      request_id: requestId,
    });
    return requestId;
  }, []);

  const loadDirectory = useCallback((path: string, refresh = false) => {
    setIsLoadingPath(true);
    setError('');
    sendFileRequest('list_dir', path, refresh);
  }, [sendFileRequest]);

  const requestInitialRoot = useCallback(() => {
    if (hasRequestedRootRef.current) {
      return;
    }
    hasRequestedRootRef.current = true;
    window.setTimeout(() => loadDirectory(''), 0);
  }, [loadDirectory]);

  const handleFileMessage = useCallback((message: ShellSessionMessage) => {
    if (message.session?.session_type === 'file_browser') {
      setSession(message.session);
    }
    if (message.op === 'attached' || message.op === 'opened') {
      setError('');
      requestInitialRoot();
      return;
    }
    if (message.op === 'list_dir') {
      setIsLoadingPath(false);
      if (message.ok === false) {
        setError(fileErrorMessage(message));
        return;
      }
      setCurrentPath(message.path ?? '');
      setEntries(message.entries ?? []);
      setPreview(null);
      setError('');
      return;
    }
    if (message.op === 'read_file') {
      if (message.ok === false) {
        setPreview(null);
        setError(fileErrorMessage(message));
        return;
      }
      setPreview({
        content: message.content ?? '',
        encoding: message.encoding ?? 'utf-8',
        path: message.path ?? '',
        size: message.size ?? 0,
        truncated: Boolean(message.truncated),
      });
      setError('');
      return;
    }
    if (message.op === 'closed') {
      clientRef.current?.stop();
      return;
    }
    if (message.op === 'error') {
      setError(fileErrorMessage(message));
    }
  }, [requestInitialRoot]);

  const handleSessionStatus = useCallback((status: ShellSessionConnectionStatus, message?: string) => {
    setConnectionStatus(status);
    if (message) {
      setError(message);
    } else if (status === 'connected') {
      setError('');
    }
  }, []);

  useEffect(() => () => clientRef.current?.stop(), []);

  useEffect(() => {
    if (activeSession && connectionStatus === 'connected') {
      requestInitialRoot();
    }
  }, [activeSession, connectionStatus, requestInitialRoot]);

  async function handleOpenSession(): Promise<void> {
    setIsOpeningSession(true);
    setError('');
    setEntries([]);
    setPreview(null);
    setCurrentPath('');
    hasRequestedRootRef.current = false;
    try {
      const created = await createFileBrowserSession(connection.baseUrl, connection.accessToken, {
        beacon_id: beacon.id,
      });
      setSession(created);
      clientRef.current?.stop();
      const client = new ShellSessionClient({
        accessToken: connection.accessToken,
        baseUrl: connection.baseUrl,
        onMessage: handleFileMessage,
        onStatusChange: handleSessionStatus,
        sessionId: created.id,
      });
      clientRef.current = client;
      client.start();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to open file browser.';
      setError(message);
    } finally {
      setIsOpeningSession(false);
    }
  }

  async function handleCloseSession(): Promise<void> {
    if (!session) {
      return;
    }
    setIsClosingSession(true);
    setError('');
    try {
      if (clientRef.current?.isOpen()) {
        clientRef.current.closeSession();
      } else {
        const closed = await closeFileBrowserSession(connection.baseUrl, connection.accessToken, session.id);
        setSession(closed);
      }
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to close file browser.';
      setError(message);
    } finally {
      setIsClosingSession(false);
    }
  }

  function handleEntryOpen(entry: FileBrowserEntry): void {
    if (entry.type === 'directory') {
      loadDirectory(entry.path);
      return;
    }
    sendFileRequest('read_file', entry.path);
  }

  return (
    <div className="file-browser-panel">
      <div className="shell-session-toolbar">
        <button
          className="primary-button shell-session-action"
          disabled={activeSession || isOpeningSession || !beacon.transport_connected}
          onClick={() => void handleOpenSession()}
          type="button"
        >
          <Folder aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>{isOpeningSession ? 'Opening' : 'Open'}</span>
        </button>
        <button
          className="secondary-button shell-session-action"
          disabled={!activeSession || isClosingSession}
          onClick={() => void handleCloseSession()}
          type="button"
        >
          <X aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>{isClosingSession ? 'Closing' : 'Close'}</span>
        </button>
        <button
          aria-label="Refresh current directory"
          className="secondary-button shell-session-action"
          disabled={!activeSession || isLoadingPath}
          onClick={() => loadDirectory(currentPath, true)}
          type="button"
        >
          <RefreshCw aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>{isLoadingPath ? 'Loading' : 'Refresh'}</span>
        </button>
      </div>

      <div className="shell-session-status-strip">
        <span data-testid="file-browser-status">{session?.status ?? connectionStatus}</span>
        <span>{connectionStatus}</span>
        <span>{beacon.transport_connected ? 'Transport online' : 'Transport offline'}</span>
      </div>

      {error ? <p className="task-queue-error" role="alert">{error}</p> : null}

      <div className="file-browser-breadcrumbs" aria-label="File browser breadcrumbs">
        {fileBreadcrumbs(currentPath).map((crumb) => (
          <button
            disabled={!activeSession || crumb.path === currentPath}
            key={crumb.path || 'root'}
            onClick={() => loadDirectory(crumb.path)}
            type="button"
          >
            {crumb.label}
          </button>
        ))}
      </div>

      <div className="file-browser-grid">
        <div className="file-browser-table-wrap">
          <table className="file-browser-table">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Type</th>
                <th scope="col">Size</th>
                <th scope="col">Modified</th>
                <th scope="col">Mode</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <span className="file-browser-empty">{activeSession ? 'No entries.' : 'Open a file browser session.'}</span>
                  </td>
                </tr>
              ) : (
                entries.map((entry) => {
                  const EntryIcon = entry.type === 'directory' ? Folder : entry.type === 'file' ? FileText : File;
                  return (
                    <tr key={entry.path}>
                      <td>
                        <button className="file-browser-entry-button" onClick={() => handleEntryOpen(entry)} type="button">
                          <EntryIcon aria-hidden="true" size={15} strokeWidth={2.1} />
                          <span>{entry.name}</span>
                        </button>
                      </td>
                      <td>{entry.type}</td>
                      <td>{entry.type === 'directory' ? '-' : formatBytes(entry.size)}</td>
                      <td>{entry.modified_at ? compactDateTime(entry.modified_at) : '-'}</td>
                      <td>
                        <span className="beacon-mono">{entry.permissions}</span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        <aside className="file-preview-panel" aria-label="File preview">
          <div className="task-result-panel-head">
            <div>
              <strong>Preview</strong>
              <span>{preview ? filePathLabel(preview.path) : filePathLabel(currentPath)}</span>
            </div>
            <Eye aria-hidden="true" size={15} strokeWidth={2.1} />
          </div>
          {preview ? (
            <>
              <div className="task-result-meta">
                <span>{formatBytes(preview.size)}</span>
                <span>{preview.encoding}</span>
                <span>{preview.truncated ? 'Truncated' : 'Complete'}</span>
              </div>
              <pre className="file-preview-output" data-testid="file-preview-output">{preview.content}</pre>
            </>
          ) : (
            <div className="task-empty-state">Select a text file to preview.</div>
          )}
        </aside>
      </div>
    </div>
  );
}

function BeaconOperationsModal({
  beacon,
  beacons,
  connection,
  latestEvent,
  onClose,
  realtimeStatus,
}: {
  beacon: Beacon;
  beacons: Beacon[];
  connection: C2Connection;
  latestEvent: OperatorRealtimeEvent | null;
  onClose: () => void;
  realtimeStatus: ReturnType<typeof useRealtime>['status'];
}) {
  const [selectedOperation, setSelectedOperation] = useState<HostOperationKey>('commands');
  const activeOperation = hostOperations.find((operation) => operation.key === selectedOperation) ?? hostOperations[0];
  const ActiveIcon = activeOperation.icon;

  return createPortal(
    <div className="beacon-operations-backdrop" role="presentation">
      <section aria-label={`Host operations for ${beacon.hostname}`} aria-modal="true" className="beacon-operations-modal" role="dialog">
        <div className="beacon-operations-header">
          <div>
            <span className="beacon-operations-kicker">Host operation center</span>
            <h2>{beacon.hostname}</h2>
            <p>
              {beacon.os} / {beacon.internal_ip} / last heartbeat {formatRelativeTime(beacon.last_seen)}
            </p>
          </div>
          <button aria-label="Close host operations" className="beacon-modal-close" onClick={onClose} type="button">
            <X aria-hidden="true" size={17} strokeWidth={2.2} />
          </button>
        </div>

        <div className="beacon-operations-body">
          <nav aria-label="Host operations" className="beacon-operation-rail">
            {hostOperations.map((operation) => {
              const Icon = operation.icon;
              const selected = operation.key === activeOperation.key;
              return (
                <button
                  aria-pressed={selected}
                  className={`beacon-operation-option ${selected ? 'is-selected' : ''}`}
                  key={operation.key}
                  onClick={() => setSelectedOperation(operation.key)}
                  type="button"
                >
                  <Icon aria-hidden="true" size={16} strokeWidth={2.1} />
                  <span>
                    <strong>{operation.label}</strong>
                    <small>{operation.status}</small>
                  </span>
                </button>
              );
            })}
          </nav>

          <div className="beacon-operation-detail" data-testid="beacon-operation-detail">
            <div className="beacon-operation-detail-head">
              <div className="panel-icon" aria-hidden="true">
                <ActiveIcon size={18} strokeWidth={2} />
              </div>
              <div>
                <h3>{activeOperation.label}</h3>
                <p>{activeOperation.description}</p>
              </div>
            </div>

            {activeOperation.key === 'commands' ? (
              <TaskExecutionPanel
                beacons={beacons}
                connection={connection}
                initialBeaconId={beacon.id}
                labelPrefix="Host operation"
                latestEvent={latestEvent}
                realtimeStatus={realtimeStatus}
                testIdPrefix="modal-"
                title="Command queue"
              />
            ) : activeOperation.key === 'session' ? (
              <ShellSessionPanel beacon={beacon} connection={connection} />
            ) : activeOperation.key === 'files' ? (
              <FileBrowserPanel beacon={beacon} connection={connection} />
            ) : activeOperation.key === 'registry' ? (
              <RegistrySessionPanel beacon={beacon} connection={connection} />
            ) : (
              <>
                <div className="beacon-operation-host-grid">
                  <DetailRow label="Hostname" value={beacon.hostname} />
                  <DetailRow label="Operating system" value={beacon.os} />
                  <DetailRow label="Internal IP" value={beacon.internal_ip} />
                  <DetailRow label="External IP" value={beacon.external_ip} />
                  <DetailRow label="Process ID" value={beacon.pid} />
                  <DetailRow label="Architecture" value={beacon.architecture} />
                </div>

                <div className="beacon-operation-locked">
                  <ShieldCheck aria-hidden="true" size={17} strokeWidth={2} />
                  <div>
                    <strong>Selection staged.</strong>
                    <span>No operation has been dispatched to this host.</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </section>
    </div>,
    document.body,
  );
}

export function BeaconsPage() {
  const location = useLocation();
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const routeBeaconId = useMemo(() => new URLSearchParams(location.search).get('beacon_id') ?? '', [location.search]);
  const routeModuleId = useMemo(() => new URLSearchParams(location.search).get('module') ?? '', [location.search]);
  const routeModuleArgs = useMemo(() => decodeLaunchArgs(new URLSearchParams(location.search).get('args')), [location.search]);
  const routeTaskId = useMemo(() => new URLSearchParams(location.search).get('task_id') ?? '', [location.search]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedBeaconId, setSelectedBeaconId] = useState('');
  const [operationBeaconId, setOperationBeaconId] = useState('');
  const [statusFilter, setStatusFilter] = useState<BeaconStatusFilter>(() => initialBeaconStatusFilter(location.search));
  const [removedBeaconIds, setRemovedBeaconIds] = useState<Set<string>>(() => new Set());
  const [profileOverrides, setProfileOverrides] = useState<Record<string, Beacon>>({});
  const [trafficProfiles, setTrafficProfiles] = useState<TrafficProfile[]>([]);
  const [profileError, setProfileError] = useState('');
  const [profileMessage, setProfileMessage] = useState('');
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(false);
  const [assigningProfile, setAssigningProfile] = useState(false);
  const [activityItems, setActivityItems] = useState<BeaconActivityItem[]>([]);
  const [activityError, setActivityError] = useState('');
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);
  const [killTarget, setKillTarget] = useState<Beacon | null>(null);
  const [killError, setKillError] = useState('');
  const [isKillingBeacon, setIsKillingBeacon] = useState(false);
  const [sortKey, setSortKey] = useState<BeaconSortKey>(DEFAULT_BEACON_SORT_KEY);
  const [sortDirection, setSortDirection] = useState<BeaconSortDirection>(DEFAULT_BEACON_SORT_DIRECTION);

  const visibleBeacons = useMemo(
    () => realtime.beacons
      .filter((beacon) => !beacon.removed_at && !removedBeaconIds.has(beacon.id))
      .map((beacon) => profileOverrides[beacon.id] ?? beacon),
    [profileOverrides, realtime.beacons, removedBeaconIds],
  );
  const beacons = useMemo(
    () => sortBeacons(
      visibleBeacons.filter((beacon) => {
        const matchesStatus = statusFilter === 'all' || beacon.status.toLowerCase() === statusFilter;
        return matchesStatus && searchBeacon(beacon, searchQuery.trim());
      }),
      sortKey,
      sortDirection,
    ),
    [searchQuery, sortDirection, sortKey, statusFilter, visibleBeacons],
  );
  const selectedBeacon = beacons.find((beacon) => beacon.id === selectedBeaconId) ?? beacons[0] ?? null;
  const operationBeacon = beacons.find((beacon) => beacon.id === operationBeaconId) ?? null;
  const activeBeaconCount = visibleBeacons.filter((beacon) => beacon.status.toLowerCase() === 'online').length;
  const offlineBeaconCount = visibleBeacons.filter((beacon) => beacon.status.toLowerCase() === 'offline').length;

  const loadBeaconActivity = useCallback(async () => {
    if (!connection || !selectedBeacon) {
      setActivityItems([]);
      setActivityError('');
      return;
    }
    setIsLoadingActivity(true);
    try {
      const response = await getBeaconActivity(connection.baseUrl, connection.accessToken, selectedBeacon.id, 20);
      setActivityItems(response.items);
      setActivityError('');
    } catch (caught) {
      setActivityError(caught instanceof Error ? caught.message : 'Unable to load beacon activity.');
    } finally {
      setIsLoadingActivity(false);
    }
  }, [connection, selectedBeacon]);

  const loadTrafficProfiles = useCallback(async () => {
    if (!connection) {
      setTrafficProfiles([]);
      return;
    }
    setIsLoadingProfiles(true);
    try {
      const response = await getTrafficProfiles(connection.baseUrl, connection.accessToken);
      setTrafficProfiles(response.items);
      setProfileError('');
    } catch (caught) {
      setProfileError(caught instanceof Error ? caught.message : 'Unable to load traffic profiles.');
    } finally {
      setIsLoadingProfiles(false);
    }
  }, [connection]);

  useEffect(() => {
    const handle = window.setTimeout(() => void loadTrafficProfiles(), 0);
    return () => window.clearTimeout(handle);
  }, [loadTrafficProfiles]);

  useEffect(() => {
    const handle = window.setTimeout(() => void loadBeaconActivity(), 0);
    return () => window.clearTimeout(handle);
  }, [loadBeaconActivity]);

  useEffect(() => {
    if (routeBeaconId && visibleBeacons.some((beacon) => beacon.id === routeBeaconId)) {
      const handle = window.setTimeout(() => setSelectedBeaconId(routeBeaconId), 0);
      return () => window.clearTimeout(handle);
    }
    return undefined;
  }, [routeBeaconId, visibleBeacons]);

  useEffect(() => {
    const eventBeaconId = realtime.latestEvent?.scope?.beacon_id ?? (realtime.latestEvent?.data.beacon as Beacon | undefined)?.id;
    if (eventBeaconId && selectedBeacon && eventBeaconId === selectedBeacon.id) {
      const handle = window.setTimeout(() => void loadBeaconActivity(), 0);
      return () => window.clearTimeout(handle);
    }
    return undefined;
  }, [loadBeaconActivity, realtime.latestEvent, selectedBeacon]);

  function handleSort(nextSortKey: BeaconSortKey): void {
    if (nextSortKey === sortKey) {
      setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(nextSortKey);
    setSortDirection(nextSortKey === DEFAULT_BEACON_SORT_KEY ? DEFAULT_BEACON_SORT_DIRECTION : 'asc');
  }

  function handleResetSort(): void {
    setSortKey(DEFAULT_BEACON_SORT_KEY);
    setSortDirection(DEFAULT_BEACON_SORT_DIRECTION);
  }

  function sortLabel(candidate: BeaconSortKey): string {
    if (candidate !== sortKey) {
      return '';
    }
    return sortDirection === 'asc' ? 'Ascending' : 'Descending';
  }

  function renderSortHeader(name: BeaconSortKey, label: string) {
    const active = name === sortKey;
    return (
      <button
        aria-label={`Sort beacons by ${label}`}
        className={`table-sort-button ${active ? 'is-active' : ''}`}
        onClick={() => handleSort(name)}
        type="button"
      >
        <span>{label}</span>
        <em>{sortLabel(name)}</em>
      </button>
    );
  }

  function openBeaconOperations(beacon: Beacon): void {
    setSelectedBeaconId(beacon.id);
    setOperationBeaconId(beacon.id);
  }

  function handleExportCsv(): void {
    if (beacons.length === 0) {
      return;
    }
    downloadBeaconCsv(beacons);
  }

  async function handleConfirmKillBeacon(): Promise<void> {
    if (!connection || !killTarget) {
      return;
    }
    setIsKillingBeacon(true);
    setKillError('');
    try {
      const response = await killBeacon(connection.baseUrl, connection.accessToken, killTarget.id);
      setRemovedBeaconIds((current) => new Set(current).add(response.beacon.id));
      setProfileOverrides((current) => {
        const next = { ...current };
        delete next[response.beacon.id];
        return next;
      });
      setSelectedBeaconId('');
      setOperationBeaconId('');
      setKillTarget(null);
      setProfileMessage(
        `Removed ${response.beacon.hostname}; closed ${response.closed_sessions} sessions and cancelled ${response.cancelled_tasks} tasks.`,
      );
    } catch (caught) {
      setKillError(caught instanceof Error ? caught.message : 'Unable to kill beacon.');
    } finally {
      setIsKillingBeacon(false);
    }
  }

  async function handleAssignProfile(profileId: string): Promise<void> {
    if (!connection || !selectedBeacon) {
      return;
    }
    setAssigningProfile(true);
    setProfileError('');
    setProfileMessage('');
    try {
      const updated = profileId
        ? await assignBeaconTrafficProfile(connection.baseUrl, connection.accessToken, selectedBeacon.id, profileId)
        : await clearBeaconTrafficProfile(connection.baseUrl, connection.accessToken, selectedBeacon.id);
      setProfileOverrides((current) => ({ ...current, [updated.id]: updated }));
      setProfileMessage(profileId ? `Assigned ${updated.profile_name ?? 'traffic profile'}.` : 'Cleared traffic profile assignment.');
    } catch (caught) {
      setProfileError(caught instanceof Error ? caught.message : 'Unable to update beacon profile.');
    } finally {
      setAssigningProfile(false);
    }
  }

  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, beacon: Beacon): void {
    if (event.key === 'Enter') {
      openBeaconOperations(beacon);
    }
  }

  return (
    <AppShell description="Controlled systems reporting through the active C2 backend" section="beacons" title="Beacons" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="beacons-workspace-grid">
          <section className="workspace-panel beacons-roster-panel" aria-label="Beacon overview">
            <div className="panel-header">
              <div>
                <h2>Beacon overview</h2>
                <p className="muted-text">Controlled systems reporting through the active C2 backend.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <RadioTower size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="beacon-summary-strip">
              <div>
                <span>Total</span>
                <strong>{visibleBeacons.length}</strong>
              </div>
              <div>
                <span>Online</span>
                <strong data-testid="beacons-online-count">{activeBeaconCount}</strong>
              </div>
              <div>
                <span>Offline</span>
                <strong data-testid="beacons-offline-count">{offlineBeaconCount}</strong>
              </div>
            </div>

            {visibleBeacons.length === 0 ? (
              <div className="beacon-empty-state" data-testid="beacons-empty-state">
                <RadioTower aria-hidden="true" size={20} strokeWidth={2} />
                <div>
                  <strong>No beacons registered.</strong>
                  <span>Beacon check-ins will appear here as the C2 backend accepts registrations.</span>
                </div>
              </div>
            ) : (
              <>
                <div className="beacon-registry-toolbar">
                  <label className="beacon-search-field">
                    <Search aria-hidden="true" size={15} strokeWidth={2} />
                    <input
                      aria-label="Search beacons"
                      onChange={(event) => setSearchQuery(event.target.value)}
                      placeholder="Search host, IP, OS, fingerprint"
                      value={searchQuery}
                    />
                  </label>
                  <div className="beacon-status-filter" role="group" aria-label="Filter beacons by status">
                    {beaconStatusFilters.map((item) => (
                      <button
                        aria-pressed={statusFilter === item}
                        className={statusFilter === item ? 'is-selected' : ''}
                        key={item}
                        onClick={() => setStatusFilter(item)}
                        type="button"
                      >
                        {statusFilterLabel(item)}
                      </button>
                    ))}
                  </div>
                  <button
                    aria-label="Toggle beacon sort direction"
                    className="beacon-sort-direction"
                    onClick={() => setSortDirection((current) => (current === 'asc' ? 'desc' : 'asc'))}
                    type="button"
                  >
                    <ArrowDownUp aria-hidden="true" size={14} strokeWidth={2} />
                    <span>{sortDirection === 'asc' ? 'Asc' : 'Desc'}</span>
                  </button>
                  <button
                    aria-label="Reset beacon sorting"
                    className="beacon-sort-reset"
                    onClick={handleResetSort}
                    title="Reset sorting"
                    type="button"
                  >
                    <RotateCcw aria-hidden="true" size={14} strokeWidth={2} />
                    <span>Reset</span>
                  </button>
                  <button
                    aria-label="Export visible beacons"
                    className="beacon-export-button"
                    disabled={beacons.length === 0}
                    onClick={handleExportCsv}
                    type="button"
                  >
                    <Download aria-hidden="true" size={14} strokeWidth={2} />
                    <span>CSV</span>
                  </button>
                  <span className="beacon-registry-count">
                    {beacons.length} / {visibleBeacons.length}
                  </span>
                </div>

                {beacons.length === 0 ? (
                  <div className="beacon-empty-state" data-testid="beacons-search-empty-state">
                    <Search aria-hidden="true" size={20} strokeWidth={2} />
                    <div>
                      <strong>No matching beacons.</strong>
                      <span>Clear or adjust the search query to return beacon rows.</span>
                    </div>
                  </div>
                ) : (
                  <div className="beacon-registry-wrap" data-testid="beacon-roster">
                    <table className="beacon-registry-table">
                      <thead>
                        <tr>
                          <th scope="col">
                            {renderSortHeader('hostname', 'Host')}
                          </th>
                          <th scope="col">
                            {renderSortHeader('os', 'Operating system')}
                          </th>
                          <th scope="col">
                            {renderSortHeader('internal_ip', 'Internal IP')}
                          </th>
                          <th scope="col">
                            {renderSortHeader('external_ip', 'External IP')}
                          </th>
                          <th scope="col">
                            <span className="table-head-label">PID / Arch</span>
                          </th>
                          <th scope="col">
                            {renderSortHeader('last_seen', 'Last Heartbeat')}
                          </th>
                          <th scope="col">
                            {renderSortHeader('transport_mode', 'Transport')}
                          </th>
                          <th scope="col">
                            {renderSortHeader('status', 'Status')}
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {beacons.map((beacon) => {
                          const selected = beacon.id === selectedBeacon?.id;
                          return (
                            <tr
                              aria-label={`Host ${beacon.hostname}`}
                              className={selected ? 'is-selected' : ''}
                              data-testid={`beacon-row-${beacon.id}`}
                              draggable
                              key={beacon.id}
                              onClick={() => setSelectedBeaconId(beacon.id)}
                              onDoubleClick={() => openBeaconOperations(beacon)}
                              onDragStart={(event) => writeBeaconDragData(event, beacon)}
                              onKeyDown={(event) => handleRowKeyDown(event, beacon)}
                              tabIndex={0}
                            >
                              <td>
                                <div className="beacon-host-cell">
                                  <strong>{beacon.hostname}</strong>
                                  <span>{beacon.machine_fingerprint_hash}</span>
                                </div>
                              </td>
                              <td>{beacon.os}</td>
                              <td>{beacon.internal_ip}</td>
                              <td>{beacon.external_ip ?? '-'}</td>
                              <td>
                                <span className="beacon-mono">
                                  {beacon.pid} / {beacon.architecture}
                                </span>
                              </td>
                              <td>
                                <span className="beacon-relative-time" data-testid={`beacon-relative-${beacon.id}`}>
                                  {formatRelativeTime(beacon.last_seen)}
                                </span>
                                <small className="beacon-absolute-time">{compactDateTime(beacon.last_seen)}</small>
                              </td>
                              <td>
                                <div className="beacon-transport-cell">
                                  <strong>{transportLabel(beacon.transport_mode)}</strong>
                                  <span className={statusClass(beacon.transport_connected ? 'online' : 'offline')}>
                                    {transportState(beacon)}
                                  </span>
                                </div>
                              </td>
                              <td>
                                <span className={statusClass(beacon.status)}>{beacon.status}</span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </section>

          <section className="workspace-panel beacon-detail-panel" aria-label="Beacon detail">
            <div className="panel-header">
              <div>
                <h2>{selectedBeacon?.hostname ?? 'No beacon selected'}</h2>
                <p className="muted-text">
                  {selectedBeacon ? 'Registration metadata captured during the latest check-in.' : 'Select a beacon to inspect metadata.'}
                </p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <Server size={18} strokeWidth={2} />
              </div>
            </div>
            {profileError ? <p className="task-queue-error" role="alert">{profileError}</p> : null}
            {profileMessage ? <p className="profile-status-message">{profileMessage}</p> : null}

            {selectedBeacon ? (
              <>
                <div className="beacon-identity-strip">
                  <div>
                    <ShieldCheck aria-hidden="true" size={17} strokeWidth={2} />
                    <span className={statusClass(selectedBeacon.status)}>{selectedBeacon.status}</span>
                  </div>
                  <strong>{selectedBeacon.id}</strong>
                </div>

                <div className="beacon-profile-panel">
                  <div>
                    <strong>Traffic profile</strong>
                    <span>
                      {selectedBeacon.profile_name
                        ? `${selectedBeacon.profile_name} / v${selectedBeacon.profile_version ?? '-'}`
                        : 'Default bootstrap'}
                    </span>
                  </div>
                  <label>
                    <span>Assignment</span>
                    <select
                      aria-label="Beacon traffic profile"
                      disabled={assigningProfile || isLoadingProfiles}
                      onChange={(event) => void handleAssignProfile(event.target.value)}
                      value={selectedBeacon.profile_id ?? ''}
                    >
                      <option value="">Default bootstrap</option>
                      {trafficProfiles.map((profile) => (
                        <option key={profile.id} value={profile.id}>
                          {profile.name} / v{profile.current_version}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button className="secondary-button" disabled={isLoadingProfiles} onClick={() => void loadTrafficProfiles()} type="button">
                    <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
                    <span>{isLoadingProfiles ? 'Loading' : 'Profiles'}</span>
                  </button>
                </div>

                <div className="beacon-detail-actions">
                  <button
                    className="danger-button"
                    onClick={() => {
                      setKillError('');
                      setKillTarget(selectedBeacon);
                    }}
                    type="button"
                  >
                    <Trash2 aria-hidden="true" size={15} strokeWidth={2.1} />
                    <span>Kill beacon</span>
                  </button>
                </div>

                <div className="beacon-tasking-panel">
                  <TaskExecutionPanel
                    beacons={visibleBeacons}
                    connection={connection}
                    initialArgs={routeModuleArgs}
                    initialBeaconId={selectedBeacon.id}
                    initialModuleId={routeModuleId || undefined}
                    initialTaskId={selectedBeacon.id === routeBeaconId ? routeTaskId : undefined}
                    latestEvent={realtime.latestEvent}
                    realtimeStatus={realtime.status}
                  />
                </div>

                <div className="beacon-detail-grid">
                  <DetailRow label="Hostname" value={selectedBeacon.hostname} />
                  <DetailRow label="Operating system" value={selectedBeacon.os} />
                  <DetailRow label="Architecture" value={selectedBeacon.architecture} />
                  <DetailRow label="Process ID" value={selectedBeacon.pid} />
                  <DetailRow
                    label="Protocol version"
                    testId="beacon-detail-protocol-version"
                    value={selectedBeacon.protocol_version ? `v${selectedBeacon.protocol_version}` : null}
                  />
                  <DetailRow
                    label="Transport"
                    testId="beacon-detail-transport-mode"
                    value={transportLabel(selectedBeacon.transport_mode)}
                  />
                  <DetailRow
                    label="Transport state"
                    testId="beacon-detail-transport-state"
                    value={transportState(selectedBeacon)}
                  />
                  <DetailRow label="Traffic profile" value={selectedBeacon.profile_name ?? 'Default bootstrap'} />
                  <DetailRow
                    label="Profile applied"
                    value={selectedBeacon.applied_profile_version ? `v${selectedBeacon.applied_profile_version}` : null}
                  />
                  <DetailRow
                    label="Sleep / jitter"
                    value={`${selectedBeacon.sleep_seconds ?? 30}s / ${Math.round((selectedBeacon.jitter ?? 0.1) * 100)}%`}
                  />
                  <DetailRow label="Internal IP" value={selectedBeacon.internal_ip} />
                  <DetailRow label="External IP" value={selectedBeacon.external_ip} />
                  <DetailRow label="First seen" value={formatDateTime(selectedBeacon.first_seen)} />
                  <DetailRow
                    label="Transport last seen"
                    value={selectedBeacon.transport_last_seen ? formatDateTime(selectedBeacon.transport_last_seen) : null}
                  />
                  <DetailRow label="Last heartbeat" value={formatRelativeTime(selectedBeacon.last_seen)} />
                  <DetailRow label="Last seen" value={formatDateTime(selectedBeacon.last_seen)} />
                </div>

                <div className="beacon-fingerprint-panel">
                  <div>
                    <Fingerprint aria-hidden="true" size={16} strokeWidth={2} />
                    <strong>Machine fingerprint</strong>
                  </div>
                  <span>{selectedBeacon.machine_fingerprint_hash}</span>
                </div>

                <div className="beacon-metadata-band">
                  <div>
                    <Network aria-hidden="true" size={16} strokeWidth={2} />
                    <span data-testid="beacon-detail-hostname">{selectedBeacon.hostname}</span>
                  </div>
                  <div>
                    <Cpu aria-hidden="true" size={16} strokeWidth={2} />
                    <span data-testid="beacon-detail-os">{selectedBeacon.os}</span>
                  </div>
                </div>

                <div className="beacon-activity-panel">
                  <div className="beacon-section-head">
                    <div>
                      <strong>Activity timeline</strong>
                      <span>Recent task, session, and lifecycle events.</span>
                    </div>
                    <button className="secondary-button" disabled={isLoadingActivity} onClick={() => void loadBeaconActivity()} type="button">
                      <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
                      <span>{isLoadingActivity ? 'Loading' : 'Refresh'}</span>
                    </button>
                  </div>
                  <BeaconActivityTimeline error={activityError} isLoading={isLoadingActivity} items={activityItems} />
                </div>
              </>
            ) : (
              <div className="beacon-empty-state beacon-empty-state--detail">
                <RadioTower aria-hidden="true" size={20} strokeWidth={2} />
                <div>
                  <strong>No beacon selected.</strong>
                  <span>Register a beacon through the C2 API to populate this panel.</span>
                </div>
              </div>
            )}
          </section>

          {operationBeacon ? (
            <BeaconOperationsModal
              beacon={operationBeacon}
              beacons={visibleBeacons}
              connection={connection}
              latestEvent={realtime.latestEvent}
              onClose={() => setOperationBeaconId('')}
              realtimeStatus={realtime.status}
            />
          ) : null}
          {killTarget ? (
            <KillBeaconModal
              beacon={killTarget}
              error={killError}
              isKilling={isKillingBeacon}
              onCancel={() => {
                if (!isKillingBeacon) {
                  setKillTarget(null);
                  setKillError('');
                }
              }}
              onConfirm={() => void handleConfirmKillBeacon()}
            />
          ) : null}
        </div>
      )}
    </AppShell>
  );
}
