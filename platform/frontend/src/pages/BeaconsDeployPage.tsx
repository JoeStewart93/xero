import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Download, FileCode2, Hammer, Loader2, RefreshCw, ServerCog, ShieldCheck } from 'lucide-react';

import {
  BeaconBuild,
  BeaconBuildConfigMode,
  BeaconBuildTarget,
  BeaconBuildTargetOS,
  createBeaconBuild,
  downloadBeaconBuildArtifact,
  getBeaconBuilds,
  getBeaconBuildTargets,
} from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useC2Connection } from '../useC2Connection';

const configModes: BeaconBuildConfigMode[] = ['all', 'file', 'env', 'ldflags'];

function buildStatusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function buildCanDownload(build: BeaconBuild): boolean {
  return build.status === 'succeeded' && build.artifact_available;
}

function buildStatusDisplay(build: BeaconBuild): string {
  if (build.status === 'succeeded' && !build.artifact_available) {
    return 'Artifact missing';
  }
  return buildStatusLabel(build.status);
}

function buildStatusClass(build: BeaconBuild): string {
  if (build.status === 'succeeded' && !build.artifact_available) {
    return 'missing';
  }
  return build.status;
}

function formatBytes(value: number | null): string {
  if (value === null) {
    return '-';
  }
  if (value < 1024) {
    return `${value} B`;
  }
  return `${(value / 1024).toFixed(1)} KiB`;
}

