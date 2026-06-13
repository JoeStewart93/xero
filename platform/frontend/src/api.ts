import {
  clearStoredAuthSession,
  emitAuthSessionExpired,
  readStoredAuthSession,
} from './authStorage';

export type DependencyStatus = 'healthy' | 'unhealthy' | 'unknown';

export interface Operator {
  id: string;
  username: string;
  role: 'admin' | 'operator';
  is_enabled: boolean;
  created_at: string;
}

export interface AuthSession {
  accessToken: string;
  tokenType: 'bearer';
  expiresAt: string;
  operator: Operator;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  expires_at: string;
  operator: Operator;
}

export interface ReadinessResponse {
  status: 'ready' | 'degraded';
  service: string;
  checks: {
    postgres: { status: DependencyStatus; error?: string };
    redis: { status: DependencyStatus; error?: string };
  };
}

export interface BeaconListResponse {
  items: Beacon[];
}

export interface BeaconRegistrationResponse {
  beacon: Beacon;
  beacon_id: string;
  beacon_token: string;
  jitter: number;
  profile?: TrafficProfilePayload | null;
  sleep: number;
  status: string;
}

export interface Beacon {
  architecture: string;
  external_ip: string | null;
  first_seen: string;
  hostname: string;
  id: string;
  internal_ip: string;
  last_seen: string;
  machine_fingerprint_hash: string;
  os: string;
  pid: number;
  applied_profile_version?: number | null;
  jitter?: number;
  profile_applied_at?: string | null;
  profile_id?: string | null;
  profile_name?: string | null;
  profile_template?: string | null;
  profile_version?: number | null;
  protocol_version: number | null;
  removed_at?: string | null;
  removed_by?: string | null;
  removed_reason?: string | null;
  sleep_seconds?: number;
  status: string;
  transport_connected: boolean;
  transport_last_seen: string | null;
  transport_mode: 'long-poll' | 'rest' | 'websocket';
}

export interface BeaconKillResponse {
  beacon: Beacon;
  cancelled_tasks: number;
  closed_sessions: number;
  status: 'already_removed' | 'removed';
}

export interface BeaconActivityItem {
  beacon_id: string;
  detail: string | null;
  id: string;
  label: string;
  occurred_at: string;
  session_id: string | null;
  status: string | null;
  task_id: string | null;
  type: string;
}

export interface BeaconActivityListResponse {
  items: BeaconActivityItem[];
}

export type WorkerKind = 'beacon-handler' | 'scanner';

export interface InfrastructureWorker {
  capabilities: string[];
  capacity: number;
  created_at: string;
  current_load: number;
  endpoint: string | null;
  id: string;
  kind: WorkerKind;
  last_error: string | null;
  last_seen: string | null;
  managed_host_port: number | null;
  managed_project: string | null;
  managed_service: string | null;
  name: string;
  origin: 'c2-managed' | 'embedded' | 'external';
  status: 'failed' | 'offline' | 'online' | 'pending' | 'starting' | 'stopping';
  updated_at: string;
  version: string | null;
}

export interface InfrastructureWorkerListResponse {
  items: InfrastructureWorker[];
}

export interface PairingTokenResponse {
  command: string;
  expires_at: string;
  id: string;
  kind: WorkerKind;
  name: string;
  pairing_token: string;
}

export interface WorkerLaunchResponse {
  worker: InfrastructureWorker;
}

export interface WorkerStopResponse {
  status: string;
  worker: InfrastructureWorker;
}

export interface ProtocolInfo {
  c2_public_key_b64: string;
  current_version: number;
  encryption: string;
  frame_harness_enabled: boolean;
  frame_header_length: number;
  integrity: string;
  key_exchange: string;
  max_frame_bytes: number;
  supported_versions: number[];
}

export interface ProtocolSecurityEvent {
  beacon_id: string | null;
  event_type: string;
  id: string;
  message: string;
  nonce: string | null;
  occurred_at: string;
  session_id: string | null;
  severity: 'high' | 'low' | 'medium';
}

export interface ProtocolSecurityEventListResponse {
  items: ProtocolSecurityEvent[];
}

export interface TransportStatus {
  active_longpoll_requests: number;
  active_websocket_connections: number;
  longpoll_max_frame_bytes: number;
  longpoll_timeout_seconds: number;
  transport_mode_counts: Record<'long-poll' | 'rest' | 'websocket', number>;
  websocket_heartbeat_timeout_seconds: number;
  websocket_max_message_bytes: number;
  websocket_ping_interval_seconds: number;
  websocket_ping_timeout_seconds: number;
  websocket_registration_timeout_seconds: number;
  websocket_send_queue_size: number;
}

export type TaskPriority = 'high' | 'low' | 'normal' | 'urgent';
export type TaskStatus = 'cancelled' | 'completed' | 'dispatched' | 'failed' | 'queued' | 'running';
export type ShellType = 'auto' | 'bash' | 'cmd' | 'powershell';
export type SessionStatus = 'closed' | 'closing' | 'detached' | 'failed' | 'open' | 'opening';
export type ShellSessionStatus = SessionStatus;
export type BeaconBuildStatus = 'building' | 'failed' | 'queued' | 'succeeded';
export type BeaconBuildTargetOS = 'linux' | 'windows';
export type BeaconBuildTargetArch = 'amd64';
export type BeaconBuildConfigMode = 'all' | 'env' | 'file' | 'ldflags';

