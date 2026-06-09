import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import {
  Boxes,
  CheckCircle2,
  FolderKanban,
  Globe2,
  Network,
  Plus,
  Power,
  RadioTower,
  ShieldCheck,
  Trash2,
} from 'lucide-react';

import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import {
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

interface TargetDetectionResult {
  error?: string;
  target?: Omit<ProjectTarget, 'id'>;
}

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

export function ProjectsPage() {
  const { connection } = useC2Connection();
  const [projects, setProjects] = useState<DiscoveryProject[]>(() => readProjects());
  const [activeProjectId, setActiveProjectId] = useState(() => readActiveProjectId(readProjects()));
  const [selectedProjectId, setSelectedProjectId] = useState(() => activeProjectId || projects[0]?.id || '');
  const [projectError, setProjectError] = useState('');
  const [targetError, setTargetError] = useState('');
  const activeProjectIdRef = useRef(activeProjectId);
  const selectedProjectIdRef = useRef(selectedProjectId);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) ?? projects[0],
    [projects, selectedProjectId],
  );
  const activeProject = useMemo(() => projects.find((project) => project.id === activeProjectId), [activeProjectId, projects]);
  const domains = selectedProject?.targets.filter((target) => target.type === 'domain') ?? [];
  const ips = selectedProject?.targets.filter((target) => target.type === 'ip') ?? [];
  const selectedProjectIsActive = Boolean(selectedProject && selectedProject.id === activeProjectId);

  useEffect(() => {
    activeProjectIdRef.current = activeProjectId;
  }, [activeProjectId]);

  useEffect(() => {
    selectedProjectIdRef.current = selectedProjectId;
  }, [selectedProjectId]);

  useEffect(
    () =>
      subscribeProjectScopeChanged(() => {
        const snapshot = readProjectScopeSnapshot();
        const previousActiveProjectId = activeProjectIdRef.current;
        const selectedProjectStillExists = snapshot.projects.some((project) => project.id === selectedProjectIdRef.current);

        setProjects(snapshot.projects);
        setActiveProjectId(snapshot.activeProjectId);
        activeProjectIdRef.current = snapshot.activeProjectId;

        if (snapshot.activeProjectId && snapshot.activeProjectId !== previousActiveProjectId) {
          selectedProjectIdRef.current = snapshot.activeProjectId;
          setSelectedProjectId(snapshot.activeProjectId);
          return;
        }

        if (!selectedProjectStillExists) {
          const fallbackProjectId = snapshot.activeProjectId || snapshot.projects[0]?.id || '';
          selectedProjectIdRef.current = fallbackProjectId;
          setSelectedProjectId(fallbackProjectId);
        }
      }),
    [],
  );

  function persistProjects(nextProjects: DiscoveryProject[]) {
    setProjects(nextProjects);
    writeProjects(nextProjects);
  }

  function handleCreateProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const name = String(form.get('projectName') ?? '').trim();
    if (!name) {
      setProjectError('Project name is required.');
      return;
    }

    if (projects.some((project) => project.name.toLowerCase() === name.toLowerCase())) {
      setProjectError('A project with this name already exists.');
      return;
    }

    const project: DiscoveryProject = {
      id: createLocalId('project'),
      name,
      targets: [],
    };
    persistProjects([...projects, project]);
    setSelectedProjectId(project.id);
    setProjectError('');
    event.currentTarget.reset();
  }

  function handleToggleProjectScope(projectId: string) {
    if (projectId === activeProjectId) {
      setActiveProjectId('');
      writeActiveProjectId('');
      return;
    }

    setActiveProjectId(projectId);
    writeActiveProjectId(projectId);
    setSelectedProjectId(projectId);
  }

  function handleAddTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject) {
      setTargetError('Create or select a project before adding targets.');
      return;
    }

    const form = new FormData(event.currentTarget);
    const detection = detectTarget(String(form.get('targetValue') ?? ''));
    if (detection.error || !detection.target) {
      setTargetError(detection.error ?? 'Enter a valid target.');
      return;
    }
    const detectedTarget = detection.target;

    const isDuplicate = selectedProject.targets.some(
      (target) => target.type === detectedTarget.type && target.value.toLowerCase() === detectedTarget.value.toLowerCase(),
    );
    if (isDuplicate) {
      setTargetError(`${detectedTarget.value} is already in this project.`);
      return;
    }

    const nextProjects = projects.map((project) =>
      project.id === selectedProject.id
        ? {
            ...project,
            targets: [...project.targets, { id: createLocalId('target'), ...detectedTarget }],
          }
        : project,
    );
    persistProjects(nextProjects);
    setTargetError('');
    event.currentTarget.reset();
  }

  function handleRemoveTarget(targetId: string) {
    if (!selectedProject) {
      return;
    }

    persistProjects(
      projects.map((project) =>
        project.id === selectedProject.id
          ? {
              ...project,
              targets: project.targets.filter((target) => target.id !== targetId),
            }
          : project,
      ),
    );
  }

  function renderTargetGroup(title: string, type: TargetType, targets: ProjectTarget[]) {
    const Icon = type === 'domain' ? Globe2 : Network;
    return (
      <section className="project-target-group" aria-label={title}>
        <div className="project-target-group-header">
          <div>
            <Icon aria-hidden="true" size={16} strokeWidth={2} />
            <strong>{title}</strong>
          </div>
          <span>{targets.length}</span>
        </div>
        {targets.length === 0 ? (
          <div className="project-target-empty">No {title.toLowerCase()} in this project.</div>
        ) : (
          <div className="project-target-list">
            {targets.map((target) => (
              <div className="project-target-row" key={target.id}>
                <span>{target.value}</span>
                <button aria-label={`Remove ${target.value}`} onClick={() => handleRemoveTarget(target.id)} type="button">
                  <Trash2 aria-hidden="true" size={14} strokeWidth={2} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    );
  }

  return (
    <AppShell description="Scoped target management" section="projects" title="Projects" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="projects-workspace-grid">
          <section className="workspace-panel project-roster-panel" aria-label="Project roster">
            <div className="panel-header">
              <div>
                <h2>Project roster</h2>
                <p className="muted-text">Select a project, then activate it as platform scope.</p>
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
                  <span>Create a project to define discovery scope.</span>
                </div>
              </div>
            ) : (
              <div className="project-roster-list">
                {projects.map((project) => {
                  const isSelected = project.id === selectedProject?.id;
                  const isActive = project.id === activeProjectId;
                  return (
                    <button
                      className={`project-roster-item ${isSelected ? 'is-selected' : ''} ${isActive ? 'is-active' : ''}`}
                      key={project.id}
                      onClick={() => setSelectedProjectId(project.id)}
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

          <section className="workspace-panel project-detail-panel" aria-label="Selected project detail">
            <div className="panel-header">
              <div>
                <h2>{selectedProject?.name ?? 'No project selected'}</h2>
                <p className="muted-text">
                  {selectedProjectIsActive ? 'This project is active platform scope.' : 'Activate this project before running scoped workflows.'}
                </p>
              </div>
              <div className={`project-scope-badge ${selectedProjectIsActive ? 'project-scope-badge--active' : ''}`}>
                {selectedProjectIsActive ? <CheckCircle2 aria-hidden="true" size={15} strokeWidth={2.2} /> : <ShieldCheck aria-hidden="true" size={15} strokeWidth={2.2} />}
                <span>{selectedProjectIsActive ? 'Active scope' : 'Inactive'}</span>
              </div>
            </div>

            {selectedProject ? (
              <>
                <div className="project-stat-grid">
                  <div>
                    <span>Domains</span>
                    <strong>{countTargets(selectedProject, 'domain')}</strong>
                  </div>
                  <div>
                    <span>IP addresses</span>
                    <strong>{countTargets(selectedProject, 'ip')}</strong>
                  </div>
                  <div>
                    <span>Total scope</span>
                    <strong>{countTargets(selectedProject)}</strong>
                  </div>
                </div>

                <div className="project-activation-strip">
                  <div>
                    <strong>{selectedProjectIsActive ? 'Current operating scope' : 'Not active across platform'}</strong>
                    <span>
                      {selectedProjectIsActive
                        ? 'Recon and later workflows resolve against this project until deactivated.'
                        : 'Press Activate to make this the only active project scope.'}
                    </span>
                  </div>
                  <button
                    className={selectedProjectIsActive ? 'danger-button' : 'primary-button'}
                    onClick={() => handleToggleProjectScope(selectedProject.id)}
                    type="button"
                  >
                    <Power aria-hidden="true" size={15} strokeWidth={2} />
                    <span>{selectedProjectIsActive ? 'Deactivate' : 'Activate'}</span>
                  </button>
                </div>

                <div className="project-target-grid">
                  {renderTargetGroup('Domains', 'domain', domains)}
                  {renderTargetGroup('IP addresses', 'ip', ips)}
                </div>
              </>
            ) : (
              <div className="project-empty-state project-empty-state--large">
                <Boxes aria-hidden="true" size={20} strokeWidth={2} />
                <div>
                  <strong>No project selected.</strong>
                  <span>Create a project on the right to begin defining scope.</span>
                </div>
              </div>
            )}
          </section>

          <aside className="project-action-stack" aria-label="Project actions">
            <section className="workspace-panel" aria-label="Project creation">
              <div className="panel-header">
                <div>
                  <h2>New project</h2>
                  <p className="muted-text">Create a scoped engagement container.</p>
                </div>
                <div className="panel-icon" aria-hidden="true">
                  <Plus size={18} strokeWidth={2} />
                </div>
              </div>

              <form className="workspace-form" onSubmit={handleCreateProject}>
                <label>
                  Project name
                  <input name="projectName" placeholder="acme-external-scope" />
                </label>
                <button className="primary-button" type="submit">
                  <Plus aria-hidden="true" size={15} strokeWidth={2} />
                  <span>Create project</span>
                </button>
              </form>
              {projectError ? (
                <p className="error-text project-form-error" role="alert">
                  {projectError}
                </p>
              ) : null}
            </section>

            <section className="workspace-panel" aria-label="Target intake">
              <div className="panel-header">
                <div>
                  <h2>Add target</h2>
                  <p className="muted-text">Domains and IPv4 addresses are detected automatically.</p>
                </div>
                <div className="panel-icon" aria-hidden="true">
                  <RadioTower size={18} strokeWidth={2} />
                </div>
              </div>

              <form className="workspace-form" onSubmit={handleAddTarget}>
                <label>
                  Target
                  <input aria-describedby="target-help" name="targetValue" placeholder="example.com or 10.0.0.1" />
                </label>
                <p className="field-hint" id="target-help">
                  The platform classifies valid entries as {targetTypeLabel('domain')} or {targetTypeLabel('ip')}.
                </p>
                <button className="secondary-button" disabled={!selectedProject} type="submit">
                  Add to {selectedProject?.name ?? 'project'}
                </button>
              </form>
              {targetError ? (
                <p className="error-text project-form-error" role="alert">
                  {targetError}
                </p>
              ) : null}
            </section>

            <section className="workspace-panel project-active-panel" aria-label="Active scope">
              <div className="panel-header">
                <div>
                  <h2>Active scope</h2>
                  <p className="muted-text">Only one project operates across the platform.</p>
                </div>
              </div>
              <div className="dashboard-list">
                <div className="dashboard-row">
                  <span>Project</span>
                  <strong>{activeProject?.name ?? '-'}</strong>
                </div>
                <div className="dashboard-row">
                  <span>Targets</span>
                  <strong>{activeProject ? countTargets(activeProject) : '-'}</strong>
                </div>
              </div>
            </section>
          </aside>
        </div>
      )}
    </AppShell>
  );
}