export function BeaconsDeployPage() {
  const { connection } = useC2Connection();
  const [targets, setTargets] = useState<BeaconBuildTarget[]>([]);
  const [builds, setBuilds] = useState<BeaconBuild[]>([]);
  const [targetOS, setTargetOS] = useState<BeaconBuildTargetOS>('linux');
  const [c2Url, setC2Url] = useState(connection?.baseUrl ?? 'http://localhost:8001');
  const [profileName, setProfileName] = useState('default');
  const [sleepSeconds, setSleepSeconds] = useState('30');
  const [jitter, setJitter] = useState('0.1');
  const [outputName, setOutputName] = useState('');
  const [configMode, setConfigMode] = useState<BeaconBuildConfigMode>('all');
  const [fallbackLongPoll, setFallbackLongPoll] = useState(true);
  const [isLoading, setLoading] = useState(false);
  const [isBuilding, setBuilding] = useState(false);
  const [downloadingBuildId, setDownloadingBuildId] = useState('');
  const [error, setError] = useState('');

  const selectedTarget = useMemo(
    () => targets.find((target) => target.os === targetOS) ?? targets[0] ?? null,
    [targetOS, targets],
  );

  const configPreview = useMemo(
    () => ({
      c2_url: c2Url,
      config_mode: configMode,
      fallback_longpoll_enabled: fallbackLongPoll,
      jitter: Number(jitter),
      output_name: outputName.trim() || undefined,
      profile_name: profileName,
      sleep_seconds: Number(sleepSeconds),
      target_arch: selectedTarget?.arch ?? 'amd64',
      target_os: selectedTarget?.os ?? targetOS,
    }),
    [c2Url, configMode, fallbackLongPoll, jitter, outputName, profileName, selectedTarget, sleepSeconds, targetOS],
  );

  const loadBuildState = useCallback(async () => {
    if (!connection) {
      setTargets([]);
      setBuilds([]);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const [targetResponse, buildResponse] = await Promise.all([
        getBeaconBuildTargets(connection.baseUrl, connection.accessToken),
        getBeaconBuilds(connection.baseUrl, connection.accessToken),
      ]);
      setTargets(targetResponse.items);
      setBuilds(buildResponse.items);
      if (targetResponse.items.length > 0 && !targetResponse.items.some((target) => target.os === targetOS)) {
        setTargetOS(targetResponse.items[0].os);
      }
      if (!c2Url && connection.baseUrl) {
        setC2Url(connection.baseUrl);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load beacon build state.');
    } finally {
      setLoading(false);
    }
  }, [c2Url, connection, targetOS]);

  useEffect(() => {
    const refreshTimer = window.setTimeout(() => void loadBuildState(), 0);
    return () => window.clearTimeout(refreshTimer);
  }, [loadBuildState]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!connection || !selectedTarget) {
      return;
    }
    const parsedSleep = Number(sleepSeconds);
    const parsedJitter = Number(jitter);
    if (!Number.isInteger(parsedSleep) || parsedSleep < 1) {
      setError('Sleep must be a positive whole number.');
      return;
    }
    if (Number.isNaN(parsedJitter) || parsedJitter < 0 || parsedJitter > 1) {
      setError('Jitter must be between 0 and 1.');
      return;
    }
    setBuilding(true);
    setError('');
    try {
      const build = await createBeaconBuild(connection.baseUrl, connection.accessToken, {
        c2_url: c2Url,
        config_mode: configMode,
        fallback_longpoll_enabled: fallbackLongPoll,
        jitter: parsedJitter,
        output_name: outputName.trim() || undefined,
        profile_name: profileName,
        sleep_seconds: parsedSleep,
        target_arch: selectedTarget.arch,
        target_os: selectedTarget.os,
      });
      setBuilds((current) => [build, ...current.filter((item) => item.id !== build.id)]);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to create beacon build.');
    } finally {
      setBuilding(false);
    }
  }

  async function handleDownload(build: BeaconBuild) {
    if (!connection) {
      return;
    }
    if (!buildCanDownload(build)) {
      setError('Beacon build artifact is missing from C2 storage. Rebuild the beacon to recreate it.');
      return;
    }
    setDownloadingBuildId(build.id);
    setError('');
    try {
      const blob = await downloadBeaconBuildArtifact(connection.baseUrl, connection.accessToken, build.id);
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = build.artifact_filename ?? `xero-beacon-${build.target_os}-${build.target_arch}`;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to download artifact.');
    } finally {
      setDownloadingBuildId('');
    }
  }

  return (
    <AppShell description="Build configured Go beacon agents for the connected C2 backend" section="beacons" title="Beacons" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="deploy-builder-layout">
          <section className="workspace-panel deploy-builder-main" aria-label="Beacon deploy builder">
            <div className="panel-header">
              <div>
                <h2>Deploy builder</h2>
                <p className="muted-text">Build a signed-in protocol profile for WebSocket primary transport and long-poll fallback.</p>
              </div>
              <button className="secondary-button" disabled={isLoading} onClick={() => void loadBuildState()} type="button">
                <RefreshCw aria-hidden="true" size={15} strokeWidth={2.2} />
                <span>{isLoading ? 'Refreshing' : 'Refresh'}</span>
              </button>
            </div>

            <form className="deploy-builder-form" onSubmit={handleSubmit}>
              <fieldset className="deploy-step">
                <legend>
                  <ServerCog aria-hidden="true" size={16} strokeWidth={2.1} />
                  Target
                </legend>
                <div className="deploy-target-grid">
                  {targets.map((target) => (
                    <button
                      aria-pressed={target.os === targetOS}
                      className={`deploy-target-option ${target.os === targetOS ? 'is-selected' : ''}`}
                      key={`${target.os}-${target.arch}`}
                      onClick={() => setTargetOS(target.os)}
                      type="button"
                    >
                      <strong>{target.label}</strong>
                      <span>{target.os}/{target.arch}</span>
                    </button>
                  ))}
                </div>
              </fieldset>

              <fieldset className="deploy-step">
                <legend>
                  <ShieldCheck aria-hidden="true" size={16} strokeWidth={2.1} />
                  Connection
                </legend>
                <div className="deploy-field-grid">
                  <label>
                    <span>C2 URL</span>
                    <input onChange={(event) => setC2Url(event.target.value)} value={c2Url} />
                  </label>
                  <label>
                    <span>Profile</span>
                    <input onChange={(event) => setProfileName(event.target.value)} value={profileName} />
                  </label>
                  <label>
                    <span>Sleep</span>
                    <input min={1} onChange={(event) => setSleepSeconds(event.target.value)} type="number" value={sleepSeconds} />
                  </label>
                  <label>
                    <span>Jitter</span>
                    <input max={1} min={0} onChange={(event) => setJitter(event.target.value)} step="0.05" type="number" value={jitter} />
                  </label>
                </div>
              </fieldset>

              <fieldset className="deploy-step">
                <legend>
                  <FileCode2 aria-hidden="true" size={16} strokeWidth={2.1} />
                  Configuration
                </legend>
                <div className="deploy-field-grid">
                  <label>
                    <span>Config mode</span>
                    <select onChange={(event) => setConfigMode(event.target.value as BeaconBuildConfigMode)} value={configMode}>
                      {configModes.map((mode) => (
                        <option key={mode} value={mode}>
                          {mode}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Artifact name</span>
                    <input onChange={(event) => setOutputName(event.target.value)} placeholder="xero-beacon-red-team" value={outputName} />
                  </label>
                  <label className="deploy-toggle">
                    <input checked={fallbackLongPoll} onChange={(event) => setFallbackLongPoll(event.target.checked)} type="checkbox" />
                    <span>Enable long-poll fallback</span>
                  </label>
                </div>
                <pre className="deploy-config-preview">{JSON.stringify(configPreview, null, 2)}</pre>
              </fieldset>

              {error ? <p className="alert-message alert-message--inline" role="alert">{error}</p> : null}

              <button className="primary-button deploy-build-button" disabled={isBuilding || !selectedTarget} type="submit">
                {isBuilding ? <Loader2 aria-hidden="true" className="spin-icon" size={15} strokeWidth={2.2} /> : <Hammer aria-hidden="true" size={15} strokeWidth={2.2} />}
                <span>{isBuilding ? 'Building' : 'Build beacon'}</span>
              </button>
            </form>
          </section>

          <aside className="workspace-panel deploy-build-history" aria-label="Beacon build history">
            <div className="panel-header">
              <div>
                <h2>Builds</h2>
                <p className="muted-text">Recent configured artifacts from the connected C2 service.</p>
              </div>
            </div>
            <div className="deploy-build-list" data-testid="beacon-build-list">
              {isLoading ? (
                <div className="task-empty-state">Loading build history.</div>
              ) : builds.length === 0 ? (
                <div className="task-empty-state">No beacon builds yet.</div>
              ) : (
                builds.map((build) => (
                  <div className="deploy-build-row" key={build.id}>
                    <div>
                      <strong>{build.artifact_filename ?? `${build.target_os}/${build.target_arch}`}</strong>
                      <span>{build.profile_name} / {formatBytes(build.artifact_size)}</span>
                      {build.status === 'succeeded' && !build.artifact_available ? (
                        <small>Artifact is missing from local C2 storage. Rebuild to recreate it.</small>
                      ) : null}
                      {build.error_message ? <small>{build.error_message}</small> : null}
                    </div>
                    <div>
                      <span className={`build-status build-status--${buildStatusClass(build)}`}>{buildStatusDisplay(build)}</span>
                      <button
                        aria-label={`Download ${build.artifact_filename ?? build.id}`}
                        className="icon-button"
                        disabled={!buildCanDownload(build) || downloadingBuildId === build.id}
                        onClick={() => void handleDownload(build)}
                        title={buildCanDownload(build) ? 'Download beacon artifact' : 'Artifact is missing from C2 storage. Rebuild to recreate it.'}
                        type="button"
                      >
                        <Download aria-hidden="true" size={15} strokeWidth={2.1} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </aside>
        </div>
      )}
    </AppShell>
  );
}
