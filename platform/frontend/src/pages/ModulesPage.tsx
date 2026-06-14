import { Clipboard, ExternalLink, Layers3, Play, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import type { ModuleDefinition } from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useModuleCatalog } from '../hooks/useModuleCatalog';
import {
  categoryLabel,
  encodeLaunchArgs,
  moduleExampleArgs,
  moduleExampleJson,
  schemaFields,
  schemaType,
} from '../modules/moduleCatalog';
import { useC2Connection } from '../useC2Connection';

function moduleSourceLabel(module: ModuleDefinition): string {
  return module.source === 'builtin' ? 'Built-in' : 'Plugin';
}

function moduleUpdatedLabel(module: ModuleDefinition): string {
  if (module.source !== 'plugin' || !module.updated_at) {
    return '';
  }
  const updatedAt = Date.parse(module.updated_at);
  if (!Number.isFinite(updatedAt)) {
    return '';
  }
  return `Updated ${new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' }).format(new Date(updatedAt))}`;
}

function launchPath(module: ModuleDefinition): string | null {
  const args = encodeLaunchArgs(moduleExampleArgs(module));
  const encodedModule = encodeURIComponent(module.id);
  if (module.execution_kind === 'scan-job' && module.id === 'builtin.portscan') {
    return `/recon?module=${encodedModule}&args=${args}`;
  }
  if (module.execution_kind === 'beacon-task') {
    return `/beacons?module=${encodedModule}&args=${args}`;
  }
  return null;
}

function ModuleBadges({ module }: { module: ModuleDefinition }) {
  const status = module.status ?? 'enabled';
  const updatedLabel = moduleUpdatedLabel(module);
  return (
    <div className="module-badge-row" aria-label={`${module.name} metadata`}>
      <span>{categoryLabel(module.category)}</span>
      <span>{moduleSourceLabel(module)}</span>
      {status !== 'enabled' ? <span>{status}</span> : null}
      <span>v{module.version}</span>
      <span>{module.author ?? 'Xero'}</span>
      {updatedLabel ? <span>{updatedLabel}</span> : null}
    </div>
  );
}

function ModuleCard({
  isSelected,
  module,
  onSelect,
}: {
  isSelected: boolean;
  module: ModuleDefinition;
  onSelect: (moduleId: string) => void;
}) {
  return (
    <button
      className={`module-card ${isSelected ? 'is-selected' : ''} ${(module.status ?? 'enabled') !== 'enabled' ? 'is-disabled' : ''}`}
      onClick={() => onSelect(module.id)}
      title={(module.status ?? 'enabled') === 'enabled' ? module.description : module.disabled_reason ?? 'Module is not currently available'}
      type="button"
    >
      <span className="module-card-head">
        <strong>{module.name}</strong>
        <small>{module.id}</small>
      </span>
      <ModuleBadges module={module} />
      <span className="module-card-description">{module.description}</span>
    </button>
  );
}

