import { FitAddon } from '@xterm/addon-fit';
import { Terminal } from '@xterm/xterm';
import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowDownUp,
  Boxes,
  Cpu,
  Crosshair,
  Download,
  FileArchive,
  FileText,
  Fingerprint,
  KeyRound,
  Network,
  RadioTower,
  RefreshCw,
  RotateCcw,
  Search,
  Send,
  Server,
  ShieldCheck,
  TerminalSquare,
  Trash2,
  X,
} from 'lucide-react';
import { createPortal } from 'react-dom';

import {
  cancelTask,
  closeShellSession,
  createShellSession,
  createShellTask,
  downloadTaskResultText,
  getTaskResult,
  getTasks,
} from '../api';
import type {
  Beacon,
  ShellSession,
  ShellType,
  Task,
  TaskPriority,
  TaskResult,
  TaskStatus,
} from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import type { C2Connection } from '../c2ConnectionContext';
import type { OperatorRealtimeEvent } from '../operatorRealtime';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';
import { ShellSessionClient } from '../shellSessionClient';
import type { ShellSessionConnectionStatus, ShellSessionMessage } from '../shellSessionClient';
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

const hostOperations = [
  {
    description: 'Prepare a scoped command or module task for this beacon.',
    icon: TerminalSquare,
    key: 'commands',
    label: 'Command queue',
    status: 'Planned',
  },
  {
    description: 'Attach to a live shell with streaming stdin and stdout.',
    icon: Crosshair,
    key: 'session',
    label: 'Interactive session',
    status: 'Ready',
  },
  {
    description: 'Inspect host files, collected artifacts, and secured output.',
    icon: FileArchive,
    key: 'files',
    label: 'Files & artifacts',
    status: 'Planned',
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

const taskPriorities: TaskPriority[] = ['low', 'normal', 'high', 'urgent'];
const shellTypes: ShellType[] = ['auto', 'cmd', 'powershell', 'bash'];
const taskStatusFilters: Array<TaskStatus | 'all'> = ['all', 'queued', 'dispatched', 'running', 'completed', 'failed', 'cancelled'];

function taskStatusLabel(status: string): string {
  return status.replace(/-/g, ' ');
}

function taskCommand(task: Task): string {
  const command = task.args.command;
  return typeof command === 'string' ? command : task.module;
}

function taskMeta(task: Task): string {
  const timeout = task.args.timeout_seconds;
  const shellType = task.args.shell_type;
  const shell = typeof shellType === 'string' ? shellType : 'auto';
  const timeoutLabel = typeof timeout === 'number' ? `${timeout}s` : 'default';
  return `${shell} / ${task.priority} / ${timeoutLabel}`;
}

function taskLifecycleTime(task: Task): string {
  const timestamp = task.completed_at ?? task.cancelled_at ?? task.running_at ?? task.dispatched_at ?? task.queued_at;
  return `${taskStatusLabel(task.status)} ${formatRelativeTime(timestamp)}`;
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

function resultOutput(result: TaskResult, stream: 'stderr' | 'stdout'): string {
  const value = result[stream];
  return typeof value === 'string' && value.length > 0 ? value : '(empty)';
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
    if (message.session) {
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

function BeaconOperationsModal({
  beacon,
  connection,
  latestEvent,
  onClose,
}: {
  beacon: Beacon;
  connection: C2Connection;
  latestEvent: OperatorRealtimeEvent | null;
  onClose: () => void;
}) {
  const [selectedOperation, setSelectedOperation] = useState<HostOperationKey>('commands');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [command, setCommand] = useState('');
  const [shellType, setShellType] = useState<ShellType>('auto');
  const [priority, setPriority] = useState<TaskPriority>('normal');
  const [timeoutSeconds, setTimeoutSeconds] = useState('60');
  const [taskSearchQuery, setTaskSearchQuery] = useState('');
  const [taskStatusFilter, setTaskStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [taskError, setTaskError] = useState('');
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [isSubmittingTask, setIsSubmittingTask] = useState(false);
  const [cancellingTaskId, setCancellingTaskId] = useState('');
  const [selectedResultTaskId, setSelectedResultTaskId] = useState('');
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null);
  const [taskResultStream, setTaskResultStream] = useState<'stderr' | 'stdout'>('stdout');
  const [taskResultError, setTaskResultError] = useState('');
  const [isLoadingTaskResult, setIsLoadingTaskResult] = useState(false);
  const [downloadingResultStream, setDownloadingResultStream] = useState('');
  const activeOperation = hostOperations.find((operation) => operation.key === selectedOperation) ?? hostOperations[0];
  const ActiveIcon = activeOperation.icon;
  const queuedTaskCount = tasks.filter((task) => task.status === 'queued').length;

  const loadTasks = useCallback(async () => {
    setIsLoadingTasks(true);
    try {
      const commandFilter = taskSearchQuery.trim();
      const response = await getTasks(connection.baseUrl, connection.accessToken, {
        beaconId: beacon.id,
        command: commandFilter || undefined,
        limit: 20,
        status: taskStatusFilter === 'all' ? undefined : taskStatusFilter,
      });
      setTasks(response.items);
      setTaskError('');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to load task history.';
      setTaskError(message);
    } finally {
      setIsLoadingTasks(false);
    }
  }, [beacon.id, connection.accessToken, connection.baseUrl, taskSearchQuery, taskStatusFilter]);

  const loadTaskResult = useCallback(async (taskId: string) => {
    setSelectedResultTaskId(taskId);
    setIsLoadingTaskResult(true);
    try {
      const result = await getTaskResult(connection.baseUrl, connection.accessToken, taskId);
      setTaskResult(result);
      setTaskResultError('');
      setTaskResultStream(result.stdout_size_bytes > 0 || result.stderr_size_bytes === 0 ? 'stdout' : 'stderr');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to load task result.';
      setTaskResult(null);
      setTaskResultError(message);
    } finally {
      setIsLoadingTaskResult(false);
    }
  }, [connection.accessToken, connection.baseUrl]);

  useEffect(() => {
    const handle = window.setTimeout(() => void loadTasks(), 0);
    return () => window.clearTimeout(handle);
  }, [loadTasks]);

  useEffect(() => {
    if (!latestEvent?.type.startsWith('task.')) {
      return;
    }
    if (latestEvent.scope.beacon_id && latestEvent.scope.beacon_id !== beacon.id) {
      return;
    }
    const handle = window.setTimeout(() => void loadTasks(), 0);
    return () => window.clearTimeout(handle);
  }, [beacon.id, latestEvent?.id, latestEvent?.scope.beacon_id, latestEvent?.type, loadTasks]);

  useEffect(() => {
    if (latestEvent?.type !== 'task.result.completed' || !selectedResultTaskId) {
      return;
    }
    if (latestEvent.scope.task_id && latestEvent.scope.task_id !== selectedResultTaskId) {
      return;
    }
    const handle = window.setTimeout(() => void loadTaskResult(selectedResultTaskId), 0);
    return () => window.clearTimeout(handle);
  }, [latestEvent?.id, latestEvent?.scope.task_id, latestEvent?.type, loadTaskResult, selectedResultTaskId]);

  async function handleSubmitTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedCommand = command.trim();
    const parsedTimeout = Number(timeoutSeconds);
    if (!trimmedCommand) {
      setTaskError('Command is required.');
      return;
    }
    if (!Number.isInteger(parsedTimeout) || parsedTimeout < 1) {
      setTaskError('Timeout must be a positive whole number.');
      return;
    }
    setIsSubmittingTask(true);
    try {
      await createShellTask(
        connection.baseUrl,
        connection.accessToken,
        beacon.id,
        { command: trimmedCommand, shell_type: shellType, timeout_seconds: parsedTimeout },
        priority,
      );
      setCommand('');
      setTaskError('');
      await loadTasks();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to queue task.';
      setTaskError(message);
    } finally {
      setIsSubmittingTask(false);
    }
  }

  async function handleCancelTask(task: Task) {
    setCancellingTaskId(task.id);
    try {
      const cancelled = await cancelTask(connection.baseUrl, connection.accessToken, task.id);
      setTasks((current) => current.map((item) => (item.id === cancelled.id ? cancelled : item)));
      setTaskError('');
      await loadTasks();
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to cancel task.';
      setTaskError(message);
    } finally {
      setCancellingTaskId('');
    }
  }

  async function handleDownloadResult(stream: 'combined' | 'stderr' | 'stdout') {
    if (!selectedResultTaskId) {
      return;
    }
    setDownloadingResultStream(stream);
    try {
      const blob = await downloadTaskResultText(connection.baseUrl, connection.accessToken, selectedResultTaskId, stream);
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = href;
      anchor.download = `${selectedResultTaskId}-${stream}.txt`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(href);
      setTaskResultError('');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to download task result.';
      setTaskResultError(message);
    } finally {
      setDownloadingResultStream('');
    }
  }

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
              <div className="task-queue-panel">
                <form className="task-command-form" onSubmit={handleSubmitTask}>
                  <label>
                    <span>Command</span>
                    <input
                      aria-label="Shell command"
                      onChange={(event) => setCommand(event.target.value)}
                      placeholder="whoami"
                      value={command}
                    />
                  </label>
                  <div className="task-command-grid">
                    <label>
                      <span>Shell</span>
                      <select
                        aria-label="Shell type"
                        onChange={(event) => setShellType(event.target.value as ShellType)}
                        value={shellType}
                      >
                        {shellTypes.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Priority</span>
                      <select
                        aria-label="Task priority"
                        onChange={(event) => setPriority(event.target.value as TaskPriority)}
                        value={priority}
                      >
                        {taskPriorities.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Timeout</span>
                      <input
                        aria-label="Timeout seconds"
                        min={1}
                        onChange={(event) => setTimeoutSeconds(event.target.value)}
                        type="number"
                        value={timeoutSeconds}
                      />
                    </label>
                    <button className="primary-button task-submit-button" disabled={isSubmittingTask} type="submit">
                      <Send aria-hidden="true" size={15} strokeWidth={2.2} />
                      <span>{isSubmittingTask ? 'Queueing' : 'Queue'}</span>
                    </button>
                  </div>
                </form>

                <div className="task-queue-toolbar">
                  <div className="task-history-count">
                    <strong>{queuedTaskCount}</strong>
                    <span>queued</span>
                  </div>
                  <label className="task-history-search">
                    <Search aria-hidden="true" size={14} strokeWidth={2} />
                    <input
                      aria-label="Search command history"
                      onChange={(event) => setTaskSearchQuery(event.target.value)}
                      placeholder="Search commands"
                      value={taskSearchQuery}
                    />
                  </label>
                  <select
                    aria-label="Filter task status"
                    className="task-status-filter"
                    onChange={(event) => setTaskStatusFilter(event.target.value as TaskStatus | 'all')}
                    value={taskStatusFilter}
                  >
                    {taskStatusFilters.map((item) => (
                      <option key={item} value={item}>
                        {item === 'all' ? 'All statuses' : taskStatusLabel(item)}
                      </option>
                    ))}
                  </select>
                  <button className="secondary-button" onClick={() => void loadTasks()} type="button">
                    <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
                    <span>Refresh</span>
                  </button>
                </div>

                {taskError ? <p className="task-queue-error" role="alert">{taskError}</p> : null}

                <div className="task-list" data-testid="beacon-task-list">
                  {isLoadingTasks ? (
                    <div className="task-empty-state">Loading task history.</div>
                  ) : tasks.length === 0 ? (
                    <div className="task-empty-state">No tasks queued for this beacon.</div>
                  ) : (
                    tasks.map((task) => (
                      <div className="task-row" key={task.id}>
                        <div>
                          <strong>{taskCommand(task)}</strong>
                          <span>{taskMeta(task)}</span>
                          <span>{taskLifecycleTime(task)}</span>
                        </div>
                        <div>
                          <span className={`task-status task-status--${task.status}`}>{taskStatusLabel(task.status)}</span>
                          {task.status === 'completed' || task.status === 'failed' ? (
                            <button
                              aria-label={`View result for ${taskCommand(task)}`}
                              className="task-result-button"
                              onClick={() => void loadTaskResult(task.id)}
                              type="button"
                            >
                              <FileText aria-hidden="true" size={14} strokeWidth={2.1} />
                            </button>
                          ) : null}
                          {task.status === 'queued' ? (
                            <button
                              aria-label={`Cancel task ${taskCommand(task)}`}
                              className="task-cancel-button"
                              disabled={cancellingTaskId === task.id}
                              onClick={() => void handleCancelTask(task)}
                              type="button"
                            >
                              <Trash2 aria-hidden="true" size={14} strokeWidth={2.1} />
                            </button>
                          ) : null}
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {selectedResultTaskId ? (
                  <div className="task-result-panel" data-testid="task-result-panel">
                    <div className="task-result-panel-head">
                      <div>
                        <strong>Task result</strong>
                        <span>{selectedResultTaskId}</span>
                      </div>
                      <button
                        aria-label="Download combined result"
                        className="secondary-button task-result-download"
                        disabled={!taskResult || downloadingResultStream === 'combined'}
                        onClick={() => void handleDownloadResult('combined')}
                        type="button"
                      >
                        <Download aria-hidden="true" size={14} strokeWidth={2.1} />
                        <span>{downloadingResultStream === 'combined' ? 'Downloading' : 'Download'}</span>
                      </button>
                    </div>

                    {isLoadingTaskResult ? (
                      <div className="task-empty-state">Loading task result.</div>
                    ) : taskResult ? (
                      <>
                        <div className="task-result-meta">
                          <span>Status {taskResult.status}</span>
                          <span>Exit {taskResult.exit_code ?? '-'}</span>
                          <span>{formatBytes(taskResult.output_size_bytes)}</span>
                          <span>Retained {formatRelativeTime(taskResult.expires_at)}</span>
                        </div>
                        <div className="task-result-tabs" role="tablist" aria-label="Task result streams">
                          {(['stdout', 'stderr'] as const).map((stream) => (
                            <button
                              aria-selected={taskResultStream === stream}
                              className={taskResultStream === stream ? 'is-selected' : ''}
                              key={stream}
                              onClick={() => setTaskResultStream(stream)}
                              role="tab"
                              type="button"
                            >
                              {stream}
                              <span>{formatBytes(stream === 'stdout' ? taskResult.stdout_size_bytes : taskResult.stderr_size_bytes)}</span>
                            </button>
                          ))}
                        </div>
                        <pre className="task-result-output">{resultOutput(taskResult, taskResultStream)}</pre>
                      </>
                    ) : (
                      <div className="task-empty-state">No durable result is available for this task.</div>
                    )}
                    {taskResultError ? <p className="task-queue-error" role="alert">{taskResultError}</p> : null}
                  </div>
                ) : null}
              </div>
            ) : activeOperation.key === 'session' ? (
              <ShellSessionPanel beacon={beacon} connection={connection} />
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
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedBeaconId, setSelectedBeaconId] = useState('');
  const [operationBeaconId, setOperationBeaconId] = useState('');
  const [sortKey, setSortKey] = useState<BeaconSortKey>(DEFAULT_BEACON_SORT_KEY);
  const [sortDirection, setSortDirection] = useState<BeaconSortDirection>(DEFAULT_BEACON_SORT_DIRECTION);
  const beacons = useMemo(
    () => sortBeacons(realtime.beacons.filter((beacon) => searchBeacon(beacon, searchQuery.trim())), sortKey, sortDirection),
    [realtime.beacons, searchQuery, sortDirection, sortKey],
  );
  const selectedBeacon = beacons.find((beacon) => beacon.id === selectedBeaconId) ?? beacons[0] ?? null;
  const operationBeacon = beacons.find((beacon) => beacon.id === operationBeaconId) ?? null;
  const activeBeaconCount = realtime.beacons.filter((beacon) => beacon.status.toLowerCase() === 'online').length;
  const offlineBeaconCount = realtime.beacons.filter((beacon) => beacon.status.toLowerCase() === 'offline').length;

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
                <strong>{realtime.beacons.length}</strong>
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

            {realtime.beacons.length === 0 ? (
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
                  <span className="beacon-registry-count">
                    {beacons.length} / {realtime.beacons.length}
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
                              key={beacon.id}
                              onClick={() => setSelectedBeaconId(beacon.id)}
                              onDoubleClick={() => openBeaconOperations(beacon)}
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

            {selectedBeacon ? (
              <>
                <div className="beacon-identity-strip">
                  <div>
                    <ShieldCheck aria-hidden="true" size={17} strokeWidth={2} />
                    <span className={statusClass(selectedBeacon.status)}>{selectedBeacon.status}</span>
                  </div>
                  <strong>{selectedBeacon.id}</strong>
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
              connection={connection}
              latestEvent={realtime.latestEvent}
              onClose={() => setOperationBeaconId('')}
            />
          ) : null}
        </div>
      )}
    </AppShell>
  );
}
