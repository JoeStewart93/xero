import { DragEvent, FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import {
  Download,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  Send,
  Target,
  Trash2,
} from 'lucide-react';

import {
  cancelTask,
  createTask,
  downloadTaskResultText,
  getModules,
  getTaskResult,
  getTasks,
} from '../api';
import type {
  Beacon,
  ModuleDefinition,
  Task,
  TaskPriority,
  TaskResult,
  TaskStatus,
} from '../api';
import { StreamOutput } from '../components/StreamOutput';
import type { C2Connection } from '../c2ConnectionContext';
import { argsStateFromRecord, fieldAriaLabel, fieldLabel, initialModuleArgs, schemaFields, schemaType } from '../modules/moduleCatalog';
import type { ArgsState } from '../modules/moduleCatalog';
import type { OperatorRealtimeEvent, RealtimeStatus } from '../operatorRealtime';
import { taskResultFromRealtimeEvent } from '../operatorRealtime';
import type { TaskResultStreamBuffer } from '../taskResultStreams';
import { useTaskResultStreams } from '../taskResultStreams';
import { compactDateTime, formatRelativeTime } from './beaconDisplay';
import { BEACON_DRAG_MIME } from './taskDrag';

const taskPriorities: TaskPriority[] = ['low', 'normal', 'high', 'urgent'];
const taskStatusFilters: Array<TaskStatus | 'all'> = ['all', 'queued', 'dispatched', 'running', 'completed', 'failed', 'cancelled'];

type FieldErrors = Record<string, string>;
type ResultStream = 'stderr' | 'stdout';

interface TaskExecutionPanelProps {
  beacons: Beacon[];
  connection: C2Connection;
  initialArgs?: Record<string, unknown>;
  initialBeaconId?: string;
  initialModuleId?: string;
  initialTaskId?: string;
  labelPrefix?: string;
  latestEvent: OperatorRealtimeEvent | null;
  lockTargetBeacon?: boolean;
  realtimeStatus?: RealtimeStatus;
  testIdPrefix?: string;
  title?: string;
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

function taskStatusLabel(status: string): string {
  return status.replace(/-/g, ' ');
}

function taskCommand(task: Task): string {
  const command = task.args.command;
  return typeof command === 'string' ? command : task.module;
}

function taskMeta(task: Task, beaconLabel: string): string {
  const timeout = task.args.timeout_seconds;
  const shellType = task.args.shell_type;
  const shell = typeof shellType === 'string' ? shellType : 'auto';
  const timeoutLabel = typeof timeout === 'number' ? `${timeout}s` : 'default';
  return `${beaconLabel} / ${task.module} / ${shell} / ${task.priority} / ${timeoutLabel}`;
}

function taskLifecycleTime(task: Task): string {
  const timestamp = task.completed_at ?? task.cancelled_at ?? task.running_at ?? task.dispatched_at ?? task.queued_at;
  return `${taskStatusLabel(task.status)} ${formatRelativeTime(timestamp)}`;
}

function resultOutput(result: TaskResult, stream: ResultStream): string {
  const value = result[stream];
  return typeof value === 'string' && value.length > 0 ? value : '(empty)';
}

function isTerminalStatus(status: TaskStatus): boolean {
  return status === 'completed' || status === 'failed';
}

function isBusyStatus(status: TaskStatus): boolean {
  return status === 'dispatched' || status === 'running';
}

function validateArgs(module: ModuleDefinition | null, args: ArgsState): FieldErrors {
  if (!module) {
    return {};
  }
  const errors: FieldErrors = {};
  for (const field of schemaFields(module)) {
    const raw = args[field.key] ?? '';
    const value = raw.trim();
    const type = schemaType(field.schema);
    if (field.isRequired && !value) {
      errors[field.key] = `${fieldLabel(field.key)} is required.`;
      continue;
    }
    if (!value) {
      continue;
    }
    if (type === 'integer' || type === 'number') {
      const parsed = Number(value);
      if (!Number.isFinite(parsed) || (type === 'integer' && !Number.isInteger(parsed))) {
        errors[field.key] = `${fieldLabel(field.key)} must be a ${type}.`;
        continue;
      }
      if (typeof field.schema.minimum === 'number' && parsed < field.schema.minimum) {
        errors[field.key] = `${fieldLabel(field.key)} must be at least ${field.schema.minimum}.`;
      }
      if (typeof field.schema.maximum === 'number' && parsed > field.schema.maximum) {
        errors[field.key] = `${fieldLabel(field.key)} must be at most ${field.schema.maximum}.`;
      }
    }
  }
  return errors;
}

function buildArgs(module: ModuleDefinition, args: ArgsState): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const field of schemaFields(module)) {
    const value = (args[field.key] ?? '').trim();
    if (!value && !field.isRequired) {
      continue;
    }
    const type = schemaType(field.schema);
    payload[field.key] = type === 'integer' || type === 'number' ? Number(value) : value;
  }
  return payload;
}