function SchemaTable({ module }: { module: ModuleDefinition }) {
  const fields = schemaFields(module);
  return (
    <div className="module-schema-table-wrap">
      <table className="module-schema-table">
        <thead>
          <tr>
            <th>Argument</th>
            <th>Type</th>
            <th>Required</th>
            <th>Default</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {fields.length === 0 ? (
            <tr>
              <td colSpan={5}>No arguments documented.</td>
            </tr>
          ) : fields.map((field) => (
            <tr key={field.key}>
              <td>{field.key}</td>
              <td>{schemaType(field.schema)}</td>
              <td>{field.isRequired ? 'yes' : 'no'}</td>
              <td>{typeof field.schema.default === 'undefined' ? '-' : String(field.schema.default)}</td>
              <td>{typeof field.schema.description === 'string' ? field.schema.description : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ModuleDetail({
  copyState,
  module,
  onCopy,
  onLaunch,
}: {
  copyState: string;
  module: ModuleDefinition | null;
  onCopy: () => void;
  onLaunch: () => void;
}) {
  if (!module) {
    return (
      <aside className="workspace-panel module-detail-panel" aria-label="Module detail">
        <div className="empty-state">
          <ShieldCheck aria-hidden="true" size={18} strokeWidth={2} />
          <div>
            <strong>No module selected.</strong>
            <span>Select a module to inspect its schema.</span>
          </div>
        </div>
      </aside>
    );
  }
  const canLaunch = (module.status ?? 'enabled') === 'enabled' && Boolean(launchPath(module));
  return (
    <aside className="workspace-panel module-detail-panel" aria-label="Module detail">
      <div className="panel-header">
        <div>
          <h2>{module.name}</h2>
          <p className="muted-text">{module.id}</p>
        </div>
        <div className="panel-icon" aria-hidden="true">
          <Layers3 size={18} strokeWidth={2} />
        </div>
      </div>

      <ModuleBadges module={module} />
      <p className="module-detail-description">{module.description}</p>
      {(module.status ?? 'enabled') !== 'enabled' ? (
        <p className="task-queue-error" role="alert">{module.disabled_reason ?? 'Module is not currently available.'}</p>
      ) : null}

      <SchemaTable module={module} />

      <div className="module-example-block">
        <div className="module-example-toolbar">
          <strong>Example task JSON</strong>
          <button className="secondary-button" onClick={onCopy} type="button">
            <Clipboard aria-hidden="true" size={14} strokeWidth={2.1} />
            <span>{copyState || 'Copy'}</span>
          </button>
        </div>
        <pre>{moduleExampleJson(module)}</pre>
      </div>

      <button
        className="primary-button module-launch-button"
        disabled={!canLaunch}
        onClick={onLaunch}
        title={canLaunch ? 'Launch task' : module.disabled_reason ?? 'This module cannot be launched from Modules'}
        type="button"
      >
        <Play aria-hidden="true" size={15} strokeWidth={2.2} />
        <span>{module.execution_kind === 'scan-job' ? 'Open in Recon' : 'Launch Task'}</span>
        <ExternalLink aria-hidden="true" size={14} strokeWidth={2.1} />
      </button>
    </aside>
  );
}

export function ModulesPage() {
  const navigate = useNavigate();
  const { connection } = useC2Connection();
  const [category, setCategory] = useState('all');
  const [copyState, setCopyState] = useState('');
  const [query, setQuery] = useState('');
  const [selectedModuleId, setSelectedModuleId] = useState('');
  const filters = useMemo(() => ({ category, query }), [category, query]);
  const {
    categories,
    error,
    filteredModules,
    isLoading,
    loadModules,
    modules,
  } = useModuleCatalog(connection, filters);
  const selectedModule = useMemo(() => (
    modules.find((module) => module.id === selectedModuleId) ?? filteredModules[0] ?? null
  ), [filteredModules, modules, selectedModuleId]);

  async function handleCopy(): Promise<void> {
    if (!selectedModule) {
      return;
    }
    await navigator.clipboard.writeText(moduleExampleJson(selectedModule));
    setCopyState('Copied');
    window.setTimeout(() => setCopyState(''), 1200);
  }

  function handleLaunch(): void {
    if (!selectedModule) {
      return;
    }
    const target = launchPath(selectedModule);
    if (target) {
      navigate(target);
    }
  }

  return (
    <AppShell description="C2 module catalog and launch schemas" section="assets" title="Modules" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="module-inventory-workspace">
          <section className="workspace-panel module-catalog-panel" aria-label="Module inventory">
            <div className="panel-header">
              <div>
                <h2>Modules</h2>
                <p className="muted-text">{modules.length} modules available</p>
              </div>
              <button className="secondary-button" disabled={isLoading} onClick={() => void loadModules()} type="button">
                <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
                <span>{isLoading ? 'Refreshing' : 'Refresh'}</span>
              </button>
            </div>

            <div className="module-catalog-toolbar">
              <label className="module-search">
                <Search aria-hidden="true" size={14} strokeWidth={2} />
                <input
                  aria-label="Search modules"
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search modules"
                  value={query}
                />
              </label>
              <select aria-label="Filter module category" onChange={(event) => setCategory(event.target.value)} value={category}>
                <option value="all">All categories</option>
                {categories.map((item) => (
                  <option key={item} value={item}>{categoryLabel(item)}</option>
                ))}
              </select>
            </div>

            {error ? <p className="task-queue-error" role="alert">{error}</p> : null}
            <div className="module-card-grid">
              {isLoading && modules.length === 0 ? (
                <div className="empty-state">
                  <Layers3 aria-hidden="true" size={18} strokeWidth={2} />
                  <div>
                    <strong>Loading modules.</strong>
                    <span>Catalog data is coming from C2.</span>
                  </div>
                </div>
              ) : null}
              {!isLoading && filteredModules.length === 0 ? (
                <div className="empty-state">
                  <Layers3 aria-hidden="true" size={18} strokeWidth={2} />
                  <div>
                    <strong>No modules found.</strong>
                    <span>Adjust search or category filters.</span>
                  </div>
                </div>
              ) : filteredModules.map((module) => (
                <ModuleCard
                  isSelected={module.id === selectedModule?.id}
                  key={module.id}
                  module={module}
                  onSelect={setSelectedModuleId}
                />
              ))}
            </div>
          </section>

          <ModuleDetail
            copyState={copyState}
            module={selectedModule}
            onCopy={() => void handleCopy()}
            onLaunch={handleLaunch}
          />
        </div>
      )}
    </AppShell>
  );
}
