import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  FolderKanban,
  Globe2,
  Network,
  Plus,
  Power,
  ShieldCheck,
  Trash2,
} from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { ModalShell } from '../components/ModalShell';
import {
  GLOBAL_SCOPE_LABEL,
  createLocalId,
  readActiveProjectId,
  readProjectScopeSnapshot,
  readProjects,
  subscribeProjectScopeChanged,
  writeActiveProjectId,
  writeProjects,
} from '../projectScopeStorage';
import type { DiscoveryProject, ProjectTarget, TargetType } from '../projectScopeStorage';
import { useC2Connection } from '../useC2Connection';

type TargetDetectionResult =
  | { error: string; target?: never }
  | { error?: never; target: Omit<ProjectTarget, 'id'> };

const IPV4_CANDIDATE_PATTERN = /^\d{1,3}(?:\.\d{1,3}){3}$/;

function isValidIpv4(value: string): boolean {
  if (!IPV4_CANDIDATE_PATTERN.test(value)) {
    return false;
  }

  return value.split('.').every((octet) => {
    if (octet.length > 1 && octet.startsWith('0')) {
      return false;
    }
    const parsed = Number(octet);
    return Number.isInteger(parsed) && parsed >= 0 && parsed <= 255;
  });
}

function looksLikeIpv4(value: string): boolean {
  return /^\d+(?:\.\d+){1,}$/.test(value);
}

function isValidDomain(value: string): boolean {
  if (value.length > 253 || value.includes('..') || !value.includes('.')) {
    return false;
  }

  const labels = value.split('.');
  const topLevelDomain = labels.at(-1) ?? '';
  if (topLevelDomain.length < 2 || !/[a-z]/.test(topLevelDomain)) {
    return false;
  }

  return labels.every((label) => {
    if (label.length < 1 || label.length > 63) {
      return false;
    }
    return /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label);
  });
}

function detectTarget(rawValue: string): TargetDetectionResult {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return { error: 'Enter a domain or IPv4 address.' };
  }

  if (/\s/.test(trimmed) || trimmed.includes('/') || trimmed.includes(':')) {
    return { error: 'Enter only a hostname or IPv4 address, without protocol, path, port, or spaces.' };
  }

  const normalized = trimmed.toLowerCase().replace(/\.$/, '');
  if (isValidIpv4(normalized)) {
    return { target: { type: 'ip', value: normalized } };
  }

  if (looksLikeIpv4(normalized)) {
    return { error: 'Enter a valid IPv4 address. Each octet must be between 0 and 255.' };
  }

  if (isValidDomain(normalized)) {
    return { target: { type: 'domain', value: normalized } };
  }

  return { error: 'Enter a valid dotted domain or IPv4 address.' };
}

function targetTypeLabel(type: TargetType): string {
  return type === 'ip' ? 'IP address' : 'Domain';
}

function countTargets(project?: DiscoveryProject, type?: TargetType): number {
  if (!project) {
    return 0;
  }

  return type ? project.targets.filter((target) => target.type === type).length : project.targets.length;
}

function hasDuplicateTarget(targets: ProjectTarget[], detectedTarget: Omit<ProjectTarget, 'id'>): boolean {
  return targets.some((target) => (
    target.type === detectedTarget.type && target.value.toLowerCase() === detectedTarget.value.toLowerCase()
  ));
}

function targetIcon(type: TargetType) {
  return type === 'domain' ? Globe2 : Network;
}

