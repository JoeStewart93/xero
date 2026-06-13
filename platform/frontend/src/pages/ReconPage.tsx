import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Crosshair, Play, RefreshCw, Search, ShieldCheck } from 'lucide-react';

import {
  createScanJob,
  getModules,
  getScanJob,
  getScanJobs,
  ModuleDefinition,
  PortScanArgs,
  ScanJob,
  ScanResultRecord,
} from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';

interface ScanFormState {
  maxThreads: string;
  portRange: string;
  targets: string;
  timeoutMs: string;
}

const initialForm: ScanFormState = {
  maxThreads: '32',
  portRange: '80,443',
  targets: '127.0.0.1',
  timeoutMs: '1000',
};

function formatDate(value: string | null): string {
  if (!value) {
    return '-';
  }
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value));
}

function progressPercent(job: ScanJob | null): number {
  if (!job || job.progress_total <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((job.progress_completed / job.progress_total) * 100));
}

function parseInteger(value: string, label: string, minimum: number, maximum: number): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new Error(`${label} must be between ${minimum} and ${maximum}.`);
  }
  return parsed;
}

function argsFromForm(form: ScanFormState): PortScanArgs {
  const targets = form.targets
    .split(/[,\n]/)
    .map((target) => target.trim())
    .filter(Boolean);
  if (targets.length === 0) {
    throw new Error('At least one target is required.');
  }
  return {
    execution_target: 'auto',
    max_threads: parseInteger(form.maxThreads, 'Max threads', 1, 256),
    port_range: form.portRange.trim(),
    targets,
    timeout_ms: parseInteger(form.timeoutMs, 'Timeout', 50, 60000),
  };
}

function resultStateLabel(result: ScanResultRecord): string {
  return `${result.host}:${result.port}`;
}

