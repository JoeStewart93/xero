import { useEffect, useRef, useState } from 'react';
import { Activity, Cable, ListChecks, RadioTower, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';

import {
  DashboardActivityItem,
  DashboardBeaconCounts,
  DashboardSummary,
  Task,
  getDashboardSummary,
} from '../api';
import { AppShell } from '../components/AppShell';
import { applyDashboardRealtimeEvent } from '../dashboardEvents';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';

type DashboardState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { data: DashboardSummary; kind: 'loaded' }
  | { kind: 'error'; message: string };

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
        <Link
          className="dashboard-task-row"
          key={task.id}
          to={`/beacons/${task.beacon_id}/commands?task_id=${encodeURIComponent(task.id)}`}
        >
          <div>
            <strong>{taskCommand(task)}</strong>
            <span>{task.module} on {task.beacon_id.slice(0, 8)}</span>
          </div>
          <span>{formatDateTime(taskTime(task))}</span>
          <strong className="dashboard-status-pill">{task.status}</strong>
        </Link>
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
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const [dashboard, setDashboard] = useState<DashboardState>({ kind: connection ? 'loading' : 'idle' });
  const appliedRealtimeEventId = useRef<string | null>(null);

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

  return (
    <AppShell description="C2 dashboard overview" section="home" title="Home" wide>
      <div className="dashboard-overview-grid">
        <section className="workspace-panel workspace-panel--flat dashboard-summary-panel" aria-label="Beacon summary">
          {dashboard.kind === 'loading' ? (
            <LoadingRows label="Loading beacon summary" />
          ) : (
            <div className="dashboard-kpi-strip">
              <span><strong data-testid="dashboard-total-beacons">{counts.total}</strong> total</span>
              <span><strong data-testid="dashboard-online-beacons">{counts.online}</strong> online</span>
              <span><strong data-testid="dashboard-offline-beacons">{counts.offline}</strong> offline</span>
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

        <section className="workspace-panel workspace-panel--flat dashboard-connection-panel" aria-label="C2 connection">
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
          <Link className="secondary-button dashboard-panel-link" to={connection ? '/settings/infrastructure' : '/settings'}>
            <Settings aria-hidden="true" size={15} strokeWidth={2} />
            <span>Settings</span>
          </Link>
        </section>

        <section className="workspace-panel workspace-panel--flat dashboard-tasks-panel" aria-label="Recent tasks">
          <h2>Recent tasks</h2>
          <div className="dashboard-panel-scroll">
            <RecentTasks state={dashboard} />
          </div>
        </section>

        <section className="workspace-panel workspace-panel--flat dashboard-activity-panel" aria-label="Recent activity">
          <h2>Recent activity</h2>
          <div className="dashboard-panel-scroll">
            <RecentActivity items={activityItems} state={dashboard} />
          </div>
        </section>
      </div>
    </AppShell>
  );
}