export interface TrafficProfileConfig {
  headers: Record<string, string>;
  jitter: number;
  padding: {
    enabled: boolean;
    max_bytes: number;
    min_bytes: number;
  };
  paths: {
    frame: string;
    poll: string;
    register: string;
    websocket: string;
  };
  sleep_seconds: number;
  user_agent: string;
}

export interface TrafficProfilePayload {
  config: TrafficProfileConfig;
  current_version: number;
  id: string | null;
  is_template: boolean;
  name: string;
  template: string;
}

export interface TrafficProfile extends TrafficProfilePayload {
  created_at: string;
  description: string | null;
  id: string;
  is_archived: boolean;
  updated_at: string;
}

export interface TrafficProfileListResponse {
  items: TrafficProfile[];
}

export interface TrafficProfileVersion {
  config: TrafficProfileConfig;
  created_at: string;
  created_by: string;
  id: string;
  profile_id: string;
  version: number;
}

export interface TrafficProfileVersionListResponse {
  items: TrafficProfileVersion[];
}

export interface TrafficProfileSaveRequest {
  config: TrafficProfileConfig;
  description?: string | null;
  name: string;
  template?: string;
}

export interface ShellTaskArgs {
  command: string;
  shell_type?: ShellType;
  timeout_seconds?: number;
}

export interface ShellSession {
  actor_subject: string;
  beacon_id: string;
  close_reason: string | null;
  closed_at: string | null;
  cols: number;
  created_at: string;
  detached_at: string | null;
  id: string;
  last_activity_at: string;
  opened_at: string;
  rows: number;
  session_type: 'shell';
  shell_type: ShellType;
  status: ShellSessionStatus;
  updated_at: string;
}

export interface ShellSessionCreateRequest {
  beacon_id: string;
  cols?: number;
  rows?: number;
  shell_type?: ShellType;
}

export interface FileBrowserSession {
  actor_subject: string;
  beacon_id: string;
  close_reason: string | null;
  closed_at: string | null;
  created_at: string;
  detached_at: string | null;
  id: string;
  last_activity_at: string;
  opened_at: string;
  session_type: 'file_browser';
  status: SessionStatus;
  updated_at: string;
}

export interface FileBrowserSessionCreateRequest {
  beacon_id: string;
  root_path?: string | null;
}

export type FileTransferDirection = 'download' | 'upload';
export type FileTransferStatus = 'completed' | 'failed' | 'staged' | 'transferring';

export interface FileTransfer {
  acked_chunks: number;
  artifact_available?: boolean | null;
  artifact_id: string | null;
  beacon_id: string;
  chunk_size_bytes: number;
  completed_at: string | null;
  created_at: string;
  direction: FileTransferDirection;
  error_message: string | null;
  filename: string;
  id: string;
  remote_path: string;
  session_id: string;
  sha256: string | null;
  size_bytes: number;
  staged_chunks: number;
  started_at: string | null;
  status: FileTransferStatus;
  total_chunks: number;
  updated_at: string;
}

export interface FileTransferCreateRequest {
  beacon_id: string;
  filename: string;
  overwrite?: boolean;
  remote_path: string;
  session_id: string;
  sha256: string;
  size_bytes: number;
}

export interface RegistrySession {
  actor_subject: string;
  beacon_id: string;
  close_reason: string | null;
  closed_at: string | null;
  created_at: string;
  detached_at: string | null;
  id: string;
  last_activity_at: string;
  opened_at: string;
  session_type: 'registry';
  status: SessionStatus;
  updated_at: string;
}

export interface RegistrySessionCreateRequest {
  beacon_id: string;
}

export interface Task {
  args: Record<string, unknown>;
  beacon_id: string;
  cancelled_at: string | null;
  completed_at: string | null;
  created_at: string;
  dispatched_at: string | null;
  id: string;
  module: string;
  priority: TaskPriority;
  queued_at: string;
  running_at: string | null;
  status: TaskStatus;
  updated_at: string;
}

export interface TaskListResponse {
  items: Task[];
}

export interface DashboardBeaconCounts {
  offline: number;
  online: number;
  total: number;
}

export interface DashboardActivityItem {
  beacon_id: string | null;
  detail: string | null;
  id: string;
  label: string;
  occurred_at: string;
  status: string | null;
  task_id: string | null;
  type: string;
}

export interface DashboardHealthCheck {
  error?: string | null;
  status: DependencyStatus | string;
}

export interface DashboardHealth {
  checks: Record<string, DashboardHealthCheck>;
  status: 'degraded' | 'ready';
}

export interface DashboardSummary {
  beacons: DashboardBeaconCounts;
  c2_health: DashboardHealth;
  generated_at: string;
  recent_activity: DashboardActivityItem[];
  recent_tasks: Task[];
}

