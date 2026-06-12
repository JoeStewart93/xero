import { FormEvent, useState } from 'react';
import { Copy, Plus, Radar, RadioTower, Rocket, ServerCog, Square, X } from 'lucide-react';
import { createPortal } from 'react-dom';

import type { InfrastructureWorker, PairingTokenResponse, WorkerKind } from '../api';
import { compactDateTime, originLabel, statusClass } from './c2SettingsDisplay';

export type WorkerActionMode = 'launch' | 'pair';

export interface WorkerAction {
  kind: WorkerKind;
  mode: WorkerActionMode;
}

const workerProfiles: Record<
  WorkerKind,
  {
    description: string;
    emptyText: string;
    icon: typeof RadioTower;
    launchPort: number;
    singular: string;
    title: string;
  }
> = {
  'beacon-handler': {
    description: 'Connection handlers that accept beacon traffic and relay control through C2.',
    emptyText: 'No dedicated beacon handlers are paired yet.',
    icon: RadioTower,
    launchPort: 8002,
    singular: 'beacon handler',
    title: 'Beacon handlers',
  },
  scanner: {
    description: 'Scanner workers available for recon execution and future distributed scan sharding.',
    emptyText: 'No external scanners are paired yet.',
    icon: Radar,
    launchPort: 8003,
    singular: 'scanner',
    title: 'Scanners',
  },
};

function defaultWorkerName(kind: WorkerKind, mode: WorkerActionMode): string {
  const profile = workerProfiles[kind];
  return mode === 'launch' ? `managed ${profile.singular}` : `external ${profile.singular}`;
}

function WorkerSummaryCard({ worker }: { worker: InfrastructureWorker }) {
  return (
    <article className="worker-card" data-testid={`worker-card-${worker.kind}-${worker.name}`}>
      <div className="worker-card-head">
        <div>
          <strong>{worker.name}</strong>
          <span>
            {originLabel(worker.origin)} / {worker.endpoint ?? 'endpoint pending'}
          </span>
        </div>
        <span className={statusClass(worker.status)}>{worker.status}</span>
      </div>
      <div className="worker-metrics">
        <div>
          <span>Load</span>
          <strong>
            {worker.current_load}/{worker.capacity}
          </strong>
        </div>
        <div>
          <span>Heartbeat</span>
          <strong>{compactDateTime(worker.last_seen)}</strong>
        </div>
        <div>
          <span>Port</span>
          <strong>{worker.managed_host_port ?? '-'}</strong>
        </div>
      </div>
      <div className="worker-capabilities" aria-label={`${worker.name} capabilities`}>
        {worker.capabilities.length > 0 ? (
          worker.capabilities.map((capability) => <span key={capability}>{capability}</span>)
        ) : (
          <span>capabilities pending</span>
        )}
      </div>
      {worker.last_error ? <p className="worker-error">{worker.last_error}</p> : null}
    </article>
  );
}

