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
  status: string;
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

export async function getBeacons(accessToken?: string): Promise<BeaconListResponse> {
  return apiFetch<BeaconListResponse>('/api/v1/beacons', {}, accessToken);
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