export interface TaskAuditEvent {
  actor_subject: string;
  beacon_id: string;
  command: string | null;
  created_at: string;
  event_type: string;
  id: string;
  message: string | null;
  metadata: Record<string, unknown>;
  module: string;
  occurred_at: string;
  task_id: string;
  task_status: TaskStatus | null;
  updated_at: string;
}

export interface TaskAuditEventListResponse {
  items: TaskAuditEvent[];
}

export interface TaskResultArtifact {
  available?: boolean | null;
  content_type: string;
  filename: string;
  id: string;
  role: 'binary' | 'combined' | 'stderr' | 'stdout';
  sha256: string;
  size_bytes: number;
}

export interface TaskResult {
  artifacts: TaskResultArtifact[];
  beacon_id: string;
  completed_at: string | null;
  created_at: string;
  error_message: string | null;
  exit_code: number | null;
  expires_at: string;
  id: string;
  metadata: Record<string, unknown>;
  output_sha256: string | null;
  output_size_bytes: number;
  status: 'completed' | 'failed';
  stderr?: string | null;
  stderr_sha256: string | null;
  stderr_size_bytes: number;
  stdout?: string | null;
  stdout_sha256: string | null;
  stdout_size_bytes: number;
  task_id: string;
  timed_out: boolean;
  truncated: boolean;
  updated_at: string;
}

export interface TaskResultListResponse {
  items: TaskResult[];
  next_cursor: string | null;
}

export interface TaskResultChunk {
  beacon_id: string;
  chunk: string;
  chunk_sha256: string;
  created_at: string;
  id: string;
  received_at: string;
  sequence: number;
  stream: 'stderr' | 'stdout';
  stream_sha256: string | null;
  stream_size_bytes: number | null;
  task_id: string;
  task_result_id: string;
  total_chunks: number;
  upload_id: string;
}

export interface TaskResultChunkListResponse {
  items: TaskResultChunk[];
}

export interface ModuleDefinition {
  args_schema: Record<string, unknown>;
  author?: string;
  category: string;
  description: string;
  disabled_reason?: string | null;
  documentation_url?: string | null;
  example: Record<string, unknown>;
  execution_kind: string;
  id: string;
  name: string;
  plugin_id?: string | null;
  required_capabilities: string[];
  result_schema: Record<string, unknown>;
  source: string;
  status?: 'disabled' | 'enabled' | 'unavailable';
  supported_execution_targets: string[];
  tags?: string[];
  updated_at?: string | null;
  version: string;
}

export interface ModuleListResponse {
  items: ModuleDefinition[];
}

export type AssetType = 'beacon_host' | 'discovered_host' | 'service';
export type AssetSource = 'beacon' | 'scan';

export interface AssetIdentifier {
  first_seen: string;
  id: string;
  kind: string;
  last_seen: string;
  normalized_value: string;
  source: AssetSource | string;
  value: string;
}

export interface AssetBeaconLink {
  beacon_id: string;
  first_seen: string;
  hostname: string | null;
  id: string;
  last_seen: string;
  machine_fingerprint_hash: string;
  status: string | null;
}

export interface AssetRelationship {
  asset_id: string;
  direction: 'inbound' | 'outbound';
  first_seen: string;
  id: string;
  last_seen: string;
  metadata: Record<string, unknown>;
  related_asset_id: string;
  related_asset_name: string | null;
  relationship_type: string;
  scan_job_id: string | null;
  source: AssetSource | string;
}

export interface AssetObservation {
  beacon_id: string | null;
  id: string;
  observation_type: string;
  observed_at: string;
  payload: Record<string, unknown>;
  scan_job_id: string | null;
  scan_result_chunk_id: string | null;
  source: AssetSource | string;
}

export interface Asset {
  asset_type: AssetType;
  created_at: string;
  display_name: string;
  domain: string | null;
  first_seen: string;
  hostname: string | null;
  id: string;
  identifiers?: AssetIdentifier[];
  last_seen: string;
  linked_beacons?: AssetBeaconLink[];
  metadata: Record<string, unknown>;
  observations?: AssetObservation[];
  os: string | null;
  primary_ip: string | null;
  relationships?: AssetRelationship[];
  role: string | null;
  source: AssetSource | string;
  updated_at: string;
}

export interface AssetListResponse {
  items: Asset[];
  limit: number;
  offset: number;
  total: number;
}

export interface AssetListOptions {
  limit?: number;
  offset?: number;
  q?: string;
  source?: AssetSource | 'all';
  type?: AssetType | 'all';
}

export type ScanJobStatus = 'completed' | 'failed' | 'queued' | 'running';
export type ScanModuleId = 'builtin.portscan' | 'builtin.serviceenum';
export type ScanResultState = 'closed' | 'filtered' | 'open';
export type ServiceEnumStatus = 'error' | 'identified' | 'skipped' | 'timeout' | 'unknown';

export interface PortScanArgs {
  execution_target?: 'auto';
  max_threads?: number;
  port_range: string;
  targets: string[];
  timeout_ms?: number;
}

export interface ServiceEnumArgs {
  execution_target?: 'auto';
  host: string;
  max_threads?: number;
  ports: number[];
  probe_timeout_ms?: number;
  source_scan_job_id?: string | null;
}

export type ScanJobArgs = PortScanArgs | ServiceEnumArgs;

