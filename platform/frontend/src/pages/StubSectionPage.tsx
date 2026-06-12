import { useEffect, useMemo, useState } from 'react';
import { Boxes, FileArchive, KeyRound, LockKeyhole, Play, ShieldCheck, TerminalSquare } from 'lucide-react';

import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { ModalShell } from '../components/ModalShell';
import { getSectionDefinition, getSectionTab, ShellSection } from '../navigation';
import { GLOBAL_SCOPE_LABEL, readProjectScopeSnapshot, subscribeProjectScopeChanged } from '../projectScopeStorage';
import { useC2Connection } from '../useC2Connection';

interface StubSectionPageProps {
  section: ShellSection;
  tabId?: string;
}

interface StubModalCopy {
  action: string;
  title: string;
  variant?: 'center' | 'side';
}

const modalCopyBySection: Partial<Record<ShellSection, StubModalCopy>> = {
  assets: { action: 'Open asset detail', title: 'Asset detail', variant: 'side' },
  beacons: { action: 'Open task modal', title: 'Task execution' },
  exploits: { action: 'View exploit details', title: 'Exploit configuration' },
  home: { action: 'Open quick action', title: 'Quick action' },
  loot: { action: 'Add credential', title: 'Credential manual entry' },
  payloads: { action: 'Open builder', title: 'Payload builder' },
  projects: { action: 'Open scope action', title: 'Project scope action' },
  recon: { action: 'Configure tool', title: 'Recon tool configuration' },
  reports: { action: 'Open report builder', title: 'Report builder' },
  settings: { action: 'Open settings modal', title: 'Settings management' },
};

function settingsModalCopy(tabId: string): StubModalCopy {
  if (tabId === 'plugins') {
    return { action: 'Open plugin manager', title: 'Plugin manager' };
  }
  if (tabId === 'access') {
    return { action: 'Open user management', title: 'User management' };
  }
  return modalCopyBySection.settings ?? { action: 'Open settings modal', title: 'Settings management' };
}

function modalCopy(section: ShellSection, tabId: string): StubModalCopy {
  if (section === 'settings') {
    return settingsModalCopy(tabId);
  }
  return modalCopyBySection[section] ?? { action: 'Open task modal', title: 'Task execution' };
}

function plannedRows(section: ShellSection, sectionLabel: string, tabLabel: string, activeProjectName: string | null) {
  if (section === 'beacons' && tabLabel === 'Sessions') {
    return [
      {
        detail: 'Active and recent shell, file browser, and Windows Registry Explorer interactions will appear here.',
        name: 'Session workspaces',
        status: 'Planned',
      },
      {
        detail: 'Each session remains tied to its beacon, operator activity, and future audit history.',
        name: 'Session history',
        status: 'Planned',
      },
      {
        detail: 'UI shell only; no operation is dispatched from this surface.',
        name: 'Operator action',
        status: 'Locked',
      },
    ];
  }

  return [
    {
      detail: activeProjectName ?? `${GLOBAL_SCOPE_LABEL} scope is active. Select a project before scoped execution.`,
      name: `${tabLabel} workspace`,
      status: activeProjectName ? 'Scoped' : 'Project required',
    },
    {
      detail: `${sectionLabel} implementation is reserved for its owning feature spec.`,
      name: 'Backend workflow',
      status: 'Planned',
    },
    {
      detail: 'UI shell only; no operation is dispatched from this surface.',
      name: 'Operator action',
      status: 'Locked',
    },
  ];
}

