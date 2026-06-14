import {
  Bell,
  Boxes,
  Check,
  ChevronDown,
  Crosshair,
  FolderPlus,
  LogIn,
  LogOut,
  Plug,
  Plus,
  Settings,
  ShieldCheck,
  TerminalSquare,
  Unplug,
} from 'lucide-react';
import { ReactNode, useEffect, useId, useMemo, useRef, useState } from 'react';
import { Link, NavLink } from 'react-router-dom';

import { getSectionDefinition, healthNav, primaryNav, ShellSection } from '../navigation';
import {
  GLOBAL_SCOPE_LABEL,
  readProjectScopeSnapshot,
  subscribeProjectScopeChanged,
  writeActiveProjectId,
} from '../projectScopeStorage';
import { useAuth } from '../useAuth';
import { useC2Connection } from '../useC2Connection';

interface AppShellProps {
  children: ReactNode;
  description?: string;
  section: ShellSection;
  title: string;
  toolbar?: ReactNode;
  wide?: boolean;
}

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
    <button
      aria-disabled="true"
      aria-label={label}
      className={className}
      disabled
      title={disabledReason ?? `${label} is planned`}
      type="button"
    >
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

const createResourceActions = [
  {
    description: 'Define an engagement container.',
    icon: FolderPlus,
    label: 'Project',
    to: '/projects?create=1',
  },
  {
    description: 'Open beacon tasking.',
    icon: TerminalSquare,
    label: 'Task',
    to: '/beacons?module=shell',
  },
  {
    description: 'Add target scope.',
    icon: Crosshair,
    label: 'Target',
    to: '/projects/scope',
  },
  {
    description: 'Open inventory resources.',
    icon: Boxes,
    label: 'Resource',
    to: '/assets',
  },
];