export interface PortScanResultRecord {
  host: string;
  latency_ms: number;
  port: number;
  state: ScanResultState;
}

export interface ServiceEnumTls {
  issuer_cn: string | null;
  not_after: string;
  not_before: string;
  sans: string[];
  serial_number: string;
  subject_cn: string | null;
}

export interface ServiceEnumEvidence {
  type: string;
  value: string;
}

export interface ServiceEnumResultRecord {
  banner: string;
  confidence: number;
  error: string | null;
  evidence: ServiceEnumEvidence[];
  host: string;
  latency_ms: number;
  port: number;
  service_guess: string;
  status: ServiceEnumStatus;
  tls: ServiceEnumTls | null;
  transport: 'tcp';
}

export type ScanResultRecord = PortScanResultRecord | ServiceEnumResultRecord;

export interface ScanJob {
  actor_subject: string;
  args: ScanJobArgs;
  completed_at: string | null;
  created_at: string;
  error_message: string | null;
  execution_target_requested: string;
  execution_target_resolved: string;
  id: string;
  module: ScanModuleId | string;
  progress_completed: number;
  progress_total: number;
  queued_at: string;
  results: ScanResultRecord[];
  started_at: string | null;
  state_counts: Record<string, number>;
  status: ScanJobStatus;
  summary: {
    duration_ms?: number;
    host?: string;
    hosts_scanned?: number;
    identified_count?: number;
    open_count?: number;
    ports_enumerated?: number;
    ports_scanned?: number;
    source_scan_job_id?: string | null;
    state_counts?: Record<string, number>;
  };
  updated_at: string;
  worker_id: string | null;
}

export interface ScanJobListResponse {
  items: ScanJob[];
}

export interface ScanResultChunk {
  created_at: string;
  emitted_at: string;
  id: string;
  kind: 'progress' | 'summary';
  payload: {
    results?: ScanResultRecord[];
    state_counts?: Record<string, number>;
    summary?: ScanJob['summary'];
  };
  probes_completed: number;
  probes_total: number;
  scan_job_id: string;
  sequence: number;
}

export interface ScanResultChunkListResponse {
  items: ScanResultChunk[];
}

export interface BeaconBuildTarget {
  arch: BeaconBuildTargetArch;
  extension: string;
  label: string;
  os: BeaconBuildTargetOS;
}

export interface BeaconBuildTargetListResponse {
  items: BeaconBuildTarget[];
}

export interface BeaconBuildCreateRequest {
  c2_url: string;
  config_mode?: BeaconBuildConfigMode;
  fallback_longpoll_enabled?: boolean;
  jitter?: number;
  output_limit_bytes?: number;
  output_name?: string;
  profile_name?: string;
  sleep_seconds?: number;
  target_arch: BeaconBuildTargetArch;
  target_os: BeaconBuildTargetOS;
  user_agent?: string | null;
}

export interface BeaconBuild {
  artifact_available: boolean;
  artifact_filename: string | null;
  artifact_sha256: string | null;
  artifact_size: number | null;
  completed_at: string | null;
  config: Record<string, unknown>;
  created_at: string;
  error_message: string | null;
  id: string;
  logs_tail: string | null;
  profile_name: string;
  started_at: string | null;
  status: BeaconBuildStatus;
  target_arch: BeaconBuildTargetArch;
  target_os: BeaconBuildTargetOS;
  updated_at: string;
}

export interface BeaconBuildListResponse {
  items: BeaconBuild[];
}

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '');
export const DEFAULT_C2_BASE_URL = (import.meta.env.VITE_DEFAULT_C2_BASE_URL ?? 'http://localhost:8001').replace(/\/$/, '');

async function parseResponseJson<T>(response: Response): Promise<T | Record<string, never>> {
  try {
    return (await response.json()) as T;
  } catch {
    return {};
  }
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  const payload = await parseResponseJson<T>(response);

  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload ? String(payload.detail) : '';
    throw new Error(detail || 'Request failed');
  }
  return payload as T;
}

function isAuthenticatedApiPath(path: string): boolean {
  return path.startsWith('/api/v1/');
}

function handleAuthenticatedUnauthorized(response: Response, shouldUseAuth: boolean): void {
  if (response.status !== 401 || !shouldUseAuth) {
    return;
  }

  clearStoredAuthSession();
  emitAuthSessionExpired();
}

async function apiFetch<T>(path: string, options: RequestInit = {}, accessToken?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const token = accessToken ?? readStoredAuthSession()?.accessToken;
  const shouldUseAuth = Boolean(token) && isAuthenticatedApiPath(path);
  if (shouldUseAuth) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  handleAuthenticatedUnauthorized(response, shouldUseAuth);
  return parseJsonResponse<T>(response);
}

