import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Crosshair, Play, RefreshCw, Search, ShieldCheck } from 'lucide-react';

import {
  createScanJob,
  getModules,
  getScanJob,
  getScanJobs,
  getScanResultChunks,
  ModuleDefinition,
  PortScanResultRecord,
  PortScanArgs,
  ScanResultChunk,
  ScanJob,
  ServiceEnumArgs,
  ServiceEnumResultRecord,
} from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { StreamOutput } from '../components/StreamOutput';
import type { StreamOutputChunk } from '../components/StreamOutput';
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

type ScanResultRecord = PortScanResultRecord | ServiceEnumResultRecord;

function isPortScanArgs(args: ScanJob['args']): args is PortScanArgs {
  return 'targets' in args && 'port_range' in args;
}

function isServiceEnumArgs(args: ScanJob['args']): args is ServiceEnumArgs {
  return 'host' in args && 'ports' in args;
}

function isPortScanResult(result: ScanResultRecord): result is PortScanResultRecord {
  return 'state' in result;
}

function isServiceEnumResult(result: ScanResultRecord): result is ServiceEnumResultRecord {
  return 'service_guess' in result;
}

function portScanResults(job: ScanJob | null): PortScanResultRecord[] {
  if (!job || job.module !== 'builtin.portscan') {
    return [];
  }
  return job.results.filter(isPortScanResult);
}

function serviceEnumResults(job: ScanJob | null): ServiceEnumResultRecord[] {
  if (!job || job.module !== 'builtin.serviceenum') {
    return [];
  }
  return job.results.filter(isServiceEnumResult);
}

function scanChunkFromRealtimeEvent(event: ReturnType<typeof useRealtime>['latestEvent']): ScanResultChunk | null {
  if (!event?.type.startsWith('scan.result.')) {
    return null;
  }
  const chunk = event.data.scan_result_chunk;
  return typeof chunk === 'object' && chunk !== null && !Array.isArray(chunk) ? chunk as ScanResultChunk : null;
}

function scanChunkKey(chunk: ScanResultChunk): string {
  return `${chunk.scan_job_id}:${chunk.sequence}:${chunk.kind}`;
}

function formatScanChunk(chunk: ScanResultChunk): string {
  const progressPrefix = `[${chunk.sequence}] ${chunk.probes_completed}/${chunk.probes_total}`;
  const results = chunk.payload.results ?? [];
  if (chunk.kind === 'summary') {
    const summary = chunk.payload.summary ?? {};
    const openCount = summary.open_count ?? results.filter(isPortScanResult).length;
    return `${progressPrefix} complete / ${openCount} open\n`;
  }
  if (results.length === 0) {
    return `${progressPrefix} progress\n`;
  }
  return `${results.map((result) => {
    if (isPortScanResult(result)) {
      return `${progressPrefix} ${result.host}:${result.port} ${result.state} ${result.latency_ms}ms`;
    }
    return `${progressPrefix} ${result.host}:${result.port} ${result.status} ${result.service_guess}`;
  }).join('\n')}\n`;
}

function scanChunksToOutput(chunks: ScanResultChunk[]): StreamOutputChunk[] {
  return chunks.map((chunk) => ({ chunk: formatScanChunk(chunk) }));
}

function scanJobTitle(job: ScanJob): string {
  if (isPortScanArgs(job.args)) {
    return job.args.targets.join(', ');
  }
  if (isServiceEnumArgs(job.args)) {
    return job.args.host;
  }
  return job.module;
}

function scanJobSubtitle(job: ScanJob): string {
  if (isPortScanArgs(job.args)) {
    return `${job.args.port_range} / ${formatDate(job.queued_at)}`;
  }
  if (isServiceEnumArgs(job.args)) {
    return `${job.args.ports.join(', ')} / ${formatDate(job.queued_at)}`;
  }
  return formatDate(job.queued_at);
}

