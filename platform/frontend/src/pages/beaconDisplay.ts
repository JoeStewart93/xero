import type { Beacon } from '../api';

export type BeaconSortDirection = 'asc' | 'desc';
export type BeaconSortKey = 'external_ip' | 'hostname' | 'internal_ip' | 'last_seen' | 'os' | 'status' | 'transport_mode';

export const DEFAULT_BEACON_SORT_DIRECTION: BeaconSortDirection = 'desc';
export const DEFAULT_BEACON_SORT_KEY: BeaconSortKey = 'last_seen';

export function compactDateTime(value: string): string {
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

export function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function formatRelativeTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - parsed.getTime()) / 1000));
  if (elapsedSeconds < 45) {
    return 'just now';
  }
  const elapsedMinutes = Math.floor(elapsedSeconds / 60);
  if (elapsedMinutes < 60) {
    return `${elapsedMinutes}m ago`;
  }
  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) {
    return `${elapsedHours}h ago`;
  }
  return `${Math.floor(elapsedHours / 24)}d ago`;
}

export function statusClass(status: string): string {
  return status.toLowerCase() === 'online' ? 'beacon-status beacon-status--online' : 'beacon-status beacon-status--offline';
}

export function transportLabel(mode: Beacon['transport_mode']): string {
  if (mode === 'websocket') {
    return 'WebSocket';
  }
  if (mode === 'long-poll') {
    return 'Long-poll';
  }
  return 'REST';
}

export function transportState(beacon: Beacon): string {
  return beacon.transport_connected ? 'Connected' : 'Disconnected';
}

export function searchBeacon(beacon: Beacon, query: string): boolean {
  if (!query) {
    return true;
  }

  const haystack = [
    beacon.hostname,
    beacon.os,
    beacon.architecture,
    beacon.internal_ip,
    beacon.external_ip ?? '',
    beacon.machine_fingerprint_hash,
    beacon.pid,
    beacon.status,
    beacon.protocol_version ?? '',
    beacon.transport_connected ? 'connected' : 'disconnected',
    transportLabel(beacon.transport_mode),
    beacon.transport_mode,
  ]
    .join(' ')
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function sortValue(beacon: Beacon, sortKey: BeaconSortKey): string | number {
  if (sortKey === 'last_seen') {
    const parsed = Date.parse(beacon.last_seen);
    return Number.isNaN(parsed) ? 0 : parsed;
  }
  if (sortKey === 'external_ip') {
    return beacon.external_ip ?? '';
  }
  return beacon[sortKey];
}

export function sortBeacons(beacons: Beacon[], sortKey: BeaconSortKey, sortDirection: BeaconSortDirection): Beacon[] {
  return [...beacons].sort((left, right) => {
    const leftValue = sortValue(left, sortKey);
    const rightValue = sortValue(right, sortKey);
    const comparison =
      typeof leftValue === 'number' && typeof rightValue === 'number'
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: 'base' });
    return sortDirection === 'asc' ? comparison : -comparison;
  });
}
