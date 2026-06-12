export type TargetType = 'domain' | 'ip';

export interface ProjectTarget {
  id: string;
  type: TargetType;
  value: string;
}

export interface DiscoveryProject {
  id: string;
  name: string;
  targets: ProjectTarget[];
}

export const PROJECT_STORAGE_KEY = 'xero.discovery.projects';
export const ACTIVE_PROJECT_STORAGE_KEY = 'xero.discovery.activeProjectId';
export const PROJECT_SCOPE_CHANGED_EVENT = 'xero:project-scope-changed';
export const GLOBAL_SCOPE_LABEL = 'Global';

export function createLocalId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizeProject(project: DiscoveryProject): DiscoveryProject {
  return {
    ...project,
    targets: Array.isArray(project.targets)
      ? project.targets.filter((target) => target.id && target.value && (target.type === 'domain' || target.type === 'ip'))
      : [],
  };
}

export function readProjects(): DiscoveryProject[] {
  const raw = window.localStorage.getItem(PROJECT_STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw) as DiscoveryProject[];
    return Array.isArray(parsed) ? parsed.map(normalizeProject).filter((project) => project.id && project.name) : [];
  } catch {
    window.localStorage.removeItem(PROJECT_STORAGE_KEY);
    return [];
  }
}

export function readActiveProjectId(projects = readProjects()): string {
  const stored = window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY) ?? '';
  return projects.some((project) => project.id === stored) ? stored : '';
}

export function dispatchProjectScopeChanged(): void {
  window.dispatchEvent(new CustomEvent(PROJECT_SCOPE_CHANGED_EVENT));
}

export function writeProjects(projects: DiscoveryProject[]): void {
  window.localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify(projects));
  if (readActiveProjectId(projects) === '' && window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY)) {
    window.localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
  }
  dispatchProjectScopeChanged();
}

export function writeActiveProjectId(projectId: string): void {
  if (projectId) {
    window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, projectId);
  } else {
    window.localStorage.removeItem(ACTIVE_PROJECT_STORAGE_KEY);
  }
  dispatchProjectScopeChanged();
}

export function readProjectScopeSnapshot(): { activeProjectId: string; projects: DiscoveryProject[] } {
  const projects = readProjects();
  return {
    activeProjectId: readActiveProjectId(projects),
    projects,
  };
}

export function subscribeProjectScopeChanged(listener: () => void): () => void {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === PROJECT_STORAGE_KEY || event.key === ACTIVE_PROJECT_STORAGE_KEY) {
      listener();
    }
  };

  window.addEventListener(PROJECT_SCOPE_CHANGED_EVENT, listener);
  window.addEventListener('storage', handleStorage);

  return () => {
    window.removeEventListener(PROJECT_SCOPE_CHANGED_EVENT, listener);
    window.removeEventListener('storage', handleStorage);
  };
}
