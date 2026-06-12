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
  protocol_version: number | null;
  status: string;
  transport_connected: boolean;
  transport_last_seen: string | null;
  transport_mode: 'long-poll' | 'rest' | 'websocket';
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
export type BeaconBuildStatus = 'building' | 'failed' | 'queued' | 'succeeded';
export type BeaconBuildTargetOS = 'linux' | 'windows';
export type BeaconBuildTargetArch = 'amd64';
export type BeaconBuildConfigMode = 'all' | 'env' | 'file' | 'ldflags';

export interface ShellTaskArgs {
  command: string;
  shell_type?: ShellType;
  timeout_seconds?: number;
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

export async function getC2Beacons(baseUrl: string, accessToken: string): Promise<BeaconListResponse> {
  const headers = new Headers();
  headers.set('Accept', 'application/json');
  headers.set('Authorization', `Bearer ${accessToken}`);

  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/beacons`, { headers });
  return parseJsonResponse<BeaconListResponse>(response);
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

export async function getTasks(
  baseUrl: string,
  accessToken: string,
  options: { beaconId?: string; limit?: number; status?: TaskStatus } = {},
): Promise<TaskListResponse> {
  const params = new URLSearchParams();
  if (options.beaconId) {
    params.set('beacon_id', options.beaconId);
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

export async function createShellTask(
  baseUrl: string,
  accessToken: string,
  beaconId: string,
  args: ShellTaskArgs,
  priority: TaskPriority = 'normal',
): Promise<Task> {
  return c2Fetch<Task>(baseUrl, accessToken, '/api/v1/tasks', {
    method: 'POST',
    body: JSON.stringify({
      args,
      beacon_id: beaconId,
      module: 'shell',
      priority,
    }),
  });
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