export function StubSectionPage({ section, tabId }: StubSectionPageProps) {
  const definition = getSectionDefinition(section);
  const activeTab = getSectionTab(section, tabId);
  const copy = modalCopy(section, activeTab.id);
  const ActiveTabIcon = activeTab.icon;
  const { connection } = useC2Connection();
  const [projectScope, setProjectScope] = useState(() => readProjectScopeSnapshot());
  const [modalOpen, setModalOpen] = useState(false);
  const activeProject = useMemo(
    () => projectScope.projects.find((project) => project.id === projectScope.activeProjectId) ?? null,
    [projectScope.activeProjectId, projectScope.projects],
  );
  const needsC2 = definition.requiresC2 || activeTab.requiresC2;
  const needsProject = definition.requiresProject;
  const rows = plannedRows(section, definition.label, activeTab.label, activeProject?.name ?? null);

  useEffect(() => subscribeProjectScopeChanged(() => setProjectScope(readProjectScopeSnapshot())), []);

  return (
    <AppShell description={definition.description} section={section} title={definition.label} wide>
      {needsC2 && !connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="stub-workspace-grid">
          <section className="workspace-panel stub-primary-panel" aria-label={`${definition.label} ${activeTab.label}`}>
            <div className="panel-header">
              <div>
                <h2>{activeTab.label}</h2>
                <p className="muted-text">{definition.description}</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <ActiveTabIcon size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="stub-toolbar">
              <label className="stub-search">
                Search
                <input disabled placeholder={`${activeTab.label.toLowerCase()} search is planned`} />
              </label>
              <button className="primary-button" onClick={() => setModalOpen(true)} type="button">
                <Play aria-hidden="true" size={14} strokeWidth={2.2} />
                <span>{copy.action}</span>
              </button>
            </div>

            {needsProject && !activeProject ? (
              <div className="stub-lock-strip" data-testid="project-required-stub">
                <LockKeyhole aria-hidden="true" size={17} strokeWidth={2} />
                <div>
                  <strong>Active project required.</strong>
                  <span>Select or activate a project before this workspace can run scoped actions.</span>
                </div>
              </div>
            ) : null}

            <div className="stub-table-shell">
              <div className="stub-table-head">
                <span>Name</span>
                <span>Status</span>
                <span>Detail</span>
              </div>
              {rows.map((row) => (
                <div className="stub-table-row" key={row.name}>
                  <strong>{row.name}</strong>
                  <span className={row.status === 'Locked' || row.status === 'Project required' ? 'stub-status stub-status--locked' : 'stub-status'}>
                    {row.status}
                  </span>
                  <span>{row.detail}</span>
                </div>
              ))}
            </div>
          </section>

          <aside className="workspace-panel stub-context-panel" aria-label={`${definition.label} context`}>
            <div className="panel-header">
              <div>
                <h2>Context</h2>
                <p className="muted-text">Shell state for future workflow wiring.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <ShieldCheck size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="dashboard-list">
              <div className="dashboard-row">
                <span>C2 backend</span>
                <strong>{connection ? 'connected' : 'disconnected'}</strong>
              </div>
              <div className="dashboard-row">
                <span>Active scope</span>
                <strong>{activeProject?.name ?? GLOBAL_SCOPE_LABEL}</strong>
              </div>
              <div className="dashboard-row">
                <span>Surface</span>
                <strong>{activeTab.label}</strong>
              </div>
            </div>
          </aside>
        </div>
      )}

      {modalOpen ? (
        <ModalShell
          ariaLabel={`${copy.title} stub`}
          onClose={() => setModalOpen(false)}
          subtitle={`${definition.label} / ${activeTab.label}`}
          title={copy.title}
          variant={copy.variant}
        >
          <div className="stub-modal-body">
            <div className="stub-modal-action-grid">
              <div>
                <TerminalSquare aria-hidden="true" size={16} strokeWidth={2} />
                <strong>Action plan</strong>
                <span>Configure arguments, target scope, and output handling in a later feature.</span>
              </div>
              <div>
                <Boxes aria-hidden="true" size={16} strokeWidth={2} />
                <strong>Scope binding</strong>
                <span>{activeProject ? `Bound to ${activeProject.name}.` : 'Requires an active project.'}</span>
              </div>
              <div>
                <FileArchive aria-hidden="true" size={16} strokeWidth={2} />
                <strong>Output</strong>
                <span>Results, artifacts, notes, or exports will land in their owning workspace.</span>
              </div>
              <div>
                <KeyRound aria-hidden="true" size={16} strokeWidth={2} />
                <strong>Authorization</strong>
                <span>No operation is sent while this surface is stubbed.</span>
              </div>
            </div>
            <div className="button-row">
              <button className="primary-button" disabled type="button">
                Execute planned action
              </button>
              <button className="secondary-button" onClick={() => setModalOpen(false)} type="button">
                Close
              </button>
            </div>
          </div>
        </ModalShell>
      ) : null}
    </AppShell>
  );
}
