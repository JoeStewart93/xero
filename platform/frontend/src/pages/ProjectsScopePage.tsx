import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Globe2, Network, Plus, Trash2 } from 'lucide-react';
import { Link, Navigate, useParams } from 'react-router-dom';

import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import {
  createLocalId,
  readActiveProjectId,
  readProjects,
  subscribeProjectScopeChanged,
  writeProjects,
} from '../projectScopeStorage';
import type { DiscoveryProject, ProjectTarget, TargetType } from '../projectScopeStorage';
import { useC2Connection } from '../useC2Connection';

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
  return labels.every((label) => label.length >= 1 && label.length <= 63 && /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(label));
}

function detectTarget(rawValue: string): { error: string } | { target: Omit<ProjectTarget, 'id'> } {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return { error: 'Enter a domain or IPv4 address.' };
  }
  const normalized = trimmed.toLowerCase().replace(/\.$/, '');
  if (isValidIpv4(normalized)) {
    return { target: { type: 'ip', value: normalized } };
  }
  if (looksLikeIpv4(normalized)) {
    return { error: 'Enter a valid IPv4 address.' };
  }
  if (isValidDomain(normalized)) {
    return { target: { type: 'domain', value: normalized } };
  }
  return { error: 'Enter a valid dotted domain or IPv4 address.' };
}

function targetIcon(type: TargetType) {
  return type === 'domain' ? Globe2 : Network;
}

export function ProjectsScopePage() {
  const { projectId: routeProjectId } = useParams();
  const { connection } = useC2Connection();
  const [projects, setProjects] = useState<DiscoveryProject[]>(() => readProjects());
  const [targetValue, setTargetValue] = useState('');
  const [targetError, setTargetError] = useState('');

  const resolvedProjectId = routeProjectId ?? readActiveProjectId(projects);
  const project = useMemo(
    () => projects.find((item) => item.id === resolvedProjectId) ?? null,
    [projects, resolvedProjectId],
  );

  useEffect(() => subscribeProjectScopeChanged(() => setProjects(readProjects())), []);

  function persistProject(nextProject: DiscoveryProject) {
    const nextProjects = projects.map((item) => (item.id === nextProject.id ? nextProject : item));
    setProjects(nextProjects);
    writeProjects(nextProjects);
  }

  function handleAddTarget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!project) {
      return;
    }
    const detected = detectTarget(targetValue);
    if ('error' in detected) {
      setTargetError(detected.error);
      return;
    }
    if (project.targets.some((target) => target.type === detected.target.type && target.value === detected.target.value)) {
      setTargetError('Target already exists in this project.');
      return;
    }
    persistProject({
      ...project,
      targets: [...project.targets, { ...detected.target, id: createLocalId('target') }],
    });
    setTargetValue('');
    setTargetError('');
  }

  function handleRemoveTarget(targetId: string) {
    if (!project) {
      return;
    }
    persistProject({
      ...project,
      targets: project.targets.filter((target) => target.id !== targetId),
    });
  }

  if (!connection) {
    return (
      <AppShell description="Project scope targets" section="projects" title="Projects" wide>
        <C2RequiredPanel />
      </AppShell>
    );
  }

  if (!resolvedProjectId) {
    return (
      <AppShell description="Project scope targets" section="projects" title="Projects" wide>
        <section className="workspace-panel workspace-panel--flat planned-section-empty">
          <h2>Scope</h2>
          <p className="muted-text">Select or create a project to manage authorized targets.</p>
          <Link className="primary-button" to="/projects?create=1">Create project</Link>
        </section>
      </AppShell>
    );
  }

  if (!project) {
    return <Navigate to="/projects" replace />;
  }

  return (
    <AppShell description={`Scope for ${project.name}`} section="projects" title="Projects" wide>
      <section className="workspace-panel workspace-panel--flat" aria-label={`Scope for ${project.name}`}>
        <h2>{project.name}</h2>
        <p className="muted-text">{project.targets.length} authorized targets</p>

        <form className="workspace-form project-scope-form" onSubmit={handleAddTarget}>
          <label>
            Add target
            <input onChange={(event) => setTargetValue(event.target.value)} placeholder="domain or IPv4" value={targetValue} />
          </label>
          <button className="primary-button" type="submit">
            <Plus aria-hidden="true" size={15} strokeWidth={2} />
            <span>Add</span>
          </button>
        </form>
        {targetError ? <p className="error-text" role="alert">{targetError}</p> : null}

        {project.targets.length === 0 ? (
          <p className="muted-text">No targets in scope yet.</p>
        ) : (
          <div className="project-target-list">
            {project.targets.map((target) => {
              const Icon = targetIcon(target.type);
              return (
                <div className="project-target-row" key={target.id}>
                  <Icon aria-hidden="true" size={14} strokeWidth={2} />
                  <span>{target.value}</span>
                  <button aria-label={`Remove ${target.value}`} onClick={() => handleRemoveTarget(target.id)} type="button">
                    <Trash2 aria-hidden="true" size={14} strokeWidth={2} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </AppShell>
  );
}

export function ProjectsScopeRedirectPage() {
  const activeId = readActiveProjectId(readProjects());
  if (!activeId) {
    return <ProjectsScopePage />;
  }
  return <Navigate to={`/projects/${activeId}/scope`} replace />;
}