export async function getReadiness(accessToken?: string): Promise<ReadinessResponse> {
  const headers = new Headers();
  headers.set('Accept', 'application/json');
  const token = accessToken ?? readStoredAuthSession()?.accessToken;
  const shouldUseAuth = Boolean(token);
  if (shouldUseAuth) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/ready`, { headers });
  const payload = await parseResponseJson<ReadinessResponse>(response);

  handleAuthenticatedUnauthorized(response, shouldUseAuth);

  if (response.status === 503) {
    return payload as ReadinessResponse;
  }

  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload ? String(payload.detail) : '';
    throw new Error(detail || 'Request failed');
  }

  return payload as ReadinessResponse;
}

export async function loginOperator(username: string, password: string): Promise<AuthSession> {
  const response = await apiFetch<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });

  return {
    accessToken: response.access_token,
    tokenType: response.token_type,
    expiresAt: response.expires_at,
    operator: response.operator,
  };
}

export async function getCurrentOperator(accessToken?: string): Promise<Operator> {
  return apiFetch<Operator>('/api/v1/me', {}, accessToken);
}

export async function getC2Beacons(
  baseUrl: string,
  accessToken: string,
  options: { includeRemoved?: boolean; status?: 'offline' | 'online' } = {},
): Promise<BeaconListResponse> {
  const headers = new Headers();
  headers.set('Accept', 'application/json');
  headers.set('Authorization', `Bearer ${accessToken}`);

  const params = new URLSearchParams();
  if (options.includeRemoved) {
    params.set('include_removed', 'true');
  }
  if (options.status) {
    params.set('status', options.status);
  }
  const query = params.toString();
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/beacons${query ? `?${query}` : ''}`, { headers });
  return parseJsonResponse<BeaconListResponse>(response);
}

export async function getC2Beacon(
  baseUrl: string,
  accessToken: string,
  beaconId: string,
  includeRemoved = false,
): Promise<Beacon> {
  const query = includeRemoved ? '?include_removed=true' : '';
  return c2Fetch<Beacon>(baseUrl, accessToken, `/api/v1/beacons/${beaconId}${query}`);
}

async function c2Fetch<T>(baseUrl: string, accessToken: string, path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Accept', 'application/json');
  headers.set('Authorization', `Bearer ${accessToken}`);
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, { ...options, headers });
  return parseJsonResponse<T>(response);
}

export async function getInfrastructureWorkers(baseUrl: string, accessToken: string): Promise<InfrastructureWorkerListResponse> {
  return c2Fetch<InfrastructureWorkerListResponse>(baseUrl, accessToken, '/api/v1/infrastructure/workers');
}

export async function createWorkerPairingToken(
  baseUrl: string,
  accessToken: string,
  kind: WorkerKind,
  name: string,
): Promise<PairingTokenResponse> {
  return c2Fetch<PairingTokenResponse>(baseUrl, accessToken, '/api/v1/infrastructure/pairing-tokens', {
    method: 'POST',
    body: JSON.stringify({ kind, name }),
  });
}

export async function launchInfrastructureWorker(
  baseUrl: string,
  accessToken: string,
  kind: WorkerKind,
  name: string,
  hostPort: number,
): Promise<WorkerLaunchResponse> {
  return c2Fetch<WorkerLaunchResponse>(baseUrl, accessToken, '/api/v1/infrastructure/workers/launch', {
    method: 'POST',
    body: JSON.stringify({ host_port: hostPort, kind, name }),
  });
}

export async function stopInfrastructureWorker(
  baseUrl: string,
  accessToken: string,
  workerId: string,
): Promise<WorkerStopResponse> {
  return c2Fetch<WorkerStopResponse>(baseUrl, accessToken, `/api/v1/infrastructure/workers/${workerId}/stop`, {
    method: 'POST',
  });
}

export async function getProtocolInfo(baseUrl: string, accessToken: string): Promise<ProtocolInfo> {
  return c2Fetch<ProtocolInfo>(baseUrl, accessToken, '/api/v1/protocol');
}

export async function getProtocolSecurityEvents(
  baseUrl: string,
  accessToken: string,
  limit = 25,
): Promise<ProtocolSecurityEventListResponse> {
  return c2Fetch<ProtocolSecurityEventListResponse>(baseUrl, accessToken, `/api/v1/security/events?limit=${limit}`);
}

export async function getTransportStatus(baseUrl: string, accessToken: string): Promise<TransportStatus> {
  return c2Fetch<TransportStatus>(baseUrl, accessToken, '/api/v1/transport');
}

export async function getDashboardSummary(baseUrl: string, accessToken: string): Promise<DashboardSummary> {
  return c2Fetch<DashboardSummary>(baseUrl, accessToken, '/api/v1/dashboard/summary');
}

export async function getTrafficProfiles(
  baseUrl: string,
  accessToken: string,
  includeArchived = false,
): Promise<TrafficProfileListResponse> {
  const query = includeArchived ? '?include_archived=true' : '';
  return c2Fetch<TrafficProfileListResponse>(baseUrl, accessToken, `/api/v1/traffic-profiles${query}`);
}

