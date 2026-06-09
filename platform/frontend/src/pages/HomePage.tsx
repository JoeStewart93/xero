import { useEffect, useState } from 'react';
import { Cable, FolderKanban, Home, RadioTower, ServerCog } from 'lucide-react';

import { ReadinessResponse, getReadiness } from '../api';
import { AppShell } from '../components/AppShell';
import { useAuth } from '../useAuth';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';

type HomeReadinessState =
  | { kind: 'loading' }
  | { data: ReadinessResponse; kind: 'loaded' }
  | { kind: 'error'; message: string };

export function HomePage() {
  const { session } = useAuth();
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const [readiness, setReadiness] = useState<HomeReadinessState>({ kind: 'loading' });

  useEffect(() => {
    if (!session) {
      return;
    }
    let active = true;
    getReadiness(session.accessToken)
      .then((data) => {
        if (active) {
          setReadiness({ data, kind: 'loaded' });
        }
      })
      .catch((error: Error) => {
        if (active) {
          setReadiness({ kind: 'error', message: error.message });
        }
      });

    return () => {
      active = false;
    };
  }, [session]);

  const bffStatus = readiness.kind === 'loaded' ? readiness.data.status : readiness.kind;
  const c2Status = connection ? 'connected' : 'disconnected';

  return (
    <AppShell description="Local BFF and C2 backend overview" section="home" title="Home">
      <div className="home-grid">
        <section className="workspace-panel" aria-label="Architecture status">
          <div className="panel-header">
            <div>
              <h2>Architecture status</h2>
              <p className="muted-text">The UI/BFF stack is local; C2 Core can run locally or remotely.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <Home size={18} strokeWidth={2} />
            </div>
          </div>

          <div className="dashboard-list">
            <div className="dashboard-row">
              <span>Local BFF</span>
              <strong>{bffStatus}</strong>
            </div>
            <div className="dashboard-row">
              <span>C2 backend</span>
              <strong>{c2Status}</strong>
            </div>
            <div className="dashboard-row">
              <span>Lifecycle controls</span>
              <strong>{connection ? 'Unlocked' : 'Locked'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Operator realtime</span>
              <strong>{realtime.status}</strong>
            </div>
            <div className="dashboard-row">
              <span>Active beacons</span>
              <strong data-testid="home-beacon-count">{realtime.activeBeaconCount}</strong>
            </div>
            <div className="dashboard-row">
              <span>Offline beacons</span>
              <strong data-testid="home-offline-beacon-count">{realtime.offlineBeaconCount}</strong>
            </div>
          </div>
          {readiness.kind === 'error' && <p className="error-text">{readiness.message}</p>}
        </section>

        <section className="workspace-panel" aria-label="C2 connection summary">
          <div className="panel-header">
            <div>
              <h2>C2 connection</h2>
              <p className="muted-text">Authenticate in Settings to bind this console to a C2 Core.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <Cable size={18} strokeWidth={2} />
            </div>
          </div>

          <div className="dashboard-list">
            <div className="dashboard-row">
              <span>Endpoint</span>
              <strong>{connection?.baseUrl ?? '-'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Service</span>
              <strong>{connection?.service ?? '-'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Token expires</span>
              <strong>{connection ? new Date(connection.expiresAt).toLocaleString() : '-'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Latest realtime event</span>
              <strong data-testid="home-latest-realtime-event">{realtime.latestEvent?.type ?? '-'}</strong>
            </div>
          </div>
        </section>

        <section className="workspace-panel lifecycle-panel" aria-label="Discovery lifecycle">
          <div className="panel-header">
            <div>
              <h2>Discovery lifecycle</h2>
              <p className="muted-text">Project scope leads into recon, then findings triage.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <ServerCog size={18} strokeWidth={2} />
            </div>
          </div>

          <div className="lifecycle-steps">
            <div className="lifecycle-step">
              <FolderKanban aria-hidden="true" size={18} strokeWidth={2} />
              <strong>Projects</strong>
              <span>Create scoped projects and add domains or IP addresses.</span>
            </div>
            <div className="lifecycle-step">
              <RadioTower aria-hidden="true" size={18} strokeWidth={2} />
              <strong>Recon</strong>
              <span>Queue discovery tools through the authenticated C2 Core.</span>
            </div>
            <div className="lifecycle-step lifecycle-step--muted">
              <ServerCog aria-hidden="true" size={18} strokeWidth={2} />
              <strong>Findings</strong>
              <span>Planned triage workspace for discovered vulnerabilities.</span>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
