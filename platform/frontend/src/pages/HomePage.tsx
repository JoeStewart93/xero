import { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, Cable, ListChecks, RadioTower, RefreshCw, Settings, TerminalSquare } from 'lucide-react';
import { Link } from 'react-router-dom';

import {
  DashboardActivityItem,
  DashboardBeaconCounts,
  DashboardSummary,
  DependencyStatus,
  ReadinessResponse,
  Task,
  getDashboardSummary,
  getReadiness,
} from '../api';
import { AppShell } from '../components/AppShell';
import { applyDashboardRealtimeEvent } from '../dashboardEvents';
import { formatRealtimeStatus, normalizeDependencyStatus, realtimeReadinessStatus } from '../healthStatus';
import { useAuth } from '../useAuth';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';

type ReadinessState =
  | { kind: 'loading' }
  | { data: ReadinessResponse; kind: 'loaded' }
  | { kind: 'error'; message: string };

type DashboardState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { data: DashboardSummary; kind: 'loaded' }
  | { kind: 'error'; message: string };

interface HealthRow {
  description: string;
  label: string;
  status: DependencyStatus;
}

const EMPTY_COUNTS: DashboardBeaconCounts = { offline: 0, online: 0, total: 0 };

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  return new Date(value).toLocaleString();
}

function taskTime(task: Task): string {
  return task.completed_at ?? task.running_at ?? task.dispatched_at ?? task.queued_at ?? task.created_at;
}

function taskCommand(task: Task): string {
  const command = task.args.command;
  return typeof command === 'string' && command.trim() ? command.trim() : task.module;
}

function statusFromReadiness(state: ReadinessState): DependencyStatus {
  if (state.kind !== 'loaded') {
    return state.kind === 'error' ? 'unhealthy' : 'unknown';
  }
  return state.data.status === 'ready' ? 'healthy' : 'unhealthy';
}

function dependencyFromReadiness(state: ReadinessState, key: 'postgres' | 'redis'): DependencyStatus {
  if (state.kind !== 'loaded') {
    return state.kind === 'error' ? 'unhealthy' : 'unknown';
  }
  return normalizeDependencyStatus(state.data.checks[key]?.status);
}

function c2StatusFromDashboard(state: DashboardState, hasConnection: boolean): DependencyStatus {
  if (!hasConnection) {
    return 'unhealthy';
  }
  if (state.kind !== 'loaded') {
    return state.kind === 'error' ? 'unhealthy' : 'unknown';
  }
  return state.data.c2_health.status === 'ready' ? 'healthy' : 'unhealthy';
}

function SummaryCard({
  icon: Icon,
  label,
  support,
  testId,
  value,
}: {
  icon: typeof RadioTower;
  label: string;
  support: string;
  testId: string;
  value: number;
}) {
  return (
    <div className="dashboard-summary-card">
      <div>
        <span>{label}</span>
        <strong data-testid={testId}>{value}</strong>
        <em>{support}</em>
      </div>
      <Icon aria-hidden="true" size={18} strokeWidth={2} />
    </div>
  );
}

function HealthStatusRow({ row }: { row: HealthRow }) {
  return (
    <div className="status-row dashboard-health-row" data-status={row.status} data-testid={`dashboard-health-${row.label.toLowerCase().replace(/\s+/g, '-')}`}>
      <div>
        <strong>{row.label}</strong>
        <span>{row.description}</span>
      </div>
      <span>Current</span>
      <strong className={`status-label status-label--${row.status}`}>{row.status}</strong>
    </div>
  );
}

function LoadingRows({ label }: { label: string }) {
  return (
    <div aria-label={label} className="dashboard-skeleton-list" data-testid="dashboard-loading-skeleton">
      <span />
      <span />
      <span />
    </div>
  );
}

function RecentTasks({ state }: { state: DashboardState }) {
  if (state.kind === 'loading') {
    return <LoadingRows label="Loading recent tasks" />;
  }
  if (state.kind === 'error') {
    return <p className="error-text">{state.message}</p>;
  }
  const tasks = state.kind === 'loaded' ? state.data.recent_tasks : [];
  if (tasks.length === 0) {
    return (
      <div className="dashboard-empty-state">
        <ListChecks aria-hidden="true" size={18} strokeWidth={2} />
        <div>
          <strong>No recent tasks</strong>
          <span>Task activity will appear here after beacons receive work.</span>
        </div>
      </div>
    );
  }
  return (
    <div className="dashboard-task-list">
      {tasks.map((task) => (
        <div className="dashboard-task-row" key={task.id}>
          <div>
            <strong>{taskCommand(task)}</strong>
            <span>{task.module} on {task.beacon_id.slice(0, 8)}</span>
          </div>
          <span>{formatDateTime(taskTime(task))}</span>
          <strong className="dashboard-status-pill">{task.status}</strong>
        </div>
      ))}
    </div>
  );
}

