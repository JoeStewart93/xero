import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Copy, Plus, RefreshCw, RotateCcw, Save, Settings2, Trash2 } from 'lucide-react';

import {
  archiveTrafficProfile,
  cloneTrafficProfile,
  createTrafficProfile,
  getTrafficProfiles,
  getTrafficProfileVersions,
  rollbackTrafficProfile,
  TrafficProfile,
  TrafficProfileConfig,
  TrafficProfileVersion,
  updateTrafficProfile,
} from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { ModalShell } from '../components/ModalShell';
import { useC2Connection } from '../useC2Connection';

interface ProfileFormState {
  description: string;
  framePath: string;
  headerLines: string;
  jitter: string;
  name: string;
  paddingEnabled: boolean;
  paddingMax: string;
  paddingMin: string;
  pollPath: string;
  registerPath: string;
  sleepSeconds: string;
  template: string;
  userAgent: string;
  websocketPath: string;
}

const defaultConfig: TrafficProfileConfig = {
  headers: {},
  jitter: 0.1,
  padding: { enabled: false, max_bytes: 0, min_bytes: 0 },
  paths: {
    frame: '/api/v1/beacons/{beacon_id}/frame',
    poll: '/api/v1/beacons/{beacon_id}/poll',
    register: '/api/v1/beacons/register',
    websocket: '/ws/beacon',
  },
  sleep_seconds: 30,
  user_agent: 'xero-go-beacon/0.1',
};

function cloneDefaultConfig(): TrafficProfileConfig {
  return {
    headers: {},
    jitter: defaultConfig.jitter,
    padding: { ...defaultConfig.padding },
    paths: { ...defaultConfig.paths },
    sleep_seconds: defaultConfig.sleep_seconds,
    user_agent: defaultConfig.user_agent,
  };
}

function headersToText(headers: Record<string, string>): string {
  return Object.entries(headers)
    .map(([name, value]) => `${name}: ${value}`)
    .join('\n');
}

function parseHeaderLines(value: string): Record<string, string> {
  const headers: Record<string, string> = {};
  const lines = value.split('\n').map((line) => line.trim()).filter(Boolean);
  for (const line of lines) {
    const separator = line.indexOf(':');
    if (separator <= 0) {
      throw new Error('Headers must use "Name: value" lines.');
    }
    const name = line.slice(0, separator).trim();
    const headerValue = line.slice(separator + 1).trim();
    if (!/^[A-Za-z0-9][A-Za-z0-9-]{0,63}$/.test(name)) {
      throw new Error(`Invalid header name: ${name}`);
    }
    headers[name] = headerValue;
  }
  return headers;
}

function formFromConfig(config: TrafficProfileConfig, profile?: TrafficProfile): ProfileFormState {
  return {
    description: profile?.description ?? '',
    framePath: config.paths.frame,
    headerLines: headersToText(config.headers),
    jitter: String(config.jitter),
    name: profile?.name ?? 'Custom profile',
    paddingEnabled: config.padding.enabled,
    paddingMax: String(config.padding.max_bytes),
    paddingMin: String(config.padding.min_bytes),
    pollPath: config.paths.poll,
    registerPath: config.paths.register,
    sleepSeconds: String(config.sleep_seconds),
    template: profile?.template ?? 'custom',
    userAgent: config.user_agent,
    websocketPath: config.paths.websocket,
  };
}

function numericField(value: string, label: string, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) {
    throw new Error(`${label} must be between ${min} and ${max}.`);
  }
  return parsed;
}

function configFromForm(form: ProfileFormState): TrafficProfileConfig {
  const sleepSeconds = numericField(form.sleepSeconds, 'Sleep seconds', 1, 86400);
  const jitter = numericField(form.jitter, 'Jitter', 0, 1);
  const paddingMin = numericField(form.paddingMin, 'Padding minimum', 0, 4096);
  const paddingMax = numericField(form.paddingMax, 'Padding maximum', 0, 4096);
  if (!Number.isInteger(sleepSeconds) || !Number.isInteger(paddingMin) || !Number.isInteger(paddingMax)) {
    throw new Error('Sleep and padding values must be whole numbers.');
  }
  if (paddingMax < paddingMin) {
    throw new Error('Padding maximum must be greater than or equal to padding minimum.');
  }
  return {
    headers: parseHeaderLines(form.headerLines),
    jitter,
    padding: {
      enabled: form.paddingEnabled,
      max_bytes: form.paddingEnabled ? paddingMax : 0,
      min_bytes: form.paddingEnabled ? paddingMin : 0,
    },
    paths: {
      frame: form.framePath.trim(),
      poll: form.pollPath.trim(),
      register: form.registerPath.trim(),
      websocket: form.websocketPath.trim(),
    },
    sleep_seconds: sleepSeconds,
    user_agent: form.userAgent.trim(),
  };
}

