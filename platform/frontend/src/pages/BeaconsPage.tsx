import { KeyboardEvent, useMemo, useState } from 'react';
import {
  Boxes,
  Cpu,
  Crosshair,
  FileArchive,
  Fingerprint,
  KeyRound,
  Network,
  RadioTower,
  Server,
  ShieldCheck,
  TerminalSquare,
  X,
} from 'lucide-react';
import { createPortal } from 'react-dom';

import type { Beacon } from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';

function formatDateTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function statusClass(status: string): string {
  return status.toLowerCase() === 'online' ? 'beacon-status beacon-status--online' : 'beacon-status beacon-status--offline';
}

function compactDateTime(value: string): string {
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

function formatRelativeTime(value: string): string {
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

function DetailRow({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="beacon-detail-row">
      <span>{label}</span>
      <strong>{value ?? '-'}</strong>
    </div>
  );
}

function sortBeacons(beacons: Beacon[]): Beacon[] {
  return [...beacons].sort((left, right) => Date.parse(right.last_seen) - Date.parse(left.last_seen));
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
    description: 'Open a focused session workspace for direct host interaction.',
    icon: Crosshair,
    key: 'session',
    label: 'Interactive session',
    status: 'Locked',
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

function BeaconOperationsModal({
  beacon,
  onClose,
}: {
  beacon: Beacon;
  onClose: () => void;
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
  const [selectedBeaconId, setSelectedBeaconId] = useState('');
  const [operationBeaconId, setOperationBeaconId] = useState('');
  const beacons = useMemo(() => sortBeacons(realtime.beacons), [realtime.beacons]);
  const selectedBeacon = beacons.find((beacon) => beacon.id === selectedBeaconId) ?? beacons[0] ?? null;
  const operationBeacon = beacons.find((beacon) => beacon.id === operationBeaconId) ?? null;
  const activeBeaconCount = beacons.filter((beacon) => beacon.status.toLowerCase() === 'online').length;
  const offlineBeaconCount = beacons.filter((beacon) => beacon.status.toLowerCase() === 'offline').length;

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
    <AppShell description="Registered C2 beacon registry" section="beacons" title="Beacons" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="beacons-workspace-grid">
          <section className="workspace-panel beacons-roster-panel" aria-label="Beacon registry">
            <div className="panel-header">
              <div>
                <h2>Beacon registry</h2>
                <p className="muted-text">Registered systems reporting through the active C2 backend.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <RadioTower size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="beacon-summary-strip">
              <div>
                <span>Total</span>
                <strong>{beacons.length}</strong>
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

            {beacons.length === 0 ? (
              <div className="beacon-empty-state" data-testid="beacons-empty-state">
                <RadioTower aria-hidden="true" size={20} strokeWidth={2} />
                <div>
                  <strong>No beacons registered.</strong>
                  <span>Beacon check-ins will appear here as the C2 backend accepts registrations.</span>
                </div>
              </div>
            ) : (
              <div className="beacon-registry-wrap" data-testid="beacon-roster">
                <table className="beacon-registry-table">
                  <thead>
                    <tr>
                      <th scope="col">Host</th>
                      <th scope="col">Operating system</th>
                      <th scope="col">Internal IP</th>
                      <th scope="col">External IP</th>
                      <th scope="col">PID / Arch</th>
                      <th scope="col">Last Heartbeat</th>
                      <th scope="col">Status</th>
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
                            <span className={statusClass(beacon.status)}>{beacon.status}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
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
                  <DetailRow label="Internal IP" value={selectedBeacon.internal_ip} />
                  <DetailRow label="External IP" value={selectedBeacon.external_ip} />
                  <DetailRow label="First seen" value={formatDateTime(selectedBeacon.first_seen)} />
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

          {operationBeacon ? <BeaconOperationsModal beacon={operationBeacon} onClose={() => setOperationBeaconId('')} /> : null}
        </div>
      )}
    </AppShell>
  );
}