export async function createTrafficProfile(
  baseUrl: string,
  accessToken: string,
  payload: TrafficProfileSaveRequest,
): Promise<TrafficProfile> {
  return c2Fetch<TrafficProfile>(baseUrl, accessToken, '/api/v1/traffic-profiles', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTrafficProfile(
  baseUrl: string,
  accessToken: string,
  profileId: string,
  payload: TrafficProfileSaveRequest,
): Promise<TrafficProfile> {
  return c2Fetch<TrafficProfile>(baseUrl, accessToken, `/api/v1/traffic-profiles/${profileId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function archiveTrafficProfile(
  baseUrl: string,
  accessToken: string,
  profileId: string,
): Promise<TrafficProfile> {
  return c2Fetch<TrafficProfile>(baseUrl, accessToken, `/api/v1/traffic-profiles/${profileId}`, {
    method: 'DELETE',
  });
}

export async function cloneTrafficProfile(
  baseUrl: string,
  accessToken: string,
  profileId: string,
  name?: string,
): Promise<TrafficProfile> {
  return c2Fetch<TrafficProfile>(baseUrl, accessToken, `/api/v1/traffic-profiles/${profileId}/clone`, {
    method: 'POST',
    body: JSON.stringify({ name: name || null }),
  });
}

export async function getTrafficProfileVersions(
  baseUrl: string,
  accessToken: string,
  profileId: string,
): Promise<TrafficProfileVersionListResponse> {
  return c2Fetch<TrafficProfileVersionListResponse>(
    baseUrl,
    accessToken,
    `/api/v1/traffic-profiles/${profileId}/versions`,
  );
}

export async function rollbackTrafficProfile(
  baseUrl: string,
  accessToken: string,
  profileId: string,
  version: number,
): Promise<TrafficProfile> {
  return c2Fetch<TrafficProfile>(baseUrl, accessToken, `/api/v1/traffic-profiles/${profileId}/rollback`, {
    method: 'POST',
    body: JSON.stringify({ version }),
  });
}

export async function assignBeaconTrafficProfile(
  baseUrl: string,
  accessToken: string,
  beaconId: string,
  profileId: string | null,
): Promise<Beacon> {
  return c2Fetch<Beacon>(baseUrl, accessToken, `/api/v1/beacons/${beaconId}/profile`, {
    method: 'PUT',
    body: JSON.stringify({ profile_id: profileId }),
  });
}

export async function clearBeaconTrafficProfile(baseUrl: string, accessToken: string, beaconId: string): Promise<Beacon> {
  return c2Fetch<Beacon>(baseUrl, accessToken, `/api/v1/beacons/${beaconId}/profile`, {
    method: 'DELETE',
  });
}

export async function killBeacon(baseUrl: string, accessToken: string, beaconId: string): Promise<BeaconKillResponse> {
  return c2Fetch<BeaconKillResponse>(baseUrl, accessToken, `/api/v1/beacons/${beaconId}/kill`, {
    method: 'POST',
  });
}

export async function getBeaconActivity(
  baseUrl: string,
  accessToken: string,
  beaconId: string,
  limit = 20,
): Promise<BeaconActivityListResponse> {
  return c2Fetch<BeaconActivityListResponse>(baseUrl, accessToken, `/api/v1/beacons/${beaconId}/activity?limit=${limit}`);
}

export async function getTasks(
  baseUrl: string,
  accessToken: string,
  options: { beaconId?: string; command?: string; limit?: number; status?: TaskStatus } = {},
): Promise<TaskListResponse> {
  const params = new URLSearchParams();
  if (options.beaconId) {
    params.set('beacon_id', options.beaconId);
  }
  if (options.command) {
    params.set('command', options.command);
  }
  if (options.status) {
    params.set('status', options.status);
  }
  if (options.limit) {
    params.set('limit', String(options.limit));
  }
  const query = params.toString();
  return c2Fetch<TaskListResponse>(baseUrl, accessToken, `/api/v1/tasks${query ? `?${query}` : ''}`);
}

export async function getTaskAuditEvents(
  baseUrl: string,
  accessToken: string,
  taskId: string,
  limit = 20,
): Promise<TaskAuditEventListResponse> {
  return c2Fetch<TaskAuditEventListResponse>(baseUrl, accessToken, `/api/v1/tasks/${taskId}/audit?limit=${limit}`);
}

export async function getTaskResult(baseUrl: string, accessToken: string, taskId: string): Promise<TaskResult> {
  return c2Fetch<TaskResult>(baseUrl, accessToken, `/api/v1/tasks/${taskId}/result`);
}

export async function getTaskResults(
  baseUrl: string,
  accessToken: string,
  options: { beaconId?: string; cursor?: string; limit?: number; status?: TaskResult['status'] } = {},
): Promise<TaskResultListResponse> {
  const params = new URLSearchParams();
  if (options.beaconId) {
    params.set('beacon_id', options.beaconId);
  }
  if (options.status) {
    params.set('status', options.status);
  }
  if (options.cursor) {
    params.set('cursor', options.cursor);
  }
  if (options.limit) {
    params.set('limit', String(options.limit));
  }
  const query = params.toString();
  return c2Fetch<TaskResultListResponse>(baseUrl, accessToken, `/api/v1/task-results${query ? `?${query}` : ''}`);
}

export async function getTaskResultChunks(
  baseUrl: string,
  accessToken: string,
  taskId: string,
  options: { afterSequence?: number; limit?: number; stream?: TaskResultChunk['stream']; uploadId?: string } = {},
): Promise<TaskResultChunkListResponse> {
  const params = new URLSearchParams();
  if (options.stream) {
    params.set('stream', options.stream);
  }
  if (options.uploadId) {
    params.set('upload_id', options.uploadId);
  }
  if (typeof options.afterSequence === 'number') {
    params.set('after_sequence', String(options.afterSequence));
  }
  if (options.limit) {
    params.set('limit', String(options.limit));
  }
  const query = params.toString();
  return c2Fetch<TaskResultChunkListResponse>(baseUrl, accessToken, `/api/v1/tasks/${taskId}/result/chunks${query ? `?${query}` : ''}`);
}

export async function getModules(baseUrl: string, accessToken: string): Promise<ModuleListResponse> {
  return c2Fetch<ModuleListResponse>(baseUrl, accessToken, '/api/v1/modules');
}

export async function getAssets(
  baseUrl: string,
  accessToken: string,
  options: AssetListOptions = {},
): Promise<AssetListResponse> {
  const params = new URLSearchParams();
  if (options.type && options.type !== 'all') {
    params.set('type', options.type);
  }
  if (options.source && options.source !== 'all') {
    params.set('source', options.source);
  }
  if (options.q) {
    params.set('q', options.q);
  }
  if (typeof options.limit === 'number') {
    params.set('limit', String(options.limit));
  }
  if (typeof options.offset === 'number') {
    params.set('offset', String(options.offset));
  }
  const query = params.toString();
  return c2Fetch<AssetListResponse>(baseUrl, accessToken, `/api/v1/assets${query ? `?${query}` : ''}`);
}

export async function getAsset(baseUrl: string, accessToken: string, assetId: string): Promise<Asset> {
  return c2Fetch<Asset>(baseUrl, accessToken, `/api/v1/assets/${assetId}`);
}

export async function createScanJob(baseUrl: string, accessToken: string, args: PortScanArgs): Promise<ScanJob>;
export async function createScanJob(baseUrl: string, accessToken: string, module: ScanModuleId, args: ScanJobArgs): Promise<ScanJob>;
export async function createScanJob(
  baseUrl: string,
  accessToken: string,
  moduleOrArgs: ScanModuleId | PortScanArgs,
  maybeArgs?: ScanJobArgs,
): Promise<ScanJob> {
  const module = typeof moduleOrArgs === 'string' ? moduleOrArgs : 'builtin.portscan';
  const args = typeof moduleOrArgs === 'string' ? maybeArgs : moduleOrArgs;
  if (!args) {
    throw new Error('Scan job args are required.');
  }
  return c2Fetch<ScanJob>(baseUrl, accessToken, '/api/v1/scan-jobs', {
    method: 'POST',
    body: JSON.stringify({
      args: { ...args, execution_target: args.execution_target ?? 'auto' },
      module,
    }),
  });
}

export async function getScanJobs(
  baseUrl: string,
  accessToken: string,
  options: { limit?: number; status?: ScanJobStatus } = {},
): Promise<ScanJobListResponse> {
  const params = new URLSearchParams();
  if (options.status) {
    params.set('status', options.status);
  }
  if (options.limit) {
    params.set('limit', String(options.limit));
  }
  const query = params.toString();
  return c2Fetch<ScanJobListResponse>(baseUrl, accessToken, `/api/v1/scan-jobs${query ? `?${query}` : ''}`);
}

export async function getScanJob(baseUrl: string, accessToken: string, scanJobId: string): Promise<ScanJob> {
  return c2Fetch<ScanJob>(baseUrl, accessToken, `/api/v1/scan-jobs/${scanJobId}`);
}

export async function getScanResultChunks(
  baseUrl: string,
  accessToken: string,
  scanJobId: string,
): Promise<ScanResultChunkListResponse> {
  return c2Fetch<ScanResultChunkListResponse>(baseUrl, accessToken, `/api/v1/scan-jobs/${scanJobId}/chunks`);
}

export async function downloadTaskResultText(
  baseUrl: string,
  accessToken: string,
  taskId: string,
  stream: 'combined' | 'stderr' | 'stdout' = 'combined',
): Promise<Blob> {
  const headers = new Headers();
  headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/tasks/${taskId}/result/download?stream=${stream}`, { headers });
  if (!response.ok) {
    const payload = await parseResponseJson<Record<string, string>>(response);
    throw new Error(payload.detail || 'Task result download failed');
  }
  return response.blob();
}

export async function downloadTaskResultArtifact(
  baseUrl: string,
  accessToken: string,
  taskId: string,
  artifactId: string,
): Promise<Blob> {
  const headers = new Headers();
  headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/tasks/${taskId}/result/artifacts/${artifactId}`, { headers });
  if (!response.ok) {
    const payload = await parseResponseJson<Record<string, string>>(response);
    throw new Error(payload.detail || 'Task result artifact download failed');
  }
  return response.blob();
}

export async function createTask(
  baseUrl: string,
  accessToken: string,
  beaconId: string,
  module: string,
  args: Record<string, unknown>,
  priority: TaskPriority = 'normal',
): Promise<Task> {
  return c2Fetch<Task>(baseUrl, accessToken, '/api/v1/tasks', {
    method: 'POST',
    body: JSON.stringify({
      args,
      beacon_id: beaconId,
      module,
      priority,
    }),
  });
}

export async function createShellTask(
  baseUrl: string,
  accessToken: string,
  beaconId: string,
  args: ShellTaskArgs,
  priority: TaskPriority = 'normal',
): Promise<Task> {
  return createTask(baseUrl, accessToken, beaconId, 'shell', { ...args }, priority);
}

export async function createShellSession(
  baseUrl: string,
  accessToken: string,
  payload: ShellSessionCreateRequest,
): Promise<ShellSession> {
  return c2Fetch<ShellSession>(baseUrl, accessToken, '/api/v1/sessions/shell', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createFileBrowserSession(
  baseUrl: string,
  accessToken: string,
  payload: FileBrowserSessionCreateRequest,
): Promise<FileBrowserSession> {
  return c2Fetch<FileBrowserSession>(baseUrl, accessToken, '/api/v1/sessions/file-browser', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function createRegistrySession(
  baseUrl: string,
  accessToken: string,
  payload: RegistrySessionCreateRequest,
): Promise<RegistrySession> {
  return c2Fetch<RegistrySession>(baseUrl, accessToken, '/api/v1/sessions/registry', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function getShellSession(baseUrl: string, accessToken: string, sessionId: string): Promise<ShellSession> {
  return c2Fetch<ShellSession>(baseUrl, accessToken, `/api/v1/sessions/${sessionId}`);
}

export async function closeShellSession(baseUrl: string, accessToken: string, sessionId: string): Promise<ShellSession> {
  return c2Fetch<ShellSession>(baseUrl, accessToken, `/api/v1/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

export async function closeFileBrowserSession(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
): Promise<FileBrowserSession> {
  return c2Fetch<FileBrowserSession>(baseUrl, accessToken, `/api/v1/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

export async function createFileTransferUpload(
  baseUrl: string,
  accessToken: string,
  payload: FileTransferCreateRequest,
): Promise<FileTransfer> {
  return c2Fetch<FileTransfer>(baseUrl, accessToken, '/api/v1/file-transfers/uploads', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function uploadFileTransferChunk(
  baseUrl: string,
  accessToken: string,
  transferId: string,
  sequence: number,
  payload: { chunk_sha256: string; data_b64: string },
): Promise<FileTransfer> {
  return c2Fetch<FileTransfer>(
    baseUrl,
    accessToken,
    `/api/v1/file-transfers/${transferId}/chunks/${sequence}`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  );
}

export async function getFileTransfer(baseUrl: string, accessToken: string, transferId: string): Promise<FileTransfer> {
  return c2Fetch<FileTransfer>(baseUrl, accessToken, `/api/v1/file-transfers/${transferId}`);
}

export async function downloadFileTransferArtifact(
  baseUrl: string,
  accessToken: string,
  transferId: string,
): Promise<Blob> {
  const headers = new Headers();
  headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/file-transfers/${transferId}/artifact`, {
    headers,
  });
  if (!response.ok) {
    const payload = await parseResponseJson<Record<string, string>>(response);
    throw new Error(payload.detail || 'File transfer artifact download failed');
  }
  return response.blob();
}

export async function closeRegistrySession(
  baseUrl: string,
  accessToken: string,
  sessionId: string,
): Promise<RegistrySession> {
  return c2Fetch<RegistrySession>(baseUrl, accessToken, `/api/v1/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

export function shellSessionWebSocketUrl(baseUrl: string, sessionId: string): string {
  return sessionWebSocketUrl(baseUrl, sessionId);
}

export function sessionWebSocketUrl(baseUrl: string, sessionId: string): string {
  const url = new URL(baseUrl);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = `/ws/sessions/${encodeURIComponent(sessionId)}`;
  url.search = '';
  url.hash = '';
  return url.toString();
}

export async function cancelTask(baseUrl: string, accessToken: string, taskId: string): Promise<Task> {
  return c2Fetch<Task>(baseUrl, accessToken, `/api/v1/tasks/${taskId}`, {
    method: 'DELETE',
  });
}

export async function getBeaconBuildTargets(baseUrl: string, accessToken: string): Promise<BeaconBuildTargetListResponse> {
  return c2Fetch<BeaconBuildTargetListResponse>(baseUrl, accessToken, '/api/v1/beacon-builds/targets');
}

export async function getBeaconBuilds(baseUrl: string, accessToken: string, limit = 25): Promise<BeaconBuildListResponse> {
  return c2Fetch<BeaconBuildListResponse>(baseUrl, accessToken, `/api/v1/beacon-builds?limit=${limit}`);
}

export async function createBeaconBuild(
  baseUrl: string,
  accessToken: string,
  payload: BeaconBuildCreateRequest,
): Promise<BeaconBuild> {
  return c2Fetch<BeaconBuild>(baseUrl, accessToken, '/api/v1/beacon-builds', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function downloadBeaconBuildArtifact(baseUrl: string, accessToken: string, buildId: string): Promise<Blob> {
  const headers = new Headers();
  headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/beacon-builds/${buildId}/artifact`, { headers });
  if (!response.ok) {
    const payload = await parseResponseJson<Record<string, string>>(response);
    throw new Error(payload.detail || 'Artifact download failed');
  }
  return response.blob();
}