function profileSummary(profile: TrafficProfile): string {
  return `${profile.config.sleep_seconds}s / ${Math.round(profile.config.jitter * 100)}% jitter / v${profile.current_version}`;
}

export function TrafficProfilesPage() {
  const { connection } = useC2Connection();
  const [profiles, setProfiles] = useState<TrafficProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState('new');
  const [versions, setVersions] = useState<TrafficProfileVersion[]>([]);
  const [rollbackVersion, setRollbackVersion] = useState('');
  const [form, setForm] = useState<ProfileFormState>(() => formFromConfig(cloneDefaultConfig()));
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [pendingArchive, setPendingArchive] = useState<TrafficProfile | null>(null);
  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.id === selectedProfileId) ?? null,
    [profiles, selectedProfileId],
  );
  const canEditSelected = Boolean(selectedProfile && !selectedProfile.is_template && !selectedProfile.is_archived);

  const loadProfiles = useCallback(async () => {
    if (!connection) {
      setProfiles([]);
      return;
    }
    setIsLoading(true);
    setError('');
    try {
      const response = await getTrafficProfiles(connection.baseUrl, connection.accessToken);
      setProfiles(response.items);
      if (selectedProfileId !== 'new' && !response.items.some((profile) => profile.id === selectedProfileId)) {
        setSelectedProfileId(response.items[0]?.id ?? 'new');
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load traffic profiles.');
    } finally {
      setIsLoading(false);
    }
  }, [connection, selectedProfileId]);

  const loadVersions = useCallback(async (profile: TrafficProfile | null) => {
    if (!connection || !profile) {
      setVersions([]);
      setRollbackVersion('');
      return;
    }
    try {
      const response = await getTrafficProfileVersions(connection.baseUrl, connection.accessToken, profile.id);
      setVersions(response.items);
      setRollbackVersion(String(response.items[0]?.version ?? ''));
    } catch (caught) {
      setVersions([]);
      setRollbackVersion('');
      setError(caught instanceof Error ? caught.message : 'Unable to load profile versions.');
    }
  }, [connection]);

  useEffect(() => {
    const handle = window.setTimeout(() => void loadProfiles(), 0);
    return () => window.clearTimeout(handle);
  }, [loadProfiles]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      if (selectedProfile) {
        setForm(formFromConfig(selectedProfile.config, selectedProfile));
        void loadVersions(selectedProfile);
        return;
      }
      setForm(formFromConfig(cloneDefaultConfig()));
      void loadVersions(null);
    }, 0);
    return () => window.clearTimeout(handle);
  }, [loadVersions, selectedProfile]);

  function handleField<K extends keyof ProfileFormState>(key: K, value: ProfileFormState[K]): void {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSave(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!connection) {
      return;
    }
    setIsSaving(true);
    setError('');
    setMessage('');
    try {
      const payload = {
        config: configFromForm(form),
        description: form.description.trim() || null,
        name: form.name.trim(),
        template: form.template.trim() || 'custom',
      };
      const saved = selectedProfile && canEditSelected
        ? await updateTrafficProfile(connection.baseUrl, connection.accessToken, selectedProfile.id, payload)
        : await createTrafficProfile(connection.baseUrl, connection.accessToken, payload);
      setSelectedProfileId(saved.id);
      setMessage(`${saved.name} saved as version ${saved.current_version}.`);
      await loadProfiles();
      await loadVersions(saved);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to save traffic profile.');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleClone(): Promise<void> {
    if (!connection || !selectedProfile) {
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      const cloned = await cloneTrafficProfile(connection.baseUrl, connection.accessToken, selectedProfile.id, `${selectedProfile.name} copy`);
      setSelectedProfileId(cloned.id);
      setMessage(`${selectedProfile.name} cloned.`);
      await loadProfiles();
      await loadVersions(cloned);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to clone traffic profile.');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRollback(): Promise<void> {
    if (!connection || !selectedProfile || !rollbackVersion) {
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      const rolledBack = await rollbackTrafficProfile(
        connection.baseUrl,
        connection.accessToken,
        selectedProfile.id,
        Number(rollbackVersion),
      );
      setSelectedProfileId(rolledBack.id);
      setMessage(`${rolledBack.name} rolled back into version ${rolledBack.current_version}.`);
      await loadProfiles();
      await loadVersions(rolledBack);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to roll back traffic profile.');
    } finally {
      setIsSaving(false);
    }
  }

  async function handleArchive(): Promise<void> {
    if (!connection || !pendingArchive) {
      return;
    }
    setIsSaving(true);
    setError('');
    try {
      await archiveTrafficProfile(connection.baseUrl, connection.accessToken, pendingArchive.id);
      setPendingArchive(null);
      setSelectedProfileId('new');
      setMessage(`${pendingArchive.name} archived.`);
      await loadProfiles();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to archive traffic profile.');
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <AppShell description="C2 traffic shape templates and beacon runtime profiles" section="settings" title="Settings" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="traffic-profile-layout">
          <section className="workspace-panel traffic-profile-list-panel" aria-label="Traffic profiles">
            <div className="panel-header">
              <div>
                <h2>Traffic profiles</h2>
                <p className="muted-text">Templates and custom versions served to beacons on check-in.</p>
              </div>
              <button className="secondary-button" disabled={isLoading} onClick={() => void loadProfiles()} type="button">
                <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
                <span>{isLoading ? 'Loading' : 'Refresh'}</span>
              </button>
            </div>

            <div className="traffic-profile-actions">
              <button
                className={selectedProfileId === 'new' ? 'primary-button' : 'secondary-button'}
                onClick={() => setSelectedProfileId('new')}
                type="button"
              >
                <Plus aria-hidden="true" size={15} strokeWidth={2.1} />
                <span>New profile</span>
              </button>
            </div>

            <div className="traffic-profile-list">
              {profiles.map((profile) => (
                <button
                  className={`traffic-profile-row ${profile.id === selectedProfileId ? 'is-selected' : ''}`}
                  key={profile.id}
                  onClick={() => setSelectedProfileId(profile.id)}
                  type="button"
                >
                  <span>
                    <strong>{profile.name}</strong>
                    <em>{profile.template}</em>
                  </span>
                  <span>{profileSummary(profile)}</span>
                  {profile.is_template ? <small>Template</small> : null}
                </button>
              ))}
            </div>
          </section>

          <section className="workspace-panel traffic-profile-editor" aria-label="Traffic profile editor">
            <div className="panel-header">
              <div>
                <h2>{selectedProfile ? selectedProfile.name : 'New traffic profile'}</h2>
                <p className="muted-text">
                  {selectedProfile?.is_template ? 'Clone templates before editing.' : 'Changes create a new immutable version.'}
                </p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <Settings2 size={18} strokeWidth={2} />
              </div>
            </div>

            {error ? <p className="alert-message alert-message--inline" role="alert">{error}</p> : null}
            {message ? <p className="alert-message alert-message--inline alert-message--success">{message}</p> : null}

            <form className="traffic-profile-form" onSubmit={handleSave}>
              <div className="traffic-profile-form-grid">
                <label>
                  Name
                  <input
                    disabled={Boolean(selectedProfile?.is_template)}
                    onChange={(event) => handleField('name', event.target.value)}
                    value={form.name}
                  />
                </label>
                <label>
                  Template key
                  <input
                    disabled={Boolean(selectedProfile)}
                    onChange={(event) => handleField('template', event.target.value)}
                    value={form.template}
                  />
                </label>
                <label className="traffic-profile-wide-field">
                  Description
                  <input
                    disabled={Boolean(selectedProfile?.is_template)}
                    onChange={(event) => handleField('description', event.target.value)}
                    value={form.description}
                  />
                </label>
                <label>
                  Sleep seconds
                  <input
                    min={1}
                    onChange={(event) => handleField('sleepSeconds', event.target.value)}
                    type="number"
                    value={form.sleepSeconds}
                  />
                </label>
                <label>
                  Jitter
                  <input
                    max={1}
                    min={0}
                    onChange={(event) => handleField('jitter', event.target.value)}
                    step="0.01"
                    type="number"
                    value={form.jitter}
                  />
                </label>
                <label className="traffic-profile-wide-field">
                  User-Agent
                  <input onChange={(event) => handleField('userAgent', event.target.value)} value={form.userAgent} />
                </label>
              </div>

              <div className="traffic-profile-fieldset">
                <strong>Headers</strong>
                <textarea
                  aria-label="Traffic profile headers"
                  onChange={(event) => handleField('headerLines', event.target.value)}
                  rows={4}
                  value={form.headerLines}
                />
              </div>

              <div className="traffic-profile-form-grid">
                <label>
                  Frame path
                  <input onChange={(event) => handleField('framePath', event.target.value)} value={form.framePath} />
                </label>
                <label>
                  Poll path
                  <input onChange={(event) => handleField('pollPath', event.target.value)} value={form.pollPath} />
                </label>
                <label>
                  Register path
                  <input onChange={(event) => handleField('registerPath', event.target.value)} value={form.registerPath} />
                </label>
                <label>
                  WebSocket path
                  <input onChange={(event) => handleField('websocketPath', event.target.value)} value={form.websocketPath} />
                </label>
              </div>

              <div className="traffic-profile-padding-row">
                <label className="traffic-profile-checkbox">
                  <input
                    checked={form.paddingEnabled}
                    onChange={(event) => handleField('paddingEnabled', event.target.checked)}
                    type="checkbox"
                  />
                  <span>Encrypted payload padding</span>
                </label>
                <label>
                  Min bytes
                  <input
                    min={0}
                    onChange={(event) => handleField('paddingMin', event.target.value)}
                    type="number"
                    value={form.paddingMin}
                  />
                </label>
                <label>
                  Max bytes
                  <input
                    min={0}
                    onChange={(event) => handleField('paddingMax', event.target.value)}
                    type="number"
                    value={form.paddingMax}
                  />
                </label>
              </div>

              <div className="traffic-profile-preview" aria-label="HTTP request preview">
                <strong>Request preview</strong>
                <code>POST {form.framePath || '-'}</code>
                <code>GET {form.pollPath || '-'}</code>
                <code>User-Agent: {form.userAgent || '-'}</code>
                {form.headerLines
                  .split('\n')
                  .map((line) => line.trim())
                  .filter(Boolean)
                  .map((line) => <code key={line}>{line}</code>)}
                <span>
                  Padding {form.paddingEnabled ? `${form.paddingMin}-${form.paddingMax} bytes` : 'disabled'} / sleep {form.sleepSeconds || '-'}s
                </span>
              </div>

              <div className="traffic-profile-editor-actions">
                <button className="primary-button" disabled={isSaving || Boolean(selectedProfile?.is_template)} type="submit">
                  <Save aria-hidden="true" size={15} strokeWidth={2.1} />
                  <span>{isSaving ? 'Saving' : selectedProfile ? 'Save version' : 'Create profile'}</span>
                </button>
                <button className="secondary-button" disabled={!selectedProfile || isSaving} onClick={() => void handleClone()} type="button">
                  <Copy aria-hidden="true" size={15} strokeWidth={2.1} />
                  <span>Clone</span>
                </button>
                <button
                  className="danger-button"
                  disabled={!canEditSelected || isSaving}
                  onClick={() => selectedProfile && setPendingArchive(selectedProfile)}
                  type="button"
                >
                  <Trash2 aria-hidden="true" size={15} strokeWidth={2.1} />
                  <span>Archive</span>
                </button>
              </div>
            </form>

            <div className="traffic-profile-versions">
              <div>
                <strong>Version history</strong>
                <span>{versions.length} saved versions</span>
              </div>
              <select
                aria-label="Traffic profile version"
                disabled={!canEditSelected || versions.length === 0}
                onChange={(event) => setRollbackVersion(event.target.value)}
                value={rollbackVersion}
              >
                {versions.map((version) => (
                  <option key={version.id} value={version.version}>
                    v{version.version} / {new Date(version.created_at).toLocaleString()}
                  </option>
                ))}
              </select>
              <button
                className="secondary-button"
                disabled={!canEditSelected || !rollbackVersion || Number(rollbackVersion) === selectedProfile?.current_version}
                onClick={() => void handleRollback()}
                type="button"
              >
                <RotateCcw aria-hidden="true" size={15} strokeWidth={2.1} />
                <span>Rollback</span>
              </button>
            </div>
          </section>
        </div>
      )}

      {pendingArchive ? (
        <ModalShell
          ariaLabel="Archive traffic profile confirmation"
          onClose={() => setPendingArchive(null)}
          subtitle="Assigned profiles cannot be archived."
          title="Archive traffic profile"
        >
          <div className="project-delete-modal-body">
            <div className="project-delete-warning">
              <Trash2 aria-hidden="true" size={18} strokeWidth={2.2} />
              <div>
                <strong>Archive {pendingArchive.name}?</strong>
                <span>Existing version history is retained, but the profile is removed from assignment choices.</span>
              </div>
            </div>
            <div className="button-row">
              <button className="secondary-button" onClick={() => setPendingArchive(null)} type="button">
                Cancel
              </button>
              <button className="danger-button" disabled={isSaving} onClick={() => void handleArchive()} type="button">
                <Trash2 aria-hidden="true" size={15} strokeWidth={2} />
                <span>{isSaving ? 'Archiving' : 'Archive profile'}</span>
              </button>
            </div>
          </div>
        </ModalShell>
      ) : null}
    </AppShell>
  );
}