function readBeaconId(event: DragEvent<HTMLElement>): string {
  return event.dataTransfer.getData(BEACON_DRAG_MIME) || event.dataTransfer.getData('text/plain');
}

function ModulePicker({
  isLoading,
  modules,
  onChange,
  selectedModuleId,
}: {
  isLoading: boolean;
  modules: ModuleDefinition[];
  onChange: (moduleId: string) => void;
  selectedModuleId: string;
}) {
  return (
    <label>
      <span>Module</span>
      <select
        aria-label="Task module"
        disabled={isLoading || modules.length === 0}
        onChange={(event) => onChange(event.target.value)}
        value={selectedModuleId}
      >
        {modules.length === 0 ? <option value="">No beacon task modules</option> : null}
        {modules.map((module) => (
          <option key={module.id} value={module.id}>
            {module.name}
          </option>
        ))}
      </select>
    </label>
  );
}

function ModuleArgsForm({
  args,
  errors,
  labelPrefix,
  module,
  onChange,
}: {
  args: ArgsState;
  errors: FieldErrors;
  labelPrefix?: string;
  module: ModuleDefinition | null;
  onChange: (field: string, value: string) => void;
}) {
  if (!module) {
    return <div className="task-empty-state">No beacon task module is available.</div>;
  }

  return (
    <>
      {schemaFields(module).map((field) => {
        const type = schemaType(field.schema);
        const enumValues = Array.isArray(field.schema.enum)
          ? field.schema.enum.filter((item): item is string => typeof item === 'string')
          : [];
        const error = errors[field.key];
        if (!['integer', 'number', 'string'].includes(type)) {
          return (
            <div className="task-schema-unsupported" key={field.key}>
              {fieldLabel(field.key)} is not editable in this task form.
            </div>
          );
        }
        return (
          <label key={field.key}>
            <span>{fieldLabel(field.key)}{field.isRequired ? ' *' : ''}</span>
            {enumValues.length > 0 ? (
              <select
                aria-invalid={Boolean(error)}
                aria-label={fieldAriaLabel(field.key, labelPrefix)}
                onChange={(event) => onChange(field.key, event.target.value)}
                value={args[field.key] ?? ''}
              >
                {enumValues.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            ) : (
              <input
                aria-invalid={Boolean(error)}
                aria-label={fieldAriaLabel(field.key, labelPrefix)}
                min={typeof field.schema.minimum === 'number' ? field.schema.minimum : undefined}
                onChange={(event) => onChange(field.key, event.target.value)}
                placeholder={field.key === 'command' ? 'whoami' : undefined}
                type={type === 'integer' || type === 'number' ? 'number' : 'text'}
                value={args[field.key] ?? ''}
              />
            )}
            {error ? <small className="task-field-error">{error}</small> : null}
          </label>
        );
      })}
    </>
  );
}

function BeaconTargetField({
  beacons,
  dragError,
  isDraggingOver,
  isLocked,
  onDragLeave,
  onDragOver,
  onDrop,
  onTargetChange,
  selectedBeacon,
  targetBeaconId,
}: {
  beacons: Beacon[];
  dragError: string;
  isDraggingOver: boolean;
  isLocked: boolean;
  onDragLeave: () => void;
  onDragOver: (event: DragEvent<HTMLDivElement>) => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onTargetChange: (beaconId: string) => void;
  selectedBeacon: Beacon | null;
  targetBeaconId: string;
}) {
  return (
    <div
      aria-label="Beacon task drop target"
      className={`beacon-task-target ${isDraggingOver ? 'is-dragging' : ''} ${dragError ? 'is-invalid' : ''} ${isLocked ? 'is-locked' : ''}`}
      data-testid="beacon-task-drop-target"
      onDragLeave={onDragLeave}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      {isLocked ? (
        <div className="beacon-task-target-lock" aria-label="Target beacon">
          <span>Target beacon</span>
          <strong>{selectedBeacon ? `${selectedBeacon.hostname} / ${selectedBeacon.internal_ip}` : targetBeaconId || 'No beacon targeted'}</strong>
        </div>
      ) : (
        <label>
          <span>Target beacon</span>
          <select
            aria-label="Target beacon"
            onChange={(event) => onTargetChange(event.target.value)}
            value={targetBeaconId}
          >
            <option value="">Select beacon</option>
            {beacons.map((beacon) => (
              <option key={beacon.id} value={beacon.id}>
                {beacon.hostname} / {beacon.internal_ip}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="beacon-task-target-chip" data-testid="beacon-task-target-chip">
        <Target aria-hidden="true" size={15} strokeWidth={2.1} />
        <span>{selectedBeacon ? `${selectedBeacon.hostname} / ${selectedBeacon.status}` : 'No beacon targeted'}</span>
      </div>
      {dragError ? <p className="task-queue-error" role="alert">{dragError}</p> : null}
    </div>
  );
}

function TaskList({
  beaconLabel,
  cancellingTaskId,
  isLoading,
  onCancel,
  onSelect,
  selectedTaskId,
  tasks,
}: {
  beaconLabel: (beaconId: string) => string;
  cancellingTaskId: string;
  isLoading: boolean;
  onCancel: (task: Task) => void;
  onSelect: (task: Task) => void;
  selectedTaskId: string;
  tasks: Task[];
}) {
  if (isLoading) {
    return <div className="task-empty-state">Loading task history.</div>;
  }
  if (tasks.length === 0) {
    return <div className="task-empty-state">No tasks queued for this beacon.</div>;
  }
  return (
    <>
      {tasks.map((task) => (
        <div
          className={`task-row ${selectedTaskId === task.id ? 'is-selected' : ''}`}
          data-testid={`task-row-${task.id}`}
          key={task.id}
          onClick={() => onSelect(task)}
          role="button"
          tabIndex={0}
        >
          <div>
            <strong>{taskCommand(task)}</strong>
            <span>{taskMeta(task, beaconLabel(task.beacon_id))}</span>
            <span>Created {compactDateTime(task.created_at)}</span>
            <span>{taskLifecycleTime(task)}</span>
          </div>
          <div>
            {isBusyStatus(task.status) ? (
              <Loader2 aria-label={`${taskStatusLabel(task.status)} task`} className="task-status-spinner" size={14} strokeWidth={2.1} />
            ) : null}
            <span className={`task-status task-status--${task.status}`}>{taskStatusLabel(task.status)}</span>
            {isTerminalStatus(task.status) ? (
              <button
                aria-label={`View result for ${taskCommand(task)}`}
                className="task-result-button"
                onClick={(event) => {
                  event.stopPropagation();
                  onSelect(task);
                }}
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
                onClick={(event) => {
                  event.stopPropagation();
                  onCancel(task);
                }}
                type="button"
              >
                <Trash2 aria-hidden="true" size={14} strokeWidth={2.1} />
              </button>
            ) : null}
          </div>
        </div>
      ))}
    </>
  );
}

function TaskDetailPanel({
  downloadingResultStream,
  isLoadingTaskResult,
  onDownloadResult,
  onClearStream,
  result,
  resultError,
  resultStream,
  selectedTask,
  setResultStream,
  streamBuffer,
}: {
  downloadingResultStream: string;
  isLoadingTaskResult: boolean;
  onDownloadResult: (stream: 'combined' | ResultStream) => void;
  onClearStream: () => void;
  result: TaskResult | null;
  resultError: string;
  resultStream: ResultStream;
  selectedTask: Task | null;
  setResultStream: (stream: ResultStream) => void;
  streamBuffer: TaskResultStreamBuffer | null;
}) {
  if (!selectedTask) {
    return null;
  }
  const allLiveChunks = streamBuffer?.chunks ?? [];
  const liveChunks = allLiveChunks.filter((chunk) => chunk.stream === resultStream);
  const showLiveOutput = allLiveChunks.length > 0 || isBusyStatus(selectedTask.status);
  return (
    <div className="task-result-panel" data-testid="task-result-panel">
      <div className="task-result-panel-head">
        <div>
          <strong>Task detail</strong>
          <span>{selectedTask.id}</span>
        </div>
        <button
          aria-label="Download combined result"
          className="secondary-button task-result-download"
          disabled={!result || downloadingResultStream === 'combined'}
          onClick={() => onDownloadResult('combined')}
          type="button"
        >
          <Download aria-hidden="true" size={14} strokeWidth={2.1} />
          <span>{downloadingResultStream === 'combined' ? 'Downloading' : 'Download'}</span>
        </button>
      </div>

      {showLiveOutput ? (
        <>
          <div className="task-result-tabs" role="tablist" aria-label="Live task result streams">
            {(['stdout', 'stderr'] as const).map((stream) => (
              <button
                aria-selected={resultStream === stream}
                className={resultStream === stream ? 'is-selected' : ''}
                key={stream}
                onClick={() => setResultStream(stream)}
                role="tab"
                type="button"
              >
                {stream}
                <span>{allLiveChunks.filter((chunk) => chunk.stream === stream).length} chunks</span>
              </button>
            ))}
          </div>
          <StreamOutput
            chunks={liveChunks}
            isComplete={Boolean(streamBuffer?.isComplete || isTerminalStatus(selectedTask.status))}
            onClear={onClearStream}
            stream={resultStream}
          />
        </>
      ) : null}

      {isLoadingTaskResult ? (
        <div className="task-empty-state">Loading task result.</div>
      ) : result ? (
        <>
          <div className="task-result-meta">
            <span>Status {result.status}</span>
            <span>Exit {result.exit_code ?? '-'}</span>
            <span>{formatBytes(result.output_size_bytes)}</span>
            <span>Retained {formatRelativeTime(result.expires_at)}</span>
          </div>
          {result.status === 'failed' && result.error_message ? (
            <p className="task-failure-reason" data-testid="task-failure-reason">{result.error_message}</p>
          ) : null}
          <div className="task-result-tabs" role="tablist" aria-label="Task result streams">
            {(['stdout', 'stderr'] as const).map((stream) => (
              <button
                aria-selected={resultStream === stream}
                className={resultStream === stream ? 'is-selected' : ''}
                key={stream}
                onClick={() => setResultStream(stream)}
                role="tab"
                type="button"
              >
                {stream}
                <span>{formatBytes(stream === 'stdout' ? result.stdout_size_bytes : result.stderr_size_bytes)}</span>
              </button>
            ))}
          </div>
          <pre className="task-result-output">{resultOutput(result, resultStream)}</pre>
        </>
      ) : isBusyStatus(selectedTask.status) ? (
        <div className="task-empty-state task-running-state">
          <Loader2 aria-hidden="true" className="task-status-spinner" size={15} strokeWidth={2.1} />
          <span>{taskStatusLabel(selectedTask.status)} task is waiting for durable output.</span>
        </div>
      ) : selectedTask.status === 'failed' ? (
        <div className="task-empty-state">Failed task result has not been retained yet.</div>
      ) : (
        <div className="task-empty-state">No durable result is available for this task.</div>
      )}
      {resultError ? <p className="task-queue-error" role="alert">{resultError}</p> : null}
    </div>
  );
}

export function TaskExecutionPanel({
  beacons,
  connection,
  initialArgs,
  initialBeaconId,
  initialModuleId,
  initialTaskId,
  labelPrefix,
  latestEvent,
  lockTargetBeacon = false,
  realtimeStatus,
  testIdPrefix = '',
  title = 'Task execution',
}: TaskExecutionPanelProps) {
  const [modules, setModules] = useState<ModuleDefinition[]>([]);
  const [moduleId, setModuleId] = useState('');
  const [args, setArgs] = useState<ArgsState>({});
  const [priority, setPriority] = useState<TaskPriority>('normal');
  const [targetBeaconId, setTargetBeaconId] = useState(initialBeaconId ?? '');
  const [tasks, setTasks] = useState<Task[]>([]);
  const [taskSearchQuery, setTaskSearchQuery] = useState('');
  const [taskStatusFilter, setTaskStatusFilter] = useState<TaskStatus | 'all'>('all');
  const [taskError, setTaskError] = useState('');
  const [moduleError, setModuleError] = useState('');
  const [isLoadingModules, setIsLoadingModules] = useState(false);
  const [isLoadingTasks, setIsLoadingTasks] = useState(false);
  const [isSubmittingTask, setIsSubmittingTask] = useState(false);
  const [cancellingTaskId, setCancellingTaskId] = useState('');
  const [selectedTaskId, setSelectedTaskId] = useState(initialTaskId ?? '');
  const [taskResult, setTaskResult] = useState<TaskResult | null>(null);
  const [taskResultStream, setTaskResultStream] = useState<ResultStream>('stdout');
  const [taskResultError, setTaskResultError] = useState('');
  const [isLoadingTaskResult, setIsLoadingTaskResult] = useState(false);
  const [downloadingResultStream, setDownloadingResultStream] = useState('');
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [dragError, setDragError] = useState('');

  const taskModules = useMemo(
    () => modules.filter((module) => module.execution_kind === 'beacon-task' && module.supported_execution_targets.includes('beacon')),
    [modules],
  );
  const selectedModule = taskModules.find((module) => module.id === moduleId) ?? null;
  const selectedBeacon = beacons.find((beacon) => beacon.id === targetBeaconId) ?? null;
  const selectedTask = tasks.find((task) => task.id === selectedTaskId) ?? null;
  const queuedTaskCount = tasks.filter((task) => task.status === 'queued').length;
  const fieldErrors = useMemo(() => validateArgs(selectedModule, args), [args, selectedModule]);
  const canSubmit = Boolean(selectedModule && selectedBeacon && Object.keys(fieldErrors).length === 0);
  const streamTaskIds = useMemo(() => (
    Array.from(new Set(tasks
      .filter((task) => isBusyStatus(task.status) || isTerminalStatus(task.status) || task.id === selectedTaskId)
      .map((task) => task.id)))
  ), [selectedTaskId, tasks]);
  const {
    backfillTask,
    clearTaskStream,
    streamForTask,
  } = useTaskResultStreams({
    activeTaskIds: streamTaskIds,
    connection,
    latestEvent,
    realtimeStatus,
  });

  const beaconLabel = useCallback((beaconId: string) => {
    const beacon = beacons.find((item) => item.id === beaconId);
    return beacon ? beacon.hostname : beaconId.slice(0, 8);
  }, [beacons]);

  const loadModules = useCallback(async () => {
    setIsLoadingModules(true);
    try {
      const response = await getModules(connection.baseUrl, connection.accessToken);
      setModules(response.items);
      setModuleError('');
    } catch (caught) {
      setModuleError(caught instanceof Error ? caught.message : 'Unable to load modules.');
    } finally {
      setIsLoadingModules(false);
    }
  }, [connection.accessToken, connection.baseUrl]);

  const loadTasks = useCallback(async () => {
    if (!targetBeaconId) {
      setTasks([]);
      return;
    }
    setIsLoadingTasks(true);
    try {
      const commandFilter = taskSearchQuery.trim();
      const response = await getTasks(connection.baseUrl, connection.accessToken, {
        beaconId: targetBeaconId,
        command: commandFilter || undefined,
        limit: 20,
        status: taskStatusFilter === 'all' ? undefined : taskStatusFilter,
      });
      setTasks(response.items);
      setTaskError('');
    } catch (caught) {
      setTaskError(caught instanceof Error ? caught.message : 'Unable to load task history.');
    } finally {
      setIsLoadingTasks(false);
    }
  }, [connection.accessToken, connection.baseUrl, targetBeaconId, taskSearchQuery, taskStatusFilter]);

  const loadTaskResult = useCallback(async (taskId: string) => {
    setIsLoadingTaskResult(true);
    try {
      const result = await getTaskResult(connection.baseUrl, connection.accessToken, taskId);
      setTaskResult(result);
      setTaskResultError('');
      setTaskResultStream(result.stdout_size_bytes > 0 || result.stderr_size_bytes === 0 ? 'stdout' : 'stderr');
    } catch (caught) {
      setTaskResult(null);
      setTaskResultError(caught instanceof Error ? caught.message : 'Unable to load task result.');
    } finally {
      setIsLoadingTaskResult(false);
    }
  }, [connection.accessToken, connection.baseUrl]);

  useEffect(() => {
    const handle = window.setTimeout(() => void loadModules(), 0);
    return () => window.clearTimeout(handle);
  }, [loadModules]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (initialBeaconId) {
        setTargetBeaconId(initialBeaconId);
      }
    }, 0);
    return () => window.clearTimeout(handle);
  }, [initialBeaconId]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (initialTaskId) {
        setSelectedTaskId(initialTaskId);
        void backfillTask(initialTaskId).catch(() => undefined);
      }
    }, 0);
    return () => window.clearTimeout(handle);
  }, [backfillTask, initialTaskId]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const requestedModule = initialModuleId ? taskModules.find((module) => module.id === initialModuleId) ?? null : null;
      if (requestedModule && moduleId !== requestedModule.id) {
        setModuleId(requestedModule.id);
        setArgs(argsStateFromRecord(requestedModule, initialArgs ?? {}));
        return;
      }
      if (!moduleId && taskModules.length > 0) {
        setModuleId(taskModules[0].id);
        setArgs(initialModuleArgs(taskModules[0]));
      }
    }, 0);
    return () => window.clearTimeout(handle);
  }, [initialArgs, initialModuleId, moduleId, taskModules]);

  useEffect(() => {
    const handle = window.setTimeout(() => void loadTasks(), 0);
    return () => window.clearTimeout(handle);
  }, [loadTasks]);

  useEffect(() => {
    if (!latestEvent?.type.startsWith('task.') || latestEvent.type === 'task.result.chunk') {
      return;
    }
    if (latestEvent.scope.beacon_id && latestEvent.scope.beacon_id !== targetBeaconId) {
      return;
    }
    const handle = window.setTimeout(() => void loadTasks(), 0);
    return () => window.clearTimeout(handle);
  }, [latestEvent?.id, latestEvent?.scope.beacon_id, latestEvent?.type, loadTasks, targetBeaconId]);

  useEffect(() => {
    if (latestEvent?.type !== 'task.result.completed' || !selectedTaskId) {
      return;
    }
    if (latestEvent.scope.task_id && latestEvent.scope.task_id !== selectedTaskId) {
      return;
    }
    const handle = window.setTimeout(() => void loadTaskResult(selectedTaskId), 0);
    return () => window.clearTimeout(handle);
  }, [latestEvent?.id, latestEvent?.scope.task_id, latestEvent?.type, loadTaskResult, selectedTaskId]);

  useEffect(() => {
    const result = latestEvent ? taskResultFromRealtimeEvent(latestEvent) : null;
    if (!result?.task_id) {
      return;
    }
    const handle = window.setTimeout(() => {
      setTasks((current) => current.map((task) => (
        task.id === result.task_id
          ? { ...task, completed_at: result.completed_at, status: result.status, updated_at: result.updated_at }
          : task
      )));
    }, 0);
    return () => window.clearTimeout(handle);
  }, [latestEvent]);

  function handleModuleChange(nextModuleId: string): void {
    const nextModule = taskModules.find((module) => module.id === nextModuleId) ?? null;
    setModuleId(nextModuleId);
    setArgs(initialModuleArgs(nextModule));
    setSelectedTaskId('');
    setTaskResult(null);
    setTaskResultError('');
  }

  function handleTargetChange(nextBeaconId: string): void {
    if (lockTargetBeacon) {
      return;
    }
    setTargetBeaconId(nextBeaconId);
    setSelectedTaskId('');
    setTaskResult(null);
    setTaskResultError('');
  }

  async function handleSubmitTask(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedModule || !selectedBeacon || Object.keys(fieldErrors).length > 0) {
      setTaskError('Select a module, valid args, and a target beacon before queueing.');
      return;
    }
    setIsSubmittingTask(true);
    try {
      await createTask(
        connection.baseUrl,
        connection.accessToken,
        selectedBeacon.id,
        selectedModule.id,
        buildArgs(selectedModule, args),
        priority,
      );
      setArgs(initialModuleArgs(selectedModule));
      setTaskError('');
      await loadTasks();
    } catch (caught) {
      setTaskError(caught instanceof Error ? caught.message : 'Unable to queue task.');
    } finally {
      setIsSubmittingTask(false);
    }
  }

  async function handleCancelTask(task: Task): Promise<void> {
    setCancellingTaskId(task.id);
    try {
      const cancelled = await cancelTask(connection.baseUrl, connection.accessToken, task.id);
      setTasks((current) => current.map((item) => (item.id === cancelled.id ? cancelled : item)));
      setTaskError('');
      await loadTasks();
    } catch (caught) {
      setTaskError(caught instanceof Error ? caught.message : 'Unable to cancel task.');
    } finally {
      setCancellingTaskId('');
    }
  }

  function handleSelectTask(task: Task): void {
    setSelectedTaskId(task.id);
    setTaskResult(null);
    setTaskResultError('');
    void backfillTask(task.id).catch(() => undefined);
    if (isTerminalStatus(task.status)) {
      void loadTaskResult(task.id);
    }
  }

  async function handleDownloadResult(stream: 'combined' | ResultStream): Promise<void> {
    if (!selectedTaskId) {
      return;
    }
    setDownloadingResultStream(stream);
    try {
      const blob = await downloadTaskResultText(connection.baseUrl, connection.accessToken, selectedTaskId, stream);
      const href = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = href;
      anchor.download = `${selectedTaskId}-${stream}.txt`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(href);
      setTaskResultError('');
    } catch (caught) {
      setTaskResultError(caught instanceof Error ? caught.message : 'Unable to download task result.');
    } finally {
      setDownloadingResultStream('');
    }
  }

  function handleDrop(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setIsDraggingOver(false);
    if (lockTargetBeacon) {
      setDragError('This command queue is locked to the open beacon.');
      return;
    }
    const beaconId = readBeaconId(event);
    const beacon = beacons.find((item) => item.id === beaconId);
    if (!beacon) {
      setDragError('Drop a known beacon row onto the target field.');
      return;
    }
    setDragError('');
    handleTargetChange(beacon.id);
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    if (lockTargetBeacon) {
      event.dataTransfer.dropEffect = 'none';
      return;
    }
    event.dataTransfer.dropEffect = 'copy';
    setIsDraggingOver(true);
  }

  return (
    <div className="task-queue-panel task-execution-panel" data-testid={`${testIdPrefix}task-execution-panel`}>
      <div className="beacon-section-head">
        <div>
          <strong>{title}</strong>
          <span>Queue one-shot module tasks and review durable results.</span>
        </div>
        <button className="secondary-button" disabled={isLoadingModules} onClick={() => void loadModules()} type="button">
          <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
          <span>{isLoadingModules ? 'Loading' : 'Modules'}</span>
        </button>
      </div>

      <form className="task-command-form" onSubmit={handleSubmitTask}>
        <div className="task-command-grid task-command-grid--module">
          <ModulePicker isLoading={isLoadingModules} modules={taskModules} onChange={handleModuleChange} selectedModuleId={moduleId} />
          <label>
            <span>Priority</span>
            <select
              aria-label={labelPrefix ? `${labelPrefix} Task priority` : 'Task priority'}
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
          <button className="primary-button task-submit-button" disabled={isSubmittingTask || !canSubmit} type="submit">
            <Send aria-hidden="true" size={15} strokeWidth={2.2} />
            <span>{isSubmittingTask ? 'Queueing' : 'Queue'}</span>
          </button>
        </div>

        <div className="task-command-grid task-command-grid--args">
          <ModuleArgsForm
            args={args}
            errors={fieldErrors}
            labelPrefix={labelPrefix}
            module={selectedModule}
            onChange={(field, value) => setArgs((current) => ({ ...current, [field]: value }))}
          />
        </div>

        <BeaconTargetField
          beacons={beacons}
          dragError={dragError}
          isLocked={lockTargetBeacon}
          isDraggingOver={isDraggingOver}
          onDragLeave={() => setIsDraggingOver(false)}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onTargetChange={handleTargetChange}
          selectedBeacon={selectedBeacon}
          targetBeaconId={targetBeaconId}
        />
      </form>

      {moduleError ? <p className="task-queue-error" role="alert">{moduleError}</p> : null}
      {taskError ? <p className="task-queue-error" role="alert">{taskError}</p> : null}

      <div className="task-queue-toolbar">
        <div className="task-history-count">
          <strong>{queuedTaskCount}</strong>
          <span>queued</span>
        </div>
        <label className="task-history-search">
          <Search aria-hidden="true" size={14} strokeWidth={2} />
          <input
            aria-label={labelPrefix ? `${labelPrefix} Search command history` : 'Search command history'}
            onChange={(event) => setTaskSearchQuery(event.target.value)}
            placeholder="Search commands"
            value={taskSearchQuery}
          />
        </label>
        <select
          aria-label={labelPrefix ? `${labelPrefix} Filter task status` : 'Filter task status'}
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

      <div className="task-list" data-testid={`${testIdPrefix}beacon-task-list`}>
        <TaskList
          beaconLabel={beaconLabel}
          cancellingTaskId={cancellingTaskId}
          isLoading={isLoadingTasks}
          onCancel={(task) => void handleCancelTask(task)}
          onSelect={handleSelectTask}
          selectedTaskId={selectedTaskId}
          tasks={tasks}
        />
      </div>

      <TaskDetailPanel
        downloadingResultStream={downloadingResultStream}
        isLoadingTaskResult={isLoadingTaskResult}
        onClearStream={() => selectedTaskId ? clearTaskStream(selectedTaskId) : undefined}
        onDownloadResult={(stream) => void handleDownloadResult(stream)}
        result={taskResult}
        resultError={taskResultError}
        resultStream={taskResultStream}
        selectedTask={selectedTask}
        setResultStream={setTaskResultStream}
        streamBuffer={selectedTaskId ? streamForTask(selectedTaskId) : null}
      />
    </div>
  );
}
