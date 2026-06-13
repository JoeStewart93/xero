import { useEffect, useMemo, useState } from 'react';
import { Cable, Clock3, Fingerprint, Gauge, LockKeyhole, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { getSectionDefinition, getSectionTab } from '../navigation';
import { GLOBAL_SCOPE_LABEL, readProjectScopeSnapshot, subscribeProjectScopeChanged } from '../projectScopeStorage';
import { useC2Connection } from '../useC2Connection';
import { TrafficProfilesModal } from './TrafficProfilesPage';

const patternRows = [
  {
    detail: 'Sleep, jitter, and padding values from assigned profiles.',
    name: 'Beacon cadence',
    status: 'Profile driven',
  },
  {
    detail: 'Frame, poll, register, and WebSocket paths for runtime check-ins.',
    name: 'Request paths',
    status: 'Template mapped',
  },
  {
    detail: 'User-Agent and custom headers served with the active profile.',
    name: 'HTTP identity',
    status: 'Mutable',
  },
];

export function TrafficPatternsPage() {
  const definition = getSectionDefinition('payloads');
  const activeTab = getSectionTab('payloads', 'traffic-patterns');
  const { connection } = useC2Connection();
  const [searchParams, setSearchParams] = useSearchParams();
  const [projectScope, setProjectScope] = useState(() => readProjectScopeSnapshot());
  const activeProject = useMemo(
    () => projectScope.projects.find((project) => project.id === projectScope.activeProjectId) ?? null,
    [projectScope.activeProjectId, projectScope.projects],
  );
  const isProfilesOpen = searchParams.get('profiles') === '1' || searchParams.get('modal') === 'profiles';

  useEffect(() => subscribeProjectScopeChanged(() => setProjectScope(readProjectScopeSnapshot())), []);

  function openProfiles(): void {
    const next = new URLSearchParams(searchParams);
    next.set('profiles', '1');
    setSearchParams(next);
  }

  function closeProfiles(): void {
    const next = new URLSearchParams(searchParams);
    next.delete('profiles');
    if (next.get('modal') === 'profiles') {
      next.delete('modal');
    }
    setSearchParams(next, { replace: true });
  }

  return (
    <AppShell description={definition.description} section="payloads" title={definition.label} wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="traffic-patterns-grid">
          <section className="workspace-panel traffic-patterns-primary-panel" aria-label="Traffic Patterns">
            <div className="panel-header">
              <div>
                <h2>{activeTab.label}</h2>
                <p className="muted-text">Runtime transport shape for beacon check-ins and task exchange.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <Cable size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="traffic-patterns-toolbar">
              <div className="traffic-patterns-stat">
                <Clock3 aria-hidden="true" size={15} strokeWidth={2.1} />
                <span>Cadence</span>
                <strong>profile</strong>
              </div>
              <div className="traffic-patterns-stat">
                <Gauge aria-hidden="true" size={15} strokeWidth={2.1} />
                <span>Jitter</span>
                <strong>bounded</strong>
              </div>
              <button className="primary-button" onClick={openProfiles} type="button">
                <SlidersHorizontal aria-hidden="true" size={15} strokeWidth={2.1} />
                <span>Manage profiles</span>
              </button>
            </div>

            {!activeProject ? (
              <div className="stub-lock-strip" data-testid="project-required-stub">
                <LockKeyhole aria-hidden="true" size={17} strokeWidth={2} />
                <div>
                  <strong>Active project required.</strong>
                  <span>Select or activate a project before applying scoped traffic patterns.</span>
                </div>
              </div>
            ) : null}

            <div className="stub-table-shell traffic-patterns-table">
              <div className="stub-table-head">
                <span>Name</span>
                <span>Status</span>
                <span>Detail</span>
              </div>
              {patternRows.map((row) => (
                <div className="stub-table-row" key={row.name}>
                  <strong>{row.name}</strong>
                  <span className="stub-status">{row.status}</span>
                  <span>{row.detail}</span>
                </div>
              ))}
            </div>
          </section>

          <aside className="workspace-panel traffic-patterns-context-panel" aria-label="Traffic Patterns context">
            <div className="panel-header">
              <div>
                <h2>Context</h2>
                <p className="muted-text">Profile scope and connected transport state.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <ShieldCheck size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="dashboard-list">
              <div className="dashboard-row">
                <span>C2 backend</span>
                <strong>{connection.status}</strong>
              </div>
              <div className="dashboard-row">
                <span>Active scope</span>
                <strong>{activeProject?.name ?? GLOBAL_SCOPE_LABEL}</strong>
              </div>
              <div className="dashboard-row">
                <span>Profile library</span>
                <strong>modal</strong>
              </div>
              <div className="dashboard-row">
                <span>Transport</span>
                <strong>{connection.baseUrl}</strong>
              </div>
            </div>

            <div className="traffic-patterns-mini-card">
              <Fingerprint aria-hidden="true" size={16} strokeWidth={2.1} />
              <div>
                <strong>Assigned at beacon profile level</strong>
                <span>Templates remain reusable across operators and active project scopes.</span>
              </div>
            </div>
          </aside>
        </div>
      )}

      {isProfilesOpen ? <TrafficProfilesModal onClose={closeProfiles} /> : null}
    </AppShell>
  );
}