export function WorkerSection({
  isStopping,
  kind,
  onLaunch,
  onPair,
  onStop,
  workers,
}: {
  isStopping: string;
  kind: WorkerKind;
  onLaunch: (kind: WorkerKind) => void;
  onPair: (kind: WorkerKind) => void;
  onStop: (worker: InfrastructureWorker) => void;
  workers: InfrastructureWorker[];
}) {
  const profile = workerProfiles[kind];
  const Icon = profile.icon;
  const embedded = workers.filter((worker) => worker.origin === 'embedded');
  const dedicated = workers.filter((worker) => worker.origin !== 'embedded');

  return (
    <section className="workspace-panel infrastructure-panel" aria-label={profile.title}>
      <div className="panel-header">
        <div>
          <h2>{profile.title}</h2>
          <p className="muted-text">{profile.description}</p>
        </div>
        <div className="panel-icon" aria-hidden="true">
          <Icon size={18} strokeWidth={2} />
        </div>
      </div>

      <div className="infrastructure-action-row">
        <button className="secondary-button" onClick={() => onPair(kind)} type="button">
          <Plus aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>Add external</span>
        </button>
        <button className="primary-button" onClick={() => onLaunch(kind)} type="button">
          <Rocket aria-hidden="true" size={15} strokeWidth={2.2} />
          <span>Launch on C2 host</span>
        </button>
      </div>

      <div className="worker-section-group">
        <div className="worker-section-heading">
          <strong>Embedded default</strong>
          <span>{embedded.length}</span>
        </div>
        <div className="worker-card-list worker-card-list--compact">
          {embedded.map((worker) => (
            <WorkerSummaryCard key={worker.id} worker={worker} />
          ))}
        </div>
      </div>

      <div className="worker-section-group">
        <div className="worker-section-heading">
          <strong>Dedicated nodes</strong>
          <span>{dedicated.length}</span>
        </div>
        {dedicated.length === 0 ? (
          <div className="worker-empty-state">
            <ServerCog aria-hidden="true" size={18} strokeWidth={2} />
            <span>{profile.emptyText}</span>
          </div>
        ) : (
          <div className="worker-card-list">
            {dedicated.map((worker) => {
              const canStop = worker.origin === 'c2-managed' && !['offline', 'stopping'].includes(worker.status);
              return (
                <div className="worker-managed-row" key={worker.id}>
                  <WorkerSummaryCard worker={worker} />
                  <button
                    className="danger-button worker-stop-button"
                    disabled={!canStop || isStopping === worker.id}
                    onClick={() => onStop(worker)}
                    type="button"
                  >
                    <Square aria-hidden="true" size={13} strokeWidth={2.4} />
                    <span>{isStopping === worker.id ? 'Stopping...' : 'Stop'}</span>
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}

export function WorkerActionModal({
  action,
  error,
  isSubmitting,
  onClose,
  onSubmit,
  pairing,
}: {
  action: WorkerAction;
  error: string;
  isSubmitting: boolean;
  onClose: () => void;
  onSubmit: (name: string, hostPort: number) => void;
  pairing: PairingTokenResponse | null;
}) {
  const [name, setName] = useState(defaultWorkerName(action.kind, action.mode));
  const [hostPort, setHostPort] = useState(workerProfiles[action.kind].launchPort);
  const profile = workerProfiles[action.kind];
  const title = action.mode === 'launch' ? `Launch ${profile.singular}` : `Pair external ${profile.singular}`;

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    onSubmit(name, hostPort);
  }

  async function copyCommand(): Promise<void> {
    if (!pairing || !navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(pairing.command);
  }

  return createPortal(
    <div className="infrastructure-modal-backdrop" role="presentation">
      <section aria-label={title} aria-modal="true" className="infrastructure-modal" role="dialog">
        <div className="infrastructure-modal-head">
          <div>
            <span className="beacon-operations-kicker">C2 worker control</span>
            <h2>{title}</h2>
            <p>
              {action.mode === 'launch'
                ? 'Start a managed worker from the C2 host through the provisioning bridge.'
                : 'Create a one-time pairing token for a dedicated worker node.'}
            </p>
          </div>
          <button aria-label="Close worker action" className="beacon-modal-close" onClick={onClose} type="button">
            <X aria-hidden="true" size={17} strokeWidth={2.2} />
          </button>
        </div>

        <form className="workspace-form infrastructure-modal-form" onSubmit={handleSubmit}>
          <label>
            Worker name
            <input onChange={(event) => setName(event.target.value)} value={name} />
          </label>
          {action.mode === 'launch' ? (
            <label>
              Host port
              <input
                max={65535}
                min={1024}
                onChange={(event) => setHostPort(Number(event.target.value))}
                type="number"
                value={hostPort}
              />
            </label>
          ) : null}
          {error ? (
            <p className="alert-message alert-message--inline" role="alert">
              {error}
            </p>
          ) : null}
          <div className="button-row">
            <button className="primary-button" disabled={isSubmitting || Boolean(pairing)} type="submit">
              {isSubmitting ? 'Working...' : action.mode === 'launch' ? 'Launch worker' : 'Create token'}
            </button>
            <button className="secondary-button" onClick={onClose} type="button">
              Close
            </button>
          </div>
        </form>

        {pairing ? (
          <div className="pairing-result" data-testid="pairing-result">
            <div className="dashboard-list">
              <div className="dashboard-row">
                <span>Token</span>
                <strong>{pairing.pairing_token}</strong>
              </div>
              <div className="dashboard-row">
                <span>Expires</span>
                <strong>{new Date(pairing.expires_at).toLocaleString()}</strong>
              </div>
            </div>
            <div className="pairing-command-block">
              <span>Worker startup command</span>
              <code>{pairing.command}</code>
              <button className="secondary-button" onClick={copyCommand} type="button">
                <Copy aria-hidden="true" size={14} strokeWidth={2.2} />
                <span>Copy command</span>
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </div>,
    document.body,
  );
}
