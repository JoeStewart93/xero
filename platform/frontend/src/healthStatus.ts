import type { DependencyStatus } from './api';
import type { RealtimeStatus } from './operatorRealtime';

export function normalizeDependencyStatus(status: DependencyStatus | string | undefined): DependencyStatus {
  if (status === 'healthy' || status === 'unhealthy' || status === 'unknown') {
    return status;
  }
  return 'unknown';
}

export function realtimeReadinessStatus(status: RealtimeStatus | string): DependencyStatus {
  if (status === 'connected') {
    return 'healthy';
  }
  if (status === 'degraded' || status === 'disconnected') {
    return 'unhealthy';
  }
  return 'unknown';
}

export function formatRealtimeStatus(status: string): string {
  return status.replace(/^\w/, (firstLetter) => firstLetter.toUpperCase());
}
