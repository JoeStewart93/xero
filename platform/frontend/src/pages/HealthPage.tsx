import { useCallback, useEffect, useMemo, useState } from 'react';
import { RadioTower, RefreshCw, ServerCog } from 'lucide-react';

import { DependencyStatus, ReadinessResponse, getReadiness } from '../api';
import { AppShell } from '../components/AppShell';
import { useAuth } from '../useAuth';
import { useRealtime } from '../useRealtime';

type HealthState =
  | { kind: 'loading' }
  | { kind: 'loaded'; data: ReadinessResponse }
  | { kind: 'error'; message: string };

function normalizeStatus(status: DependencyStatus | undefined): DependencyStatus {
  return status ?? 'unknown';
}

function realtimeReadinessStatus(status: string): DependencyStatus {
  if (status === 'connected') {
    return 'healthy';
  }
  if (status === 'degraded' || status === 'disconnected') {
    return 'unhealthy';
  }
  return 'unknown';
}

function formatRealtimeStatus(status: string): string {
  return status.replace(/^\w/, (firstLetter) => firstLetter.toUpperCase());
}

function StatusRow({
  label,
  description,
  status,
  testId,
}: {
  label: string;
  description: string;
  status: DependencyStatus;
  testId: string;
}) {
  return (
    <div className="status-row" data-testid={testId} data-status={status}>
      <div>
        <strong>{label}</strong>
        <span>{description}</span>
      </div>
      <span>Last checked just now</span>
      <strong className={`status-label status-label--${status}`}>{status}</strong>
    </div>
  );
}

export function HealthPage() {
  const { session } = useAuth();
  const realtime = useRealtime();
  const [state, setState] = useState<HealthState>({ kind: 'loading' });

  const refreshReadiness = useCallback(() => {
    if (!session) {
      return;
    }
    setState({ kind: 'loading' });
    let active = true;

    getReadiness(session.accessToken)
      .then((data) => {
        if (active) {
          setState({ kind: 'loaded', data });
        }
      })
      .catch((error: Error) => {
        if (active) {
          setState({ kind: 'error', message: error.message });
        }
      });

    return () => {
      active = false;
    };
  }, [session]);

  useEffect(() => {
    if (!session) {
      return;
    }
    let active = true;

    getReadiness(session.accessToken)
      .then((data) => {
        if (active) {
          setState({ kind: 'loaded', data });
        }
      })
      .catch((error: Error) => {
        if (active) {
          setState({ kind: 'error', message: error.message });
        }
      });

    return () => {
      active = false;
    };
  }, [session]);

  const statuses = useMemo(() => {
    if (state.kind !== 'loaded') {
      return {
        backend: 'unknown' as DependencyStatus,
        postgres: 'unknown' as DependencyStatus,
        redis: 'unknown' as DependencyStatus,
      };
    }

    return {
      backend: state.data.status === 'ready' ? 'healthy' as const : 'unhealthy' as const,
      postgres: normalizeStatus(state.data.checks.postgres.status),
      redis: normalizeStatus(state.data.checks.redis.status),
    };
  }, [state]);

  return (
    <AppShell
      description="Authenticated readiness"
      section="health"
      title="System health"
      toolbar={
        <button aria-label="Refresh" className="secondary-button" title="Refresh readiness" type="button" onClick={refreshReadiness}>
          <RefreshCw aria-hidden="true" size={15} strokeWidth={2} />
          <span>Refresh</span>
        </button>
      }
    >
      <section className="workspace-panel health-panel" aria-label="Dependency readiness">
        <div className="panel-header">
          <div>
            <h2>Dependency readiness</h2>
            <p className="muted-text">Backend service checks for the local stack.</p>
          </div>
          <div className="panel-icon" aria-hidden="true">
            <ServerCog size={18} strokeWidth={2} />
          </div>
        </div>

        <div className="status-list" aria-live="polite">
          <StatusRow
            label="Backend"
            description="API service"
            status={statuses.backend}
            testId="backend-status"
          />
          <StatusRow
            label="PostgreSQL"
            description="Primary database"
            status={statuses.postgres}
            testId="postgres-status"
          />
          <StatusRow
            label="Redis"
            description="Cache layer"
            status={statuses.redis}
            testId="redis-status"
          />
          <StatusRow
            label="Operator realtime"
            description={`${formatRealtimeStatus(realtime.status)} stream, ${realtime.activeBeaconCount} active / ${realtime.beaconCount} total beacons`}
            status={realtimeReadinessStatus(realtime.status)}
            testId="realtime-status"
          />
        </div>

        <div className="health-realtime-strip" aria-label="Realtime details">
          <RadioTower aria-hidden="true" size={15} strokeWidth={2} />
          <span>Latest event</span>
          <strong>{realtime.latestEvent?.type ?? 'none'}</strong>
          {realtime.error ? <em>{realtime.error}</em> : null}
        </div>

        {state.kind === 'loading' && <p className="supporting-text">Checking service readiness...</p>}
        {state.kind === 'error' && <p className="error-text">{state.message}</p>}
      </section>
    </AppShell>
  );
}