function TargetList({
  emptyLabel,
  onRemove,
  targets,
}: {
  emptyLabel: string;
  onRemove?: (targetId: string) => void;
  targets: ProjectTarget[];
}) {
  if (targets.length === 0) {
    return <div className="project-target-empty">{emptyLabel}</div>;
  }

  return (
    <div className="project-target-list">
      {targets.map((target) => {
        const Icon = targetIcon(target.type);
        return (
          <div className="project-target-row" key={target.id}>
            <Icon aria-hidden="true" size={14} strokeWidth={2} />
            <span>{target.value}</span>
            {onRemove ? (
              <button aria-label={`Remove ${target.value}`} onClick={() => onRemove(target.id)} type="button">
                <Trash2 aria-hidden="true" size={14} strokeWidth={2} />
              </button>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function ProjectsPage() {
  const { connection } = useC2Connection();
  const [searchParams, setSearchParams] = useSearchParams();
  const [projects, setProjects] = useState<DiscoveryProject[]>(() => readProjects());
  const [activeProjectId, setActiveProjectId] = useState(() => readActiveProjectId(readProjects()));
  const [managingProjectId, setManagingProjectId] = useState('');
  const [isCreateWizardOpen, setCreateWizardOpen] = useState(false);
  const [createStep, setCreateStep] = useState(0);
  const [draftName, setDraftName] = useState('');
  const [draftTargets, setDraftTargets] = useState<ProjectTarget[]>([]);
  const [draftTargetValue, setDraftTargetValue] = useState('');
  const [projectError, setProjectError] = useState('');
  const [targetError, setTargetError] = useState('');
  const [manageTargetValue, setManageTargetValue] = useState('');
  const [pendingDeleteProject, setPendingDeleteProject] = useState<DiscoveryProject | null>(null);
  const activeProjectIdRef = useRef(activeProjectId);
  const managingProjectIdRef = useRef(managingProjectId);

  const activeProject = useMemo(() => projects.find((project) => project.id === activeProjectId), [activeProjectId, projects]);
  const managingProject = useMemo(
    () => projects.find((project) => project.id === managingProjectId) ?? null,
    [managingProjectId, projects],
  );
  const activeScopeName = activeProject?.name ?? GLOBAL_SCOPE_LABEL;
  const activeScopeTargets = activeProject ? String(countTargets(activeProject)) : 'Unscoped';
  const createRequested = searchParams.get('create') === '1';

  useEffect(() => {
    activeProjectIdRef.current = activeProjectId;
  }, [activeProjectId]);

  useEffect(() => {
    managingProjectIdRef.current = managingProjectId;
  }, [managingProjectId]);

  useEffect(() => {
    if (createRequested) {
      setCreateWizardOpen(true);
    }
  }, [createRequested]);

  useEffect(
    () =>
      subscribeProjectScopeChanged(() => {
        const snapshot = readProjectScopeSnapshot();
        const managedProjectStillExists = snapshot.projects.some((project) => project.id === managingProjectIdRef.current);

        setProjects(snapshot.projects);
        setActiveProjectId(snapshot.activeProjectId);
        activeProjectIdRef.current = snapshot.activeProjectId;

        if (!managedProjectStillExists) {
          managingProjectIdRef.current = '';
          setManagingProjectId('');
        }
      }),
    [],
  );

  function persistProjects(nextProjects: DiscoveryProject[]) {
    setProjects(nextProjects);
    writeProjects(nextProjects);
  }

  function closeCreateWizard(): void {
    setCreateWizardOpen(false);
    setCreateStep(0);
    setDraftName('');
    setDraftTargets([]);
    setDraftTargetValue('');
    setProjectError('');
    setTargetError('');
    const next = new URLSearchParams(searchParams);
    next.delete('create');
    setSearchParams(next, { replace: true });
  }

  function openManageProject(projectId: string): void {
    setManagingProjectId(projectId);
    setTargetError('');
    setProjectError('');
    setManageTargetValue('');
  }

  function handleToggleProjectScope(projectId: string) {
    if (projectId === activeProjectId) {
      setActiveProjectId('');
      writeActiveProjectId('');
      return;
    }

    setActiveProjectId(projectId);
    writeActiveProjectId(projectId);
  }

  function handleAddDraftTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const detection = detectTarget(draftTargetValue);
    if (detection.error || !detection.target) {
      setTargetError(detection.error ?? 'Enter a valid target.');
      return;
    }
    if (hasDuplicateTarget(draftTargets, detection.target)) {
      setTargetError(`${detection.target.value} is already in this project.`);
      return;
    }
    setDraftTargets((current) => [...current, { id: createLocalId('target'), ...detection.target }]);
    setDraftTargetValue('');
    setTargetError('');
  }

  function handleAddManagedTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!managingProject) {
      return;
    }
    const detection = detectTarget(manageTargetValue);
    if (detection.error || !detection.target) {
      setTargetError(detection.error ?? 'Enter a valid target.');
      return;
    }
    if (hasDuplicateTarget(managingProject.targets, detection.target)) {
      setTargetError(`${detection.target.value} is already in this project.`);
      return;
    }
    persistProjects(projects.map((project) => (
      project.id === managingProject.id
        ? { ...project, targets: [...project.targets, { id: createLocalId('target'), ...detection.target }] }
        : project
    )));
    setManageTargetValue('');
    setTargetError('');
  }

  function handleRemoveManagedTarget(targetId: string) {
    if (!managingProject) {
      return;
    }
    persistProjects(projects.map((project) => (
      project.id === managingProject.id
        ? { ...project, targets: project.targets.filter((target) => target.id !== targetId) }
        : project
    )));
  }

  function handleCreateProject() {
    const name = draftName.trim();
    if (!name) {
      setProjectError('Project name is required.');
      setCreateStep(0);
      return;
    }
    if (projects.some((project) => project.name.toLowerCase() === name.toLowerCase())) {
      setProjectError('A project with this name already exists.');
      setCreateStep(0);
      return;
    }

    const project: DiscoveryProject = {
      id: createLocalId('project'),
      name,
      targets: draftTargets,
    };
    persistProjects([...projects, project]);
    closeCreateWizard();
    openManageProject(project.id);
  }

  function handleRenameProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!managingProject) {
      return;
    }
    const form = new FormData(event.currentTarget);
    const name = String(form.get('projectName') ?? '').trim();
    if (!name) {
      setProjectError('Project name is required.');
      return;
    }
    if (projects.some((project) => project.id !== managingProject.id && project.name.toLowerCase() === name.toLowerCase())) {
      setProjectError('A project with this name already exists.');
      return;
    }
    persistProjects(projects.map((project) => project.id === managingProject.id ? { ...project, name } : project));
    setProjectError('');
  }

  function handleConfirmDeleteProject() {
    if (!pendingDeleteProject) {
      return;
    }

    const deletedProjectId = pendingDeleteProject.id;
    const nextProjects = projects.filter((project) => project.id !== deletedProjectId);
    const nextActiveProjectId = activeProjectId === deletedProjectId ? '' : activeProjectId;

    setProjects(nextProjects);
    setActiveProjectId(nextActiveProjectId);
    if (managingProjectId === deletedProjectId) {
      setManagingProjectId('');
    }
    activeProjectIdRef.current = nextActiveProjectId;
    managingProjectIdRef.current = managingProjectId === deletedProjectId ? '' : managingProjectId;
    writeProjects(nextProjects);
    if (activeProjectId === deletedProjectId) {
      writeActiveProjectId('');
    }
    setPendingDeleteProject(null);
    setProjectError('');
    setTargetError('');
  }

  function renderCreateStep() {
    if (createStep === 0) {
      return (
        <div className="project-wizard-step">
          <label>
            Project name
            <input
              autoFocus
              onChange={(event) => setDraftName(event.target.value)}
              placeholder="acme-external-scope"
              value={draftName}
            />
          </label>
          <p className="field-hint">Use the project name for the engagement or authorized test boundary.</p>
        </div>
      );
    }

    if (createStep === 1) {
      return (
        <div className="project-wizard-step">
          <form className="project-target-intake-row" onSubmit={handleAddDraftTarget}>
            <label>
              Target
              <input
                aria-describedby="project-wizard-target-help"
                onChange={(event) => setDraftTargetValue(event.target.value)}
                placeholder="example.com or 10.0.0.1"
                value={draftTargetValue}
              />
            </label>
            <button className="secondary-button" type="submit">
              <Plus aria-hidden="true" size={15} strokeWidth={2} />
              <span>Add</span>
            </button>
          </form>
          <p className="field-hint" id="project-wizard-target-help">
            Targets are classified as {targetTypeLabel('domain')} or {targetTypeLabel('ip')}. You can add more later.
          </p>
          <TargetList
            emptyLabel="No targets added yet."
            onRemove={(targetId) => setDraftTargets((current) => current.filter((target) => target.id !== targetId))}
            targets={draftTargets}
          />
        </div>
      );
    }

    return (
      <div className="project-wizard-review">
        <div>
          <span>Name</span>
          <strong>{draftName.trim() || 'Untitled project'}</strong>
        </div>
        <div>
          <span>Domains</span>
          <strong>{draftTargets.filter((target) => target.type === 'domain').length}</strong>
        </div>
        <div>
          <span>IP addresses</span>
          <strong>{draftTargets.filter((target) => target.type === 'ip').length}</strong>
        </div>
      </div>
    );
  }

  return (
    <AppShell description="Scoped target management" section="projects" title="Projects" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="projects-workspace-grid projects-workspace-grid--modal-refactor">
          <section className="workspace-panel project-roster-panel" aria-label="Project roster">
            <div className="panel-header">
              <div>
                <h2>Project roster</h2>
                <p className="muted-text">Click a project to manage scope, targets, and activation.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <FolderKanban size={18} strokeWidth={2} />
              </div>
            </div>

            {projects.length === 0 ? (
              <div className="project-empty-state">
                <FolderKanban aria-hidden="true" size={18} strokeWidth={2} />
                <div>
                  <strong>No projects yet.</strong>
                  <span>Use the top-bar New menu to start the project wizard.</span>
                </div>
              </div>
            ) : (
              <div className="project-roster-list">
                {projects.map((project) => {
                  const isActive = project.id === activeProjectId;
                  return (
                    <button
                      className={`project-roster-item ${isActive ? 'is-active' : ''}`}
                      key={project.id}
                      onClick={() => openManageProject(project.id)}
                      type="button"
                    >
                      <span className="project-roster-name">
                        <strong>{project.name}</strong>
                      </span>
                      <span className="project-roster-meta">
                        <small>{countTargets(project)} targets</small>
                        {isActive ? <em>Active</em> : null}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </section>

          <section className="workspace-panel project-active-panel" aria-label="Active scope">
            <div className="panel-header">
              <div>
                <h2>Active scope</h2>
                <p className="muted-text">Only one project operates across the platform.</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <ShieldCheck size={18} strokeWidth={2} />
              </div>
            </div>
            <div className="project-stat-grid">
              <div>
                <span>Scope</span>
                <strong>{activeScopeName}</strong>
              </div>
              <div>
                <span>Targets</span>
                <strong>{activeScopeTargets}</strong>
              </div>
              <div>
                <span>Projects</span>
                <strong>{projects.length}</strong>
              </div>
            </div>
            <div className="project-activation-strip">
              <div>
                <strong>{activeProject ? 'Scoped workflows are active' : `${GLOBAL_SCOPE_LABEL} scope is active`}</strong>
                <span>{activeProject ? 'Recon and later workflows resolve against the active project.' : 'Use the top-bar New menu to create a scoped project.'}</span>
              </div>
            </div>
          </section>
        </div>
      )}

      {isCreateWizardOpen ? (
        <ModalShell
          ariaLabel="Create project wizard"
          onClose={closeCreateWizard}
          subtitle="Projects / scoped engagement setup"
          title="Create project"
          variant="wide"
        >
          <div className="project-wizard-modal">
            <div className="project-wizard-steps" aria-label="Project creation steps">
              {['Name', 'Targets', 'Review'].map((step, index) => (
                <span className={index === createStep ? 'is-active' : ''} key={step}>{step}</span>
              ))}
            </div>
            {renderCreateStep()}
            {projectError ? <p className="error-text project-form-error" role="alert">{projectError}</p> : null}
            {targetError ? <p className="error-text project-form-error" role="alert">{targetError}</p> : null}
            <div className="button-row">
              <button className="secondary-button" disabled={createStep === 0} onClick={() => setCreateStep((current) => Math.max(0, current - 1))} type="button">
                Back
              </button>
              {createStep < 2 ? (
                <button className="primary-button" onClick={() => setCreateStep((current) => Math.min(2, current + 1))} type="button">
                  Next
                </button>
              ) : (
                <button className="primary-button" onClick={handleCreateProject} type="button">
                  <Plus aria-hidden="true" size={15} strokeWidth={2} />
                  <span>Create project</span>
                </button>
              )}
            </div>
          </div>
        </ModalShell>
      ) : null}

      {managingProject ? (
        <ModalShell
          ariaLabel={`Manage project ${managingProject.name}`}
          onClose={() => setManagingProjectId('')}
          subtitle="Projects / attributes and scope"
          title={managingProject.name}
          variant="wide"
        >
          <div className="project-manage-modal">
            <section className="project-manage-summary" aria-label="Project summary">
              <div className={`project-scope-badge ${managingProject.id === activeProjectId ? 'project-scope-badge--active' : ''}`}>
                {managingProject.id === activeProjectId ? <CheckCircle2 aria-hidden="true" size={15} strokeWidth={2.2} /> : <ShieldCheck aria-hidden="true" size={15} strokeWidth={2.2} />}
                <span>{managingProject.id === activeProjectId ? 'Active scope' : 'Inactive'}</span>
              </div>
              <div className="project-stat-grid">
                <div>
                  <span>Domains</span>
                  <strong>{countTargets(managingProject, 'domain')}</strong>
                </div>
                <div>
                  <span>IP addresses</span>
                  <strong>{countTargets(managingProject, 'ip')}</strong>
                </div>
                <div>
                  <span>Total scope</span>
                  <strong>{countTargets(managingProject)}</strong>
                </div>
              </div>
            </section>

            <form className="workspace-form project-manage-name-form" onSubmit={handleRenameProject}>
              <label>
                Project name
                <input defaultValue={managingProject.name} name="projectName" />
              </label>
              <button className="secondary-button" type="submit">Save name</button>
            </form>

            <div className="project-activation-strip">
              <div>
                <strong>{managingProject.id === activeProjectId ? 'Current operating scope' : 'Not active across platform'}</strong>
                <span>{managingProject.id === activeProjectId ? 'Deactivate to return to Global scope.' : 'Activate this project before running scoped workflows.'}</span>
              </div>
              <button
                className={managingProject.id === activeProjectId ? 'danger-button' : 'primary-button'}
                onClick={() => handleToggleProjectScope(managingProject.id)}
                type="button"
              >
                <Power aria-hidden="true" size={15} strokeWidth={2} />
                <span>{managingProject.id === activeProjectId ? 'Deactivate' : 'Activate'}</span>
              </button>
            </div>

            <form className="project-target-intake-row" onSubmit={handleAddManagedTarget}>
              <label>
                Add target
                <input
                  aria-describedby="manage-target-help"
                  onChange={(event) => setManageTargetValue(event.target.value)}
                  placeholder="example.com or 10.0.0.1"
                  value={manageTargetValue}
                />
              </label>
              <button className="secondary-button" type="submit">
                <Plus aria-hidden="true" size={15} strokeWidth={2} />
                <span>Add</span>
              </button>
            </form>
            <p className="field-hint" id="manage-target-help">
              Domains and IPv4 addresses are detected automatically.
            </p>
            {projectError ? <p className="error-text project-form-error" role="alert">{projectError}</p> : null}
            {targetError ? <p className="error-text project-form-error" role="alert">{targetError}</p> : null}

            <div className="project-target-grid">
              <section className="project-target-group" aria-label="Domains">
                <div className="project-target-group-header">
                  <div>
                    <Globe2 aria-hidden="true" size={16} strokeWidth={2} />
                    <strong>Domains</strong>
                  </div>
                  <span>{countTargets(managingProject, 'domain')}</span>
                </div>
                <TargetList
                  emptyLabel="No domains in this project."
                  onRemove={handleRemoveManagedTarget}
                  targets={managingProject.targets.filter((target) => target.type === 'domain')}
                />
              </section>
              <section className="project-target-group" aria-label="IP addresses">
                <div className="project-target-group-header">
                  <div>
                    <Network aria-hidden="true" size={16} strokeWidth={2} />
                    <strong>IP addresses</strong>
                  </div>
                  <span>{countTargets(managingProject, 'ip')}</span>
                </div>
                <TargetList
                  emptyLabel="No IP addresses in this project."
                  onRemove={handleRemoveManagedTarget}
                  targets={managingProject.targets.filter((target) => target.type === 'ip')}
                />
              </section>
            </div>

            <div className="project-manage-danger-row">
              <button className="danger-button" onClick={() => setPendingDeleteProject(managingProject)} type="button">
                <Trash2 aria-hidden="true" size={15} strokeWidth={2} />
                <span>Delete project</span>
              </button>
            </div>
          </div>
        </ModalShell>
      ) : null}

      {pendingDeleteProject ? (
        <ModalShell
          ariaLabel="Delete project confirmation"
          onClose={() => setPendingDeleteProject(null)}
          subtitle="This removes the local project container and all targets in it."
          title="Delete project"
        >
          <div className="project-delete-modal-body">
            <div className="project-delete-warning">
              <AlertTriangle aria-hidden="true" size={18} strokeWidth={2.2} />
              <div>
                <strong>Delete {pendingDeleteProject.name}?</strong>
                <span>This cannot be undone. If this project is active, the platform returns to {GLOBAL_SCOPE_LABEL}.</span>
              </div>
            </div>
            <div className="button-row">
              <button className="secondary-button" onClick={() => setPendingDeleteProject(null)} type="button">
                Cancel
              </button>
              <button className="danger-button" onClick={handleConfirmDeleteProject} type="button">
                <Trash2 aria-hidden="true" size={15} strokeWidth={2} />
                <span>Delete project</span>
              </button>
            </div>
          </div>
        </ModalShell>
      ) : null}
    </AppShell>
  );
}