export function AppShell({ children, description, section, title, toolbar, wide = false }: AppShellProps) {
  const { logout, session } = useAuth();
  const { connection } = useC2Connection();
  const [projectScope, setProjectScope] = useState(() => readProjectScopeSnapshot());
  const [isCreateMenuOpen, setCreateMenuOpen] = useState(false);
  const [isNotificationMenuOpen, setNotificationMenuOpen] = useState(false);
  const [isProjectScopeOpen, setProjectScopeOpen] = useState(false);
  const createMenuRef = useRef<HTMLDivElement | null>(null);
  const notificationMenuRef = useRef<HTMLDivElement | null>(null);
  const projectScopeSelectorRef = useRef<HTMLDivElement | null>(null);
  const createMenuId = useId();
  const notificationMenuId = useId();
  const projectScopeMenuId = useId();
  const subNav = getSectionDefinition(section).tabs;
  const hasC2Connection = Boolean(connection);
  const HealthIcon = healthNav.icon;
  const C2StatusIcon = hasC2Connection ? Plug : Unplug;
  const c2Host = connection ? c2HostLabel(connection.baseUrl) : '';
  const activeProject = useMemo(
    () => projectScope.projects.find((project) => project.id === projectScope.activeProjectId),
    [projectScope.activeProjectId, projectScope.projects],
  );
  const scopeLabel = activeProject?.name ?? GLOBAL_SCOPE_LABEL;
  const scopeTitle = `Scope: ${scopeLabel}`;
  const c2Title = hasC2Connection ? `C2 Connected: ${c2Host}` : 'C2 Disconnected';

  useEffect(() => subscribeProjectScopeChanged(() => setProjectScope(readProjectScopeSnapshot())), []);

  useEffect(() => {
    if (!isCreateMenuOpen && !isNotificationMenuOpen) {
      return undefined;
    }

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (isCreateMenuOpen && !createMenuRef.current?.contains(target)) {
        setCreateMenuOpen(false);
      }
      if (isNotificationMenuOpen && !notificationMenuRef.current?.contains(target)) {
        setNotificationMenuOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setCreateMenuOpen(false);
        setNotificationMenuOpen(false);
      }
    };

    window.addEventListener('pointerdown', handlePointerDown);
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('pointerdown', handlePointerDown);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isCreateMenuOpen, isNotificationMenuOpen]);

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
          <div className="shell-left-stack">
            <h1 className="sr-only">{title}</h1>
            {description && <p className="sr-only">{description}</p>}

            <nav className="sub-nav" aria-label={`${title} sections`}>
              {subNav.map((item) => {
                const Icon = item.icon;
                const content = (
                  <>
                    <Icon aria-hidden="true" size={16} strokeWidth={2} />
                    <span>{item.label}</span>
                  </>
                );

                const isEnabled = item.enabled;
                if (!isEnabled) {
                  return (
                    <DisabledNavButton
                      className="sub-nav-tab sub-nav-tab--disabled"
                      key={item.label}
                      label={item.label}
                    >
                      {content}
                    </DisabledNavButton>
                  );
                }

                return (
                  <NavLink
                    aria-label={item.label}
                    className={({ isActive }) => activeClass('sub-nav-tab', isActive)}
                    end
                    key={item.label}
                    title={item.label}
                    to={item.to}
                  >
                    {content}
                  </NavLink>
                );
              })}
            </nav>
          </div>

          <div className="shell-brand-banner" aria-hidden="true">
            <img src="/assets/xero-wordmark-topbar.png" alt="" />
          </div>

          <div className="shell-actions">
            {toolbar}

            {session ? (
              <>
                <div className={`shell-create-menu ${isCreateMenuOpen ? 'is-open' : ''}`} ref={createMenuRef}>
                  <button
                    aria-controls={isCreateMenuOpen ? createMenuId : undefined}
                    aria-expanded={isCreateMenuOpen}
                    aria-haspopup="menu"
                    aria-label="Create resource"
                    className="shell-action-button shell-action-button--icon"
                    onClick={() => {
                      setCreateMenuOpen((current) => !current);
                      setNotificationMenuOpen(false);
                      setProjectScopeOpen(false);
                    }}
                    title="Create resource"
                    type="button"
                  >
                    <Plus aria-hidden="true" size={15} strokeWidth={2.2} />
                    <span>New</span>
                  </button>
                  {isCreateMenuOpen ? (
                    <div aria-label="Create resource" className="shell-dropdown-menu shell-create-menu-panel" id={createMenuId} role="menu">
                      <div className="shell-dropdown-head">
                        <strong>Create</strong>
                        <span>{scopeLabel}</span>
                      </div>
                      <div className="shell-dropdown-list">
                        {createResourceActions.map((action) => {
                          const Icon = action.icon;
                          return (
                            <Link
                              className="shell-dropdown-option"
                              key={action.label}
                              onClick={() => setCreateMenuOpen(false)}
                              role="menuitem"
                              to={action.to}
                            >
                              <Icon aria-hidden="true" size={15} strokeWidth={2.1} />
                              <span>
                                <strong>{action.label}</strong>
                                <small>{action.description}</small>
                              </span>
                            </Link>
                          );
                        })}
                      </div>
                    </div>
                  ) : null}
                </div>
                <div
                  className={`project-scope-selector project-scope-selector--active ${isProjectScopeOpen ? 'is-open' : ''}`}
                  ref={projectScopeSelectorRef}
                  title={scopeTitle}
                >
                  <ShieldCheck aria-hidden="true" size={15} strokeWidth={2.2} />
                  <button
                    aria-controls={isProjectScopeOpen ? projectScopeMenuId : undefined}
                    aria-expanded={isProjectScopeOpen}
                    aria-haspopup="listbox"
                    aria-label="Active project scope"
                    className="project-scope-trigger"
                    onClick={() => {
                      setProjectScopeOpen((current) => !current);
                      setCreateMenuOpen(false);
                      setNotificationMenuOpen(false);
                    }}
                    title={scopeTitle}
                    type="button"
                  >
                    <span className="project-scope-selector-copy">
                      <strong>Scope</strong>
                      <span className="project-scope-value">{scopeLabel}</span>
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
                        <span>{GLOBAL_SCOPE_LABEL}</span>
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
                <Link
                  aria-label={hasC2Connection ? `C2 Connected to ${c2Host}` : 'C2 Disconnected'}
                  className={`c2-status-button ${hasC2Connection ? 'c2-status-button--connected' : 'c2-status-button--disconnected'}`}
                  title={c2Title}
                  to="/settings"
                >
                  <C2StatusIcon aria-hidden="true" size={15} strokeWidth={2.25} />
                  <span className="c2-status-copy">
                    <strong>{hasC2Connection ? 'C2 Connected' : 'C2 Disconnected'}</strong>
                    {hasC2Connection && <span>{c2Host}</span>}
                  </span>
                </Link>
                <div className={`shell-notification-menu ${isNotificationMenuOpen ? 'is-open' : ''}`} ref={notificationMenuRef}>
                  <button
                    aria-controls={isNotificationMenuOpen ? notificationMenuId : undefined}
                    aria-expanded={isNotificationMenuOpen}
                    aria-haspopup="menu"
                    aria-label="Notifications"
                    className="shell-action-button shell-action-button--icon"
                    onClick={() => {
                      setNotificationMenuOpen((current) => !current);
                      setCreateMenuOpen(false);
                      setProjectScopeOpen(false);
                    }}
                    title="Notifications"
                    type="button"
                  >
                    <Bell aria-hidden="true" size={15} strokeWidth={2.1} />
                    <span>Notifications</span>
                  </button>
                  {isNotificationMenuOpen ? (
                    <aside aria-label="Notifications" className="shell-dropdown-menu shell-notification-panel" id={notificationMenuId} role="menu">
                      <div className="shell-dropdown-head">
                        <strong>Notifications</strong>
                        <Link onClick={() => setNotificationMenuOpen(false)} role="menuitem" to="/settings/notifications">
                          Manage
                        </Link>
                      </div>
                      <div className="shell-notification-empty">
                        <Bell aria-hidden="true" size={16} strokeWidth={2.1} />
                        <span>No notifications</span>
                      </div>
                      <Link className="shell-dropdown-footer" onClick={() => setNotificationMenuOpen(false)} role="menuitem" to="/settings/notifications">
                        <Settings aria-hidden="true" size={14} strokeWidth={2.1} />
                        <span>Manage notifications</span>
                      </Link>
                    </aside>
                  ) : null}
                </div>
                <button aria-label="Log out" className="shell-action-button" onClick={logout} title="Log out" type="button">
                  <LogOut aria-hidden="true" size={15} strokeWidth={2} />
                  <span>Log out</span>
                </button>
              </>
            ) : (
              <Link aria-label="Login" className="shell-action-button" title="Login" to="/login">
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
            const isEnabled = item.enabled;

            if (!isEnabled) {
              return (
                <DisabledNavButton
                  className="side-nav-tab side-nav-tab--disabled"
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