function tlsExpiryState(result: ServiceEnumResultRecord): 'critical' | 'warning' | '' {
  if (!result.tls?.not_after) {
    return '';
  }
  const expiresAt = Date.parse(result.tls.not_after);
  if (!Number.isFinite(expiresAt)) {
    return '';
  }
  const daysUntilExpiry = (expiresAt - Date.now()) / 86_400_000;
  if (daysUntilExpiry < 0) {
    return 'critical';
  }
  return daysUntilExpiry <= 30 ? 'warning' : '';
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
  const [serviceEnumPending, setServiceEnumPending] = useState('');
  const [scanChunksByJob, setScanChunksByJob] = useState<Record<string, ScanResultChunk[]>>({});
  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null,
    [jobs, selectedJobId],
  );
  const portscanModule = modules.find((module) => module.id === 'builtin.portscan');
  const serviceenumModule = modules.find((module) => module.id === 'builtin.serviceenum');
  const selectedPortScanResults = portScanResults(selectedJob);
  const selectedServiceEnumResults = serviceEnumResults(selectedJob);
  const openResults = selectedPortScanResults.filter((result) => result.state === 'open');
  const selectedScanJobId = selectedJob?.id ?? '';
  const selectedScanChunks = useMemo(
    () => selectedScanJobId ? scanChunksByJob[selectedScanJobId] ?? [] : [],
    [scanChunksByJob, selectedScanJobId],
  );
  const selectedScanOutput = useMemo(() => scanChunksToOutput(selectedScanChunks), [selectedScanChunks]);

  const appendScanChunks = useCallback((chunks: ScanResultChunk[]) => {
    if (chunks.length === 0) {
      return;
    }
    setScanChunksByJob((current) => {
      const next = { ...current };
      for (const chunk of chunks) {
        const existing = next[chunk.scan_job_id] ?? [];
        if (existing.some((item) => scanChunkKey(item) === scanChunkKey(chunk))) {
          continue;
        }
        next[chunk.scan_job_id] = [...existing, chunk].sort((left, right) => left.sequence - right.sequence);
      }
      return next;
    });
  }, []);

  const clearSelectedScanStream = useCallback(() => {
    if (!selectedScanJobId) {
      return;
    }
    setScanChunksByJob((current) => ({ ...current, [selectedScanJobId]: [] }));
  }, [selectedScanJobId]);

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
      const chunk = scanChunkFromRealtimeEvent(event);
      if (chunk) {
        appendScanChunks([chunk]);
      }
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
  }, [appendScanChunks, connection, loadReconState, realtime.latestEvent]);

  useEffect(() => {
    if (!connection || !selectedScanJobId) {
      return undefined;
    }
    let isCancelled = false;
    void getScanResultChunks(connection.baseUrl, connection.accessToken, selectedScanJobId)
      .then((response) => {
        if (!isCancelled) {
          appendScanChunks(response.items);
        }
      })
      .catch(() => undefined);
    return () => {
      isCancelled = true;
    };
  }, [appendScanChunks, connection, selectedScanJobId]);

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

  async function handleServiceEnum(result: PortScanResultRecord): Promise<void> {
    if (!connection || !selectedJob) {
      return;
    }
    const pendingKey = `${result.host}:${result.port}`;
    setServiceEnumPending(pendingKey);
    setError('');
    setMessage('');
    try {
      const created = await createScanJob(connection.baseUrl, connection.accessToken, 'builtin.serviceenum', {
        execution_target: 'auto',
        host: result.host,
        ports: [result.port],
        probe_timeout_ms: 1000,
        source_scan_job_id: selectedJob.id,
      });
      setJobs((current) => [created, ...current.filter((job) => job.id !== created.id)]);
      setSelectedJobId(created.id);
      setMessage('Service enumeration queued.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Unable to queue service enumeration.');
    } finally {
      setServiceEnumPending('');
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
                      <strong>{scanJobTitle(job)}</strong>
                      <em>{job.module === 'builtin.serviceenum' ? 'Service enum' : 'Port scan'} / {scanJobSubtitle(job)}</em>
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
                <p className="muted-text">{selectedJob ? `${selectedJob.module} / ${selectedJob.id}` : 'No job selected'}</p>
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
                {selectedJob.module === 'builtin.portscan' ? (
                  <div className="scan-progress-stream" aria-label="Port scan progress output">
                    <StreamOutput
                      chunks={selectedScanOutput}
                      isComplete={selectedJob.status === 'completed' || selectedJob.status === 'failed'}
                      onClear={clearSelectedScanStream}
                      stream="progress"
                    />
                  </div>
                ) : null}
                <div className="scan-summary-grid">
                  <div>
                    <span>{selectedJob.module === 'builtin.serviceenum' ? 'Identified' : 'Open'}</span>
                    <strong>{selectedJob.module === 'builtin.serviceenum' ? selectedJob.summary.identified_count ?? selectedServiceEnumResults.length : selectedJob.summary.open_count ?? openResults.length}</strong>
                  </div>
                  <div>
                    <span>Ports</span>
                    <strong>{selectedJob.summary.ports_scanned ?? selectedJob.summary.ports_enumerated ?? selectedJob.progress_total}</strong>
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
                {selectedJob.module === 'builtin.portscan' && openResults.length > 0 ? (
                  <div className="recon-followup-strip">
                    <strong>{serviceenumModule?.name ?? 'Service Enumeration'}</strong>
                    <span>Run banner, HTTP, and TLS probes against open ports.</span>
                  </div>
                ) : null}
                <div className="scan-result-table-wrap">
                  {selectedJob.module === 'builtin.serviceenum' ? (
                    <table className="scan-result-table service-enum-table">
                      <thead>
                        <tr>
                          <th>Endpoint</th>
                          <th>Service</th>
                          <th>Evidence</th>
                          <th>TLS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedServiceEnumResults.length === 0 ? (
                          <tr>
                            <td colSpan={4}>No service rows yet.</td>
                          </tr>
                        ) : (
                          selectedServiceEnumResults.map((result) => {
                            const expiryState = tlsExpiryState(result);
                            return (
                              <tr className={result.status === 'identified' ? 'is-open' : ''} key={`${result.host}-${result.port}`}>
                                <td>{resultStateLabel(result)}</td>
                                <td>
                                  <span className="service-guess">{result.service_guess}</span>
                                  <small>{Math.round(result.confidence * 100)}% confidence</small>
                                </td>
                                <td>{result.banner || result.evidence[0]?.value || result.status}</td>
                                <td>
                                  {result.tls ? (
                                    <span className={`tls-expiry-badge ${expiryState ? `tls-expiry-badge--${expiryState}` : ''}`}>
                                      {result.tls.subject_cn ?? 'TLS'} / {formatDate(result.tls.not_after)}
                                    </span>
                                  ) : (
                                    <span className="muted-text">-</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  ) : (
                    <table className="scan-result-table">
                      <thead>
                        <tr>
                          <th>Endpoint</th>
                          <th>State</th>
                          <th>Latency</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedPortScanResults.length === 0 ? (
                          <tr>
                            <td colSpan={4}>No result rows yet.</td>
                          </tr>
                        ) : (
                          selectedPortScanResults.map((result) => {
                            const pendingKey = `${result.host}:${result.port}`;
                            return (
                              <tr className={result.state === 'open' ? 'is-open' : ''} key={`${result.host}-${result.port}`}>
                                <td>{resultStateLabel(result)}</td>
                                <td>{result.state}</td>
                                <td>{result.latency_ms}ms</td>
                                <td>
                                  <button
                                    className="inline-action-button"
                                    disabled={result.state !== 'open' || Boolean(serviceEnumPending)}
                                    onClick={() => void handleServiceEnum(result)}
                                    type="button"
                                  >
                                    {serviceEnumPending === pendingKey ? 'Queueing' : 'Enum'}
                                  </button>
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  )}
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