function RecentActivity({ items, state }: { items: DashboardActivityItem[]; state: DashboardState }) {
  if (state.kind === 'loading') {
    return <LoadingRows label="Loading recent activity" />;
  }
  if (state.kind === 'error') {
    return <p className="error-text">{state.message}</p>;
  }
  if (items.length === 0) {
    return (
      <div className="dashboard-empty-state">
        <Activity aria-hidden="true" size={18} strokeWidth={2} />
        <div>
          <strong>No activity yet</strong>
          <span>Beacon and task events will appear as the C2 stream receives them.</span>
        </div>
      </div>
    );
  }
  return (
    <div className="dashboard-activity-list">
      {items.map((item) => (
        <div className="dashboard-activity-row" key={item.id}>
          <div>
            <strong>{item.label}</strong>
            <span>{item.detail ?? item.type}</span>
          </div>
          <span>{formatDateTime(item.occurred_at)}</span>
        </div>
      ))}
    </div>
  );
}

export function HomePage() {
  const { session } = useAuth();
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const [readiness, setReadiness] = useState<ReadinessState>({ kind: 'loading' });
  const [dashboard, setDashboard] = useState<DashboardState>({ kind: connection ? 'loading' : 'idle' });
  const appliedRealtimeEventId = useRef<string | null>(null);

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

  useEffect(() => {
    if (!connection) {
      return;
    }
    let active = true;
    getDashboardSummary(connection.baseUrl, connection.accessToken)
      .then((data) => {
        if (active) {
          setDashboard({ data, kind: 'loaded' });
        }
      })
      .catch((error: Error) => {
        if (active) {
          setDashboard({ kind: 'error', message: error.message });
        }
      });

    return () => {
      active = false;
    };
  }, [connection]);

  useEffect(() => {
    if (!realtime.latestEvent || appliedRealtimeEventId.current === realtime.latestEvent.id) {
      return;
    }
    appliedRealtimeEventId.current = realtime.latestEvent.id;
    setDashboard((current) => {
      if (current.kind !== 'loaded') {
        return current;
      }
      return { data: applyDashboardRealtimeEvent(current.data, realtime.latestEvent!), kind: 'loaded' };
    });
  }, [realtime.latestEvent]);

  const summaryCounts = dashboard.kind === 'loaded' ? dashboard.data.beacons : EMPTY_COUNTS;
  const counts = realtime.beaconCount > 0 && realtime.beaconCount >= summaryCounts.total
    ? { offline: realtime.offlineBeaconCount, online: realtime.activeBeaconCount, total: realtime.beaconCount }
    : summaryCounts;
  const activityItems = dashboard.kind === 'loaded' ? dashboard.data.recent_activity : [];
  const hasNoBeacons = dashboard.kind === 'loaded' && counts.total === 0;

  const healthRows = useMemo<HealthRow[]>(
    () => [
      {
        description: readiness.kind === 'loaded' ? readiness.data.service : 'Local API service',
        label: 'Local BFF',
        status: statusFromReadiness(readiness),
      },
      {
        description: 'Primary database',
        label: 'PostgreSQL',
        status: dependencyFromReadiness(readiness, 'postgres'),
      },
      {
        description: 'Cache and message bus',
        label: 'Redis',
        status: dependencyFromReadiness(readiness, 'redis'),
      },
      {
        description: connection?.baseUrl ?? 'No C2 connection',
        label: 'C2 API',
        status: c2StatusFromDashboard(dashboard, Boolean(connection)),
      },
      {
        description: `${formatRealtimeStatus(realtime.status)} stream`,
        label: 'Realtime',
        status: realtimeReadinessStatus(realtime.status),
      },
    ],
    [connection, dashboard, readiness, realtime.status],
  );

  return (
    <AppShell description="C2 dashboard overview" section="home" title="Home" wide>
      <div className="dashboard-overview-grid">
        <section className="workspace-panel dashboard-summary-panel" aria-label="Beacon summary">
          <div className="panel-header">
            <div>
              <h2>Beacon summary</h2>
              <p className="muted-text">Counts reflect the connected C2 backend and realtime stream.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <RadioTower size={18} strokeWidth={2} />
            </div>
          </div>
          {dashboard.kind === 'loading' ? (
            <LoadingRows label="Loading beacon summary" />
          ) : (
            <div className="dashboard-summary-cards">
              <SummaryCard icon={RadioTower} label="Total" support="registered beacons" testId="dashboard-total-beacons" value={counts.total} />
              <SummaryCard icon={Activity} label="Online" support="currently reporting" testId="dashboard-online-beacons" value={counts.online} />
              <SummaryCard icon={Cable} label="Offline" support="needs review" testId="dashboard-offline-beacons" value={counts.offline} />
            </div>
          )}
          {hasNoBeacons ? (
            <div className="dashboard-empty-state dashboard-empty-state--inline">
              <RadioTower aria-hidden="true" size={18} strokeWidth={2} />
              <div>
                <strong>No beacons registered</strong>
                <span>Use Deploy or a beacon registration flow when you are ready to attach lab systems.</span>
              </div>
            </div>
          ) : null}
        </section>

        <section className="workspace-panel dashboard-connection-panel" aria-label="C2 connection">
          <div className="panel-header">
            <div>
              <h2>C2 connection</h2>
              <p className="muted-text">Current console binding and session expiry.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <Cable size={18} strokeWidth={2} />
            </div>
          </div>
          <div className="dashboard-list">
            <div className="dashboard-row">
              <span>State</span>
              <strong data-testid="dashboard-c2-state">{connection ? 'connected' : 'disconnected'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Endpoint</span>
              <strong>{connection?.baseUrl ?? '-'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Token expires</span>
              <strong>{formatDateTime(connection?.expiresAt)}</strong>
            </div>
          </div>
          <Link className="secondary-button dashboard-panel-link" to="/settings">
            <Settings aria-hidden="true" size={15} strokeWidth={2} />
            <span>Settings</span>
          </Link>
        </section>

        <section className="workspace-panel dashboard-health-panel" aria-label="System health">
          <div className="panel-header">
            <div>
              <h2>System health</h2>
              <p className="muted-text">Readiness across local services and C2 connectivity.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <RefreshCw size={18} strokeWidth={2} />
            </div>
          </div>
          <div className="status-list">
            {healthRows.map((row) => <HealthStatusRow key={row.label} row={row} />)}
          </div>
          {readiness.kind === 'error' ? <p className="error-text">{readiness.message}</p> : null}
        </section>

        <section className="workspace-panel dashboard-tasks-panel" aria-label="Recent tasks">
          <div className="panel-header">
            <div>
              <h2>Recent tasks</h2>
              <p className="muted-text">Latest queued, running, completed, failed, and cancelled work.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <ListChecks size={18} strokeWidth={2} />
            </div>
          </div>
          <RecentTasks state={dashboard} />
        </section>

        <section className="workspace-panel dashboard-activity-panel" aria-label="Recent activity">
          <div className="panel-header">
            <div>
              <h2>Recent activity</h2>
              <p className="muted-text">Task and beacon events normalized for the Home feed.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <Activity size={18} strokeWidth={2} />
            </div>
          </div>
          <RecentActivity items={activityItems} state={dashboard} />
        </section>

        <section className="workspace-panel dashboard-actions-panel" aria-label="Quick actions">
          <div className="panel-header">
            <div>
              <h2>Quick actions</h2>
              <p className="muted-text">Common operator routes from the Home overview.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <TerminalSquare size={18} strokeWidth={2} />
            </div>
          </div>
          <div className="dashboard-action-grid">
            <Link className="primary-button" to="/beacons">
              <TerminalSquare aria-hidden="true" size={15} strokeWidth={2} />
              <span>New task</span>
            </Link>
            <Link className="secondary-button" to="/beacons?status=offline">
              <RadioTower aria-hidden="true" size={15} strokeWidth={2} />
              <span>Offline beacons</span>
            </Link>
            <Link className="secondary-button" to="/settings">
              <Settings aria-hidden="true" size={15} strokeWidth={2} />
              <span>Settings</span>
            </Link>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
