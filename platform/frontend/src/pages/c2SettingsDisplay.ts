import type { InfrastructureWorker, ProtocolSecurityEvent } from '../api';

export function compactDateTime(value: string | null): string {
  if (!value) {
    return '-';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(undefined, {
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    month: '2-digit',
  });
}

export function formatBytes(value: number): string {
  const mebibyte = 1024 * 1024;
  const kibibyte = 1024;
  if (value >= mebibyte) {
    return `${Number((value / mebibyte).toFixed(1))} MB`;
  }
  if (value >= kibibyte) {
    return `${Number((value / kibibyte).toFixed(1))} KB`;
  }
  return `${value} bytes`;
}

export function originLabel(origin: InfrastructureWorker['origin']): string {
  if (origin === 'c2-managed') {
    return 'C2 managed';
  }
  return origin;
}

export function severityClass(severity: ProtocolSecurityEvent['severity']): string {
  return `worker-status protocol-severity protocol-severity--${severity}`;
}

export function statusClass(status: InfrastructureWorker['status']): string {
  return `worker-status worker-status--${status}`;
}