export function ReconPage() {
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const [form, setForm] = useState<ScanFormState>(initialForm);
  const [modules, setModules] = useState<ModuleDefinition[]>([]);
  const [jobs, setJobs] = useState<ScanJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null,
    [jobs, selectedJobId],
  );
  const portscanModule = modules.find((module) => module.id === 'builtin.portscan');
  const openResults = selectedJob?.results.filter((result) => result.state === 'open') ?? [];

  const loadReconState = useCallback(async () => {
    if (!connection) {
      setModules([]);
      setJobs([]);
      return;
    }
    setIsLoading(true);
    try {
      const [moduleResponse, jobResponse] = await Promise.all([
        getModules(connection.baseUrl, connection.accessToken),
        getScanJobs(connection.baseUrl, connection.accessToken, { limit: 25 }),
      ]);
      setModules(moduleResponse.items);
      setJobs(jobResponse.items);
      setError('');
      setSelectedJobId((current) => {
        if (current && jobResponse.items.some((job) => job.id === current)) {
          return current;
        }
        return jobResponse.items[0]?.id ?? '';
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to load recon state.');
    } finally {
      setIsLoading(false);
    }
  }, [connection]);

  useEffect(() => {
    const handle = window.setTimeout(() => void loadReconState(), 0);
    return () => window.clearTimeout(handle);
  }, [loadReconState]);

  useEffect(() => {
    if (!connection || !selectedJob || selectedJob.status === 'completed' || selectedJob.status === 'failed') {
      return undefined;
    }
    const handle = window.setInterval(async () => {
      try {
        const updated = await getScanJob(connection.baseUrl, connection.accessToken, selectedJob.id);
        setJobs((current) => [updated, ...current.filter((job) => job.id !== updated.id)]);
      } catch {
        // Polling is secondary to explicit refresh and realtime events.
      }
    }, 1000);
    return () => window.clearInterval(handle);
  }, [connection, selectedJob]);

  useEffect(() => {
    const event = realtime.latestEvent;
    if (!connection || !event?.type.startsWith('scan.')) {
      return undefined;
    }
    const handle = window.setTimeout(() => {
      const scanJobId = event.scope.scan_job_id;
      if (!scanJobId || typeof scanJobId !== 'string') {
        void loadReconState();
        return;
      }
      const scanJob = event.data.scan_job;
      if (scanJob && typeof scanJob === 'object') {
        setJobs((current) => [scanJob as ScanJob, ...current.filter((job) => job.id !== scanJobId)]);
        setSelectedJobId((current) => current || scanJobId);
      } else {
        void loadReconState();
      }
    }, 0);
    return () => window.clearTimeout(handle);
  }, [connection, loadReconState, realtime.latestEvent]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!connection) {
      return;
    }
    setIsSubmitting(true);
    setError('');
    setMessage('');
    try {
      const created = await createScanJob(connection.baseUrl, connection.accessToken, argsFromForm(form));
      setJobs((current) => [created, ...current.filter((job) => job.id !== created.id)]);
      setSelectedJobId(created.id);
      setMessage('Port scan queued.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to queue port scan.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AppShell description="Discovery tool orchestration" section="recon" title="Recon" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div className="recon-workspace">
          <section className="workspace-panel recon-run-panel" aria-label="Port scan runner">
            <div className="panel-header">
              <div>
                <h2>Port scan</h2>
                <p className="muted-text">Embedded scanner / {portscanModule?.version ?? '0.1.0'}</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <Crosshair size={18} strokeWidth={2} />
              </div>
            </div>

            <form className="recon-scan-form" onSubmit={handleSubmit}>
              <label className="recon-wide-field">
                Targets
                <textarea
                  aria-label="Scan targets"
                  onChange={(event) => setForm((current) => ({ ...current, targets: event.target.value }))}
                  rows={3}
                  value={form.targets}
                />
              </label>
              <label>
                Ports
                <input
                  aria-label="Port range"
                  onChange={(event) => setForm((current) => ({ ...current, portRange: event.target.value }))}
                  value={form.portRange}
                />
              </label>
              <label>
                Timeout ms
                <input
                  min={50}
                  onChange={(event) => setForm((current) => ({ ...current, timeoutMs: event.target.value }))}
                  type="number"
                  value={form.timeoutMs}
                />
              </label>
              <label>
                Max threads
                <input
                  min={1}
                  max={256}
                  onChange={(event) => setForm((current) => ({ ...current, maxThreads: event.target.value }))}
                  type="number"
                  value={form.maxThreads}
                />
              </label>
              <label>
                Execution
                <select aria-label="Execution target" value="auto" disabled>
                  <option value="auto">Auto / embedded C2</option>
                </select>
              </label>
              <div className="recon-form-actions">
                <button className="primary-button" disabled={isSubmitting} type="submit">
                  <Play aria-hidden="true" size={15} strokeWidth={2.1} />
                  <span>{isSubmitting ? 'Queueing' : 'Run scan'}</span>
                </button>
                <button className="secondary-button" disabled={isLoading} onClick={() => void loadReconState()} type="button">
                  <RefreshCw aria-hidden="true" size={15} strokeWidth={2.1} />
                  <span>{isLoading ? 'Refreshing' : 'Refresh'}</span>
                </button>
              </div>
            </form>
            {error ? <p className="task-queue-error" role="alert">{error}</p> : null}
            {message ? <p className="profile-status-message">{message}</p> : null}
          </section>

          <section className="workspace-panel recon-runs-panel" aria-label="Scan jobs">
            <div className="panel-header">
              <div>
                <h2>Runs</h2>
                <p className="muted-text">{jobs.length} recent jobs</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <Search size={18} strokeWidth={2} />
              </div>
            </div>
            <div className="recon-job-list">
              {jobs.length === 0 ? (
                <div className="empty-state">
                  <ShieldCheck aria-hidden="true" size={18} strokeWidth={2} />
                  <div>
                    <strong>No scan jobs yet.</strong>
                    <span>Run a scan against a lab target.</span>
                  </div>
                </div>
              ) : (
                jobs.map((job) => (
                  <button
                    className={`recon-job-row ${job.id === selectedJob?.id ? 'is-selected' : ''}`}
                    key={job.id}
                    onClick={() => setSelectedJobId(job.id)}
                    type="button"
                  >
                    <span>
                      <strong>{job.args.targets.join(', ')}</strong>
                      <em>{job.args.port_range} / {formatDate(job.queued_at)}</em>
                    </span>
                    <small className={`scan-status scan-status--${job.status}`}>{job.status}</small>
                  </button>
                ))
              )}
            </div>
          </section>

          <section className="workspace-panel recon-result-panel" aria-label="Scan result">
            <div className="panel-header">
              <div>
                <h2>Result</h2>
                <p className="muted-text">{selectedJob ? selectedJob.id : 'No job selected'}</p>
              </div>
            </div>
            {selectedJob ? (
              <>
                <div className="scan-progress-block">
                  <div>
                    <strong>{progressPercent(selectedJob)}%</strong>
                    <span>{selectedJob.progress_completed} / {selectedJob.progress_total} probes</span>
                  </div>
                  <div className="scan-progress-track" aria-label="Scan progress">
                    <span style={{ width: `${progressPercent(selectedJob)}%` }} />
                  </div>
                </div>
                <div className="scan-summary-grid">
                  <div>
                    <span>Open</span>
                    <strong>{selectedJob.summary.open_count ?? openResults.length}</strong>
                  </div>
                  <div>
                    <span>Ports</span>
                    <strong>{selectedJob.summary.ports_scanned ?? selectedJob.progress_total}</strong>
                  </div>
                  <div>
                    <span>Duration</span>
                    <strong>{selectedJob.summary.duration_ms ? `${selectedJob.summary.duration_ms}ms` : '-'}</strong>
                  </div>
                  <div>
                    <span>Executor</span>
                    <strong>{selectedJob.execution_target_resolved}</strong>
                  </div>
                </div>
                {selectedJob.error_message ? <p className="task-queue-error" role="alert">{selectedJob.error_message}</p> : null}
                <div className="scan-result-table-wrap">
                  <table className="scan-result-table">
                    <thead>
                      <tr>
                        <th>Endpoint</th>
                        <th>State</th>
                        <th>Latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedJob.results.length === 0 ? (
                        <tr>
                          <td colSpan={3}>No result rows yet.</td>
                        </tr>
                      ) : (
                        selectedJob.results.map((result) => (
                          <tr className={result.state === 'open' ? 'is-open' : ''} key={`${result.host}-${result.port}`}>
                            <td>{resultStateLabel(result)}</td>
                            <td>{result.state}</td>
                            <td>{result.latency_ms}ms</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="empty-state">
                <ShieldCheck aria-hidden="true" size={18} strokeWidth={2} />
                <div>
                  <strong>No result selected.</strong>
                  <span>Scan output will render here.</span>
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </AppShell>
  );
}
