import {
  Check,
  ChevronDown,
  LogIn,
  LogOut,
  Plug,
  ShieldCheck,
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

export function AppShell({ children, description, section, title, toolbar, wide = false }: AppShellProps) {
  const { logout, session } = useAuth();
  const { connection } = useC2Connection();
  const [projectScope, setProjectScope] = useState(() => readProjectScopeSnapshot());
  const [isProjectScopeOpen, setProjectScopeOpen] = useState(false);
  const projectScopeSelectorRef = useRef<HTMLDivElement | null>(null);
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
                    onClick={() => setProjectScopeOpen((current) => !current)}
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
