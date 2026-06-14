import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';

import {
  createWorkerPairingToken,
  getInfrastructureWorkers,
  getProtocolInfo,
  getProtocolSecurityEvents,
  getTransportStatus,
  InfrastructureWorker,
  launchInfrastructureWorker,
  PairingTokenResponse,
  ProtocolInfo,
  ProtocolSecurityEvent,
  TransportStatus,
  stopInfrastructureWorker,
  WorkerKind,
} from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';
import { ProtocolSecurityEventsPanel, ProtocolStatusPanel, TransportStatusPanel } from './C2ProtocolPanels';
import { WorkerAction, WorkerActionModal, WorkerActionMode, WorkerSection } from './C2WorkerPanels';

export function C2SettingsPage() {
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const [workers, setWorkers] = useState<InfrastructureWorker[]>([]);
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [action, setAction] = useState<WorkerAction | null>(null);
  const [actionError, setActionError] = useState('');
  const [pairing, setPairing] = useState<PairingTokenResponse | null>(null);
  const [protocolInfo, setProtocolInfo] = useState<ProtocolInfo | null>(null);
  const [protocolEvents, setProtocolEvents] = useState<ProtocolSecurityEvent[]>([]);
  const [protocolError, setProtocolError] = useState('');
  const [transportStatus, setTransportStatus] = useState<TransportStatus | null>(null);
  const [transportError, setTransportError] = useState('');
  const [isSubmitting, setSubmitting] = useState(false);
  const [stoppingWorkerId, setStoppingWorkerId] = useState('');

  const loadWorkers = useCallback(async () => {
    if (!connection) {
      setWorkers([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await getInfrastructureWorkers(connection.baseUrl, connection.accessToken);
      setWorkers(response.items);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load C2 workers.');
    } finally {
      setLoading(false);
    }
  }, [connection]);

  const loadProtocolState = useCallback(async () => {
    if (!connection) {
      setProtocolInfo(null);
      setProtocolEvents([]);
      return;
    }
    setProtocolError('');
    try {
      const [info, events] = await Promise.all([
        getProtocolInfo(connection.baseUrl, connection.accessToken),
        getProtocolSecurityEvents(connection.baseUrl, connection.accessToken),
      ]);
      setProtocolInfo(info);
      setProtocolEvents(events.items);
    } catch (caught) {
      setProtocolError(caught instanceof Error ? caught.message : 'Unable to load C2 protocol state.');
    }
  }, [connection]);

  const loadTransportState = useCallback(async () => {
    if (!connection) {
      setTransportStatus(null);
      return;
    }
    setTransportError('');
    try {
      setTransportStatus(await getTransportStatus(connection.baseUrl, connection.accessToken));
    } catch (caught) {
      setTransportError(caught instanceof Error ? caught.message : 'Unable to load C2 transport state.');
    }
  }, [connection]);

  useEffect(() => {
    const refreshTimer = window.setTimeout(() => {
      void loadWorkers();
      void loadProtocolState();
      void loadTransportState();
    }, 0);
    return () => window.clearTimeout(refreshTimer);
  }, [loadProtocolState, loadTransportState, loadWorkers]);

  useEffect(() => {
    const eventType = realtime.latestEvent?.type ?? '';
    if (eventType.startsWith('worker.') || eventType.startsWith('beacon.')) {
      const refreshTimer = window.setTimeout(() => {
        if (eventType.startsWith('worker.')) {
          void loadWorkers();
        }
        if (eventType.startsWith('beacon.')) {
          void loadTransportState();
        }
      }, 0);
      return () => window.clearTimeout(refreshTimer);
    }
    return undefined;
  }, [loadTransportState, loadWorkers, realtime.latestEvent]);

  const workerCounts = useMemo(
    () => ({
      failed: workers.filter((worker) => worker.status === 'failed').length,
      offline: workers.filter((worker) => worker.status === 'offline').length,
      online: workers.filter((worker) => worker.status === 'online').length,
      total: workers.length,
    }),
    [workers],
  );

  function openAction(kind: WorkerKind, mode: WorkerActionMode): void {
    setAction({ kind, mode });
    setPairing(null);
    setActionError('');
  }

  async function handleActionSubmit(name: string, hostPort: number): Promise<void> {
    if (!connection || !action) {
      return;
    }
    setSubmitting(true);
    setActionError('');
    try {
      if (action.mode === 'pair') {
        const response = await createWorkerPairingToken(connection.baseUrl, connection.accessToken, action.kind, name);
        setPairing(response);
      } else {
        await launchInfrastructureWorker(connection.baseUrl, connection.accessToken, action.kind, name, hostPort);
        setAction(null);
        await loadWorkers();
      }
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : 'Worker action failed.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStop(worker: InfrastructureWorker): Promise<void> {
    if (!connection) {
      return;
    }
    setStoppingWorkerId(worker.id);
    setError('');
    try {
      await stopInfrastructureWorker(connection.baseUrl, connection.accessToken, worker.id);
      await loadWorkers();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to stop worker.');
    } finally {
      setStoppingWorkerId('');
    }
  }

  return (
    <AppShell description="C2 worker registration and provisioning" section="settings" title="Settings" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="c2-settings-layout">
          <section className="workspace-panel infrastructure-overview" aria-label="C2 worker overview">
            <div className="panel-header">
              <div>
                <h2>C2 infrastructure</h2>
                <p className="muted-text">Pair dedicated workers or launch managed workers on the connected C2 host.</p>
              </div>
              <button
                className="secondary-button"
                disabled={isLoading}
                onClick={() => {
                  void loadWorkers();
                  void loadProtocolState();
                  void loadTransportState();
                }}
                type="button"
              >
                <RefreshCw aria-hidden="true" size={15} strokeWidth={2.2} />
                <span>{isLoading ? 'Refreshing...' : 'Refresh'}</span>
              </button>
            </div>

            <div className="worker-stat-grid">
              <div>
                <span>Total workers</span>
                <strong>{workerCounts.total}</strong>
              </div>
              <div>
                <span>Online</span>
                <strong>{workerCounts.online}</strong>
              </div>
              <div>
                <span>Offline</span>
                <strong>{workerCounts.offline}</strong>
              </div>
              <div>
                <span>Failed</span>
                <strong>{workerCounts.failed}</strong>
              </div>
            </div>
            {error ? (
              <p className="alert-message alert-message--inline" role="alert">
                {error}
              </p>
            ) : null}
          </section>

          <div className="protocol-observability-grid">
            <ProtocolStatusPanel protocolError={protocolError} protocolInfo={protocolInfo} />
            <TransportStatusPanel transportError={transportError} transportStatus={transportStatus} />
            <ProtocolSecurityEventsPanel protocolEvents={protocolEvents} />
          </div>

          <div className="infrastructure-grid">
            <WorkerSection
              isStopping={stoppingWorkerId}
              kind="beacon-handler"
              onLaunch={(kind) => openAction(kind, 'launch')}
              onPair={(kind) => openAction(kind, 'pair')}
              onStop={handleStop}
              workers={workers.filter((worker) => worker.kind === 'beacon-handler')}
            />
            <WorkerSection
              isStopping={stoppingWorkerId}
              kind="scanner"
              onLaunch={(kind) => openAction(kind, 'launch')}
              onPair={(kind) => openAction(kind, 'pair')}
              onStop={handleStop}
              workers={workers.filter((worker) => worker.kind === 'scanner')}
            />
          </div>
        </div>
      )}

      {action ? (
        <WorkerActionModal
          action={action}
          error={actionError}
          isSubmitting={isSubmitting}
          onClose={() => setAction(null)}
          onSubmit={handleActionSubmit}
          pairing={pairing}
        />
      ) : null}
    </AppShell>
  );
}
