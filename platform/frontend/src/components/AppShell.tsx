import {
  Activity,
  Boxes,
  Check,
  ChevronDown,
  Crosshair,
  FolderKanban,
  Gauge,
  HeartPulse,
  Home,
  Layers3,
  ListChecks,
  LogIn,
  LogOut,
  Plug,
  RadioTower,
  Settings,
  ShieldCheck,
  Unplug,
} from 'lucide-react';
import { ReactNode, useEffect, useId, useMemo, useRef, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';

import {
  readProjectScopeSnapshot,
  subscribeProjectScopeChanged,
  writeActiveProjectId,
} from '../projectScopeStorage';
import { useAuth } from '../useAuth';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';

type ShellSection = 'beacons' | 'health' | 'home' | 'projects' | 'recon' | 'settings';

interface AppShellProps {
  children: ReactNode;
  description?: string;
  section: ShellSection;
  title: string;
  toolbar?: ReactNode;
  wide?: boolean;
}

interface PrimaryNavItem {
  enabled: boolean;
  icon: typeof Gauge;
  label: string;
  requiresC2?: boolean;
  shortLabel: string;
  to: string;
}

interface SubNavItem {
  enabled: boolean;
  icon: typeof Gauge;
  label: string;
  requiresC2?: boolean;
  to: string;
}

const primaryNav: PrimaryNavItem[] = [
  { label: 'Home', shortLabel: 'Home', to: '/home', icon: Home, enabled: true },
  { label: 'Projects', shortLabel: 'Projects', to: '/projects', icon: FolderKanban, enabled: true, requiresC2: true },
  { label: 'Recon', shortLabel: 'Recon', to: '/recon', icon: Crosshair, enabled: true, requiresC2: true },
  { label: 'Beacons', shortLabel: 'Beacons', to: '/beacons', icon: RadioTower, enabled: true, requiresC2: true },
  { label: 'Reporting', shortLabel: 'Reporting', to: '/reporting', icon: ListChecks, enabled: false, requiresC2: true },
  { label: 'Inventory', shortLabel: 'Inventory', to: '/inventory', icon: Boxes, enabled: false, requiresC2: true },
  { label: 'Assets', shortLabel: 'Assets', to: '/assets', icon: Layers3, enabled: false, requiresC2: true },
  { label: 'Settings', shortLabel: 'Settings', to: '/settings', icon: Settings, enabled: true },
];

const subNavBySection: Record<ShellSection, SubNavItem[]> = {
  health: [
    { label: 'Readiness', to: '/health', icon: HeartPulse, enabled: true },
    { label: 'Liveness', to: '/health/live', icon: Activity, enabled: false },
  ],
  beacons: [
    { label: 'Registry', to: '/beacons', icon: RadioTower, enabled: true, requiresC2: true },
  ],
  home: [
    { label: 'Overview', to: '/home', icon: Home, enabled: true },
  ],
  projects: [
    { label: 'Projects', to: '/projects', icon: FolderKanban, enabled: true, requiresC2: true },
  ],
  recon: [
    { label: 'Tools', to: '/recon', icon: Crosshair, enabled: true, requiresC2: true },
    { label: 'Runs', to: '/recon/runs', icon: ListChecks, enabled: false, requiresC2: true },
    { label: 'Activity', to: '/recon/activity', icon: Activity, enabled: false, requiresC2: true },
  ],
  settings: [
    { label: 'C2 Backend', to: '/settings', icon: Settings, enabled: true },
    { label: 'BFF', to: '/settings/bff', icon: Layers3, enabled: false },
    { label: 'Access', to: '/settings/access', icon: Settings, enabled: false },
  ],
};

const healthNav: PrimaryNavItem = {
  label: 'Health',
  shortLabel: 'Health',
  to: '/health',
  icon: HeartPulse,
  enabled: true,
};

function activeClass(baseClass: string, isActive: boolean) {
  return isActive ? `${baseClass} is-active` : baseClass;
}

function DisabledNavButton({
  children,
  className,
  disabledReason,
  label,
}: {
  children: ReactNode;
  className: string;
  disabledReason?: string;
  label: string;
}) {
  return (
    <button aria-disabled="true" className={className} disabled title={disabledReason ?? `${label} is planned`} type="button">
      {children}
    </button>
  );
}

function c2HostLabel(baseUrl: string): string {
  try {
    return new URL(baseUrl).host;
  } catch {
    return baseUrl.replace(/^https?:\/\//, '').replace(/\/+$/, '');
  }
}

export function AppShell({ children, description, section, title, toolbar, wide = false }: AppShellProps) {
  const { logout, session } = useAuth();
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const [projectScope, setProjectScope] = useState(() => readProjectScopeSnapshot());
  const [isProjectScopeOpen, setProjectScopeOpen] = useState(false);
  const projectScopeSelectorRef = useRef<HTMLDivElement | null>(null);
  const projectScopeMenuId = useId();
  const subNav = subNavBySection[section];
  const hasC2Connection = Boolean(connection);
  const HealthIcon = healthNav.icon;
  const C2StatusIcon = hasC2Connection ? Plug : Unplug;
  const realtimeLabel = {
    connected: 'Realtime Connected',
    connecting: 'Realtime Connecting',
    degraded: 'Realtime Degraded',
    disconnected: 'Realtime Disconnected',
    reconnecting: 'Realtime Reconnecting',
  }[realtime.status];
  const c2Host = connection ? c2HostLabel(connection.baseUrl) : '';
  const activeProject = useMemo(
    () => projectScope.projects.find((project) => project.id === projectScope.activeProjectId),
    [projectScope.activeProjectId, projectScope.projects],
  );

  useEffect(() => subscribeProjectScopeChanged(() => setProjectScope(readProjectScopeSnapshot())), []);

  useEffect(() => {
    if (!isProjectScopeOpen) {
      return undefined;
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (projectScopeSelectorRef.current?.contains(event.target as Node)) {
        return;
      }
      setProjectScopeOpen(false);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setProjectScopeOpen(false);
      }
    };

    window.addEventListener('pointerdown', handlePointerDown);
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isProjectScopeOpen]);

  function handleProjectScopeChange(projectId: string) {
    writeActiveProjectId(projectId);
    setProjectScope(readProjectScopeSnapshot());
    setProjectScopeOpen(false);
  }

  return (
    <div className="app-shell">
      <main className="shell-main">
        <header className="shell-topbar">
          <div className="shell-title-block">
            <div>
              <h1>{title}</h1>
              {description && <p>{description}</p>}
            </div>
          </div>

          <div className="shell-brand-banner" aria-hidden="true">
            <img src="/assets/xero-wordmark-topbar.png" alt="" />
          </div>

          <nav className="sub-nav" aria-label={`${title} sections`}>
            {subNav.map((item) => {
              const Icon = item.icon;
              const content = (
                <>
                  <Icon aria-hidden="true" size={16} strokeWidth={2} />
                  <span>{item.label}</span>
                </>
              );

              const isEnabled = item.enabled && (!item.requiresC2 || hasC2Connection);
              if (!isEnabled) {
                return (
                  <DisabledNavButton
                    className="sub-nav-tab sub-nav-tab--disabled"
                    disabledReason={item.requiresC2 && !hasC2Connection ? 'Connect a Xero C2 backend in Settings.' : undefined}
                    key={item.label}
                    label={item.label}
                  >
                    {content}
                  </DisabledNavButton>
                );
              }

              return (
                <NavLink className={({ isActive }) => activeClass('sub-nav-tab', isActive)} end key={item.label} to={item.to}>
                  {content}
                </NavLink>
              );
            })}
          </nav>

          <div className="shell-actions">
            {toolbar}

            {session ? (
              <>
                <div
                  className={`project-scope-selector ${activeProject ? 'project-scope-selector--active' : ''} ${isProjectScopeOpen ? 'is-open' : ''}`}
                  ref={projectScopeSelectorRef}
                >
                  <ShieldCheck aria-hidden="true" size={15} strokeWidth={2.2} />
                  <button
                    aria-controls={isProjectScopeOpen ? projectScopeMenuId : undefined}
                    aria-expanded={isProjectScopeOpen}
                    aria-haspopup="listbox"
                    aria-label="Active project scope"
                    className="project-scope-trigger"
                    disabled={projectScope.projects.length === 0}
                    onClick={() => setProjectScopeOpen((current) => !current)}
                    type="button"
                  >
                    <span className="project-scope-selector-copy">
                      <strong>Scope</strong>
                      <span className="project-scope-value">
                        {activeProject?.name ?? (projectScope.projects.length === 0 ? 'No projects' : 'Select project')}
                      </span>
                    </span>
                    <ChevronDown aria-hidden="true" className="project-scope-chevron" size={14} strokeWidth={2.2} />
                  </button>
                  {isProjectScopeOpen ? (
                    <div className="project-scope-menu" id={projectScopeMenuId} role="listbox">
                      <button
                        aria-selected={!activeProject}
                        className={`project-scope-option ${!activeProject ? 'is-selected' : ''}`}
                        onClick={() => handleProjectScopeChange('')}
                        role="option"
                        type="button"
                      >
                        <span className="project-scope-option-check">{!activeProject ? <Check aria-hidden="true" size={12} strokeWidth={2.4} /> : null}</span>
                        <span>Select project</span>
                      </button>
                      {projectScope.projects.map((project) => {
                        const isSelected = project.id === activeProject?.id;
                        return (
                          <button
                            aria-selected={isSelected}
                            className={`project-scope-option ${isSelected ? 'is-selected' : ''}`}
                            key={project.id}
                            onClick={() => handleProjectScopeChange(project.id)}
                            role="option"
                            type="button"
                          >
                            <span className="project-scope-option-check">
                              {isSelected ? <Check aria-hidden="true" size={12} strokeWidth={2.4} /> : null}
                            </span>
                            <span>{project.name}</span>
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
                <div
                  aria-label={realtimeLabel}
                  className={`realtime-status-pill realtime-status-pill--${realtime.status}`}
                  title={realtime.error || realtimeLabel}
                >
                  <RadioTower aria-hidden="true" size={15} strokeWidth={2.25} />
                  <span className="realtime-status-copy">
                    <strong>{realtimeLabel}</strong>
                    <span>
                      {realtime.activeBeaconCount} active / {realtime.beaconCount} total
                    </span>
                  </span>
                </div>
                <Link
                  aria-label={hasC2Connection ? `C2 Connected to ${c2Host}` : 'C2 Disconnected'}
                  className={`c2-status-button ${hasC2Connection ? 'c2-status-button--connected' : 'c2-status-button--disconnected'}`}
                  to="/settings"
                >
                  <C2StatusIcon aria-hidden="true" size={15} strokeWidth={2.25} />
                  <span className="c2-status-copy">
                    <strong>{hasC2Connection ? 'C2 Connected' : 'C2 Disconnected'}</strong>
                    {hasC2Connection && <span>{c2Host}</span>}
                  </span>
                </Link>
                <button className="shell-action-button" onClick={logout} type="button">
                  <LogOut aria-hidden="true" size={15} strokeWidth={2} />
                  <span>Log out</span>
                </button>
              </>
            ) : (
              <Link className="shell-action-button" to="/login">
                <LogIn aria-hidden="true" size={15} strokeWidth={2} />
                <span>Login</span>
              </Link>
            )}
          </div>
        </header>

        <div className={`shell-content ${wide ? 'shell-content--wide' : ''} page-enter`}>{children}</div>
      </main>

      <aside className="side-nav" aria-label="Primary">
        <nav className="side-nav-list">
          {primaryNav.map((item) => {
            const Icon = item.icon;
            const content = (
              <>
                <Icon aria-hidden="true" size={20} strokeWidth={2} />
                <span>{item.shortLabel}</span>
              </>
            );
            const isEnabled = item.enabled && (!item.requiresC2 || hasC2Connection);

            if (!isEnabled) {
              return (
                <DisabledNavButton
                  className="side-nav-tab side-nav-tab--disabled"
                  disabledReason={item.requiresC2 && !hasC2Connection ? 'Connect a Xero C2 backend in Settings.' : undefined}
                  key={item.label}
                  label={item.label}
                >
                  {content}
                </DisabledNavButton>
              );
            }

            return (
              <NavLink className={({ isActive }) => activeClass('side-nav-tab', isActive)} key={item.label} to={item.to}>
                {content}
              </NavLink>
            );
          })}
        </nav>
        <nav className="side-nav-utility" aria-label="System">
          <NavLink className={({ isActive }) => activeClass('side-nav-tab', isActive)} to={healthNav.to}>
            <HealthIcon aria-hidden="true" size={20} strokeWidth={2} />
            <span>{healthNav.shortLabel}</span>
          </NavLink>
        </nav>
      </aside>
    </div>
  );
}
