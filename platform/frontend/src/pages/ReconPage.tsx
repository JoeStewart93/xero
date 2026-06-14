import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Compass,
  Crosshair,
  Database,
  Globe2,
  Play,
  Radar,
  Route,
  Search,
  ServerCog,
  ShieldCheck,
  SlidersHorizontal,
  Zap,
} from 'lucide-react';
import { useLocation } from 'react-router-dom';

import {
  createScanJob,
  getInfrastructureWorkers,
  getModules,
  getScanJob,
  getScanJobs,
  getScanResultChunks,
  InfrastructureWorker,
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
import { ModalShell } from '../components/ModalShell';
import { StreamOutput } from '../components/StreamOutput';
import type { StreamOutputChunk } from '../components/StreamOutput';
import { decodeLaunchArgs, stringValue } from '../modules/moduleCatalog';
import { SHODAN_API_KEY_STORAGE_KEY } from '../settingsStorage';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';

interface ScanFormState {
  allowDisruptiveScripts: string;
  dnsResolution: string;
  executionTarget: string;
  maxThreads: string;
  osDetection: string;
  portRange: string;
  scriptCategories: string[];
  scriptScanEnabled: string;
  scanTechnique: string;
  serviceDetection: string;
  targets: string;
  timingTemplate: string;
  timeoutMs: string;
}

const initialForm: ScanFormState = {
  allowDisruptiveScripts: 'disabled',
  dnsResolution: 'disabled',
  executionTarget: 'auto',
  maxThreads: '32',
  osDetection: 'disabled',
  portRange: '80,443',
  scriptCategories: ['default', 'safe'],
  scriptScanEnabled: 'disabled',
  scanTechnique: 'tcp-connect',
  serviceDetection: 'disabled',
  targets: '127.0.0.1',
  timingTemplate: '3',
  timeoutMs: '1000',
};

type ReconScanTypeId = 'nmap' | 'masscan' | 'dns' | 'path' | 'shodan';
type NmapModalTabId = 'targets' | 'detection' | 'scripts' | 'routing';

const nmapModalTabs: Array<{ icon: typeof SlidersHorizontal; id: NmapModalTabId; label: string }> = [
  { icon: SlidersHorizontal, id: 'targets', label: 'Targets' },
  { icon: Crosshair, id: 'detection', label: 'Detection' },
  { icon: AlertTriangle, id: 'scripts', label: 'Scripts' },
  { icon: ServerCog, id: 'routing', label: 'Routing' },
];

const scriptCategoryOptions = [
  { description: 'Baseline NSE script set', label: 'Default', value: 'default' },
  { description: 'Low-risk checks', label: 'Safe', value: 'safe' },
  { description: 'Host and service discovery', label: 'Discovery', value: 'discovery' },
  { description: 'Version enrichment', label: 'Version', value: 'version' },
  { description: 'Known vulnerability checks', label: 'Vuln', value: 'vuln' },
  { description: 'Auth-oriented checks', label: 'Auth', value: 'auth' },
  { description: 'Intrusive probes', label: 'Intrusive', value: 'intrusive' },
  { description: 'Potential denial checks', label: 'DoS', value: 'dos' },
  { description: 'Exploit verification', label: 'Exploit', value: 'exploit' },
];

const reconScanTypes: Array<{
  capability: string;
  description: string;
  id: ReconScanTypeId;
  label: string;
  moduleId?: string;
  status: 'Ready' | 'Configured' | 'Needs key' | 'Planned';
  icon: typeof Crosshair;
}> = [
  {
    capability: 'NMAP service and port fingerprinting',
    description: 'Queue the built-in NMAP-backed TCP port scan with explicit timing and detection options.',
    icon: Crosshair,
    id: 'nmap',
    label: 'NMAP port scan',
    moduleId: 'builtin.portscan',
    status: 'Ready',
  },
  {
    capability: 'High-speed TCP discovery',
    description: 'Prepare fast breadth scans for authorized ranges before deeper NMAP follow-up.',
    icon: Zap,
    id: 'masscan',
    label: 'MASSCAN port scan',
    status: 'Planned',
  },
  {
    capability: 'Records, zones, and resolvers',
    description: 'Stage DNS enumeration for nameservers, TXT/MX/NS records, and zone-transfer checks.',
    icon: Globe2,
    id: 'dns',
    label: 'DNS enumeration',
    status: 'Planned',
  },
  {
    capability: 'HTTP paths and content probes',
    description: 'Stage path enumeration with wordlists, status filters, and concurrency controls.',
    icon: Route,
    id: 'path',
    label: 'Path enumeration',
    status: 'Planned',
  },
  {
    capability: 'External intelligence enrichment',
    description: 'Use Shodan search once an API key is stored in Settings.',
    icon: Database,
    id: 'shodan',
    label: 'Shodan lookup',
    status: 'Needs key',
  },
];

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

function stringArrayValue(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  if (typeof value === 'string') {
    return value.split(',').map((item) => item.trim()).filter(Boolean);
  }
  return [];
}

function toggleValue(value: unknown, fallback: string): string {
  if (typeof value === 'boolean') {
    return value ? 'enabled' : 'disabled';
  }
  const normalized = stringValue(value).trim().toLowerCase();
  if (['true', 'enabled', 'on', 'yes'].includes(normalized)) {
    return 'enabled';
  }
  if (['false', 'disabled', 'off', 'no'].includes(normalized)) {
    return 'disabled';
  }
  return fallback;
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
    allow_disruptive_scripts: form.allowDisruptiveScripts === 'enabled',
    dns_resolution: form.dnsResolution === 'enabled',
    execution_target: (form.executionTarget || 'auto') as PortScanArgs['execution_target'],
    max_threads: parseInteger(form.maxThreads, 'Max threads', 1, 256),
    os_detection: form.osDetection === 'enabled',
    port_range: form.portRange.trim(),
    scan_engine: 'nmap',
    scan_technique: form.scanTechnique,
    script_categories: form.scriptScanEnabled === 'enabled' ? form.scriptCategories : [],
    script_scan_enabled: form.scriptScanEnabled === 'enabled',
    service_detection: form.serviceDetection === 'enabled',
    targets,
    timing_template: parseInteger(form.timingTemplate, 'Timing template', 0, 5),
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
  const location = useLocation();
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
  const [activeScanTypeId, setActiveScanTypeId] = useState<ReconScanTypeId | ''>('');
  const [activeNmapTab, setActiveNmapTab] = useState<NmapModalTabId>('targets');
  const [scannerWorkers, setScannerWorkers] = useState<InfrastructureWorker[]>([]);
  const [scanChunksByJob, setScanChunksByJob] = useState<Record<string, ScanResultChunk[]>>({});
  const routeModuleId = useMemo(() => new URLSearchParams(location.search).get('module') ?? '', [location.search]);
  const routeModuleArgs = useMemo(() => decodeLaunchArgs(new URLSearchParams(location.search).get('args')), [location.search]);
  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null,
    [jobs, selectedJobId],
  );
  const portscanModule = modules.find((module) => module.id === 'builtin.portscan');
  const serviceenumModule = modules.find((module) => module.id === 'builtin.serviceenum');
  const activeScanType = reconScanTypes.find((scanType) => scanType.id === activeScanTypeId) ?? null;
  const hasShodanApiKey = useMemo(() => Boolean(window.localStorage.getItem(SHODAN_API_KEY_STORAGE_KEY)?.trim()), []);
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
      setScannerWorkers([]);
      return;
    }
    setIsLoading(true);
    try {
      const [moduleResponse, jobResponse, workerResponse] = await Promise.all([
        getModules(connection.baseUrl, connection.accessToken),
        getScanJobs(connection.baseUrl, connection.accessToken, { limit: 25 }),
        getInfrastructureWorkers(connection.baseUrl, connection.accessToken),
      ]);
      setModules(moduleResponse.items);
      setJobs(jobResponse.items);
      setScannerWorkers(workerResponse.items.filter((worker) => worker.kind === 'scanner'));
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
    if (routeModuleId !== 'builtin.portscan') {
      return;
    }
    const handle = window.setTimeout(() => {
      setActiveScanTypeId('nmap');
      setForm((current) => ({
        allowDisruptiveScripts: toggleValue(routeModuleArgs.allow_disruptive_scripts, current.allowDisruptiveScripts),
        dnsResolution: toggleValue(routeModuleArgs.dns_resolution, current.dnsResolution),
        executionTarget: stringValue(routeModuleArgs.execution_target) || current.executionTarget,
        maxThreads: stringValue(routeModuleArgs.max_threads) || current.maxThreads,
        osDetection: toggleValue(routeModuleArgs.os_detection, current.osDetection),
        portRange: stringValue(routeModuleArgs.port_range) || current.portRange,
        scriptCategories: (() => {
          const categories = stringArrayValue(routeModuleArgs.script_categories);
          return categories.length > 0 ? categories : current.scriptCategories;
        })(),
        scriptScanEnabled: toggleValue(routeModuleArgs.script_scan_enabled, current.scriptScanEnabled),
        scanTechnique: stringValue(routeModuleArgs.scan_technique) || current.scanTechnique,
        serviceDetection: toggleValue(routeModuleArgs.service_detection, current.serviceDetection),
        targets: stringValue(routeModuleArgs.targets) || current.targets,
        timingTemplate: stringValue(routeModuleArgs.timing_template) || current.timingTemplate,
        timeoutMs: stringValue(routeModuleArgs.timeout_ms) || current.timeoutMs,
      }));
      setMessage('Port scan loaded from Inventory.');
    }, 0);
    return () => window.clearTimeout(handle);
  }, [routeModuleArgs, routeModuleId]);

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

  function renderPlannedScannerModal(scanType: NonNullable<typeof activeScanType>) {
    const isShodan = scanType.id === 'shodan';
    const canQueue = isShodan && hasShodanApiKey;
    return (
      <div className="recon-scanner-modal">
        <div className="recon-planned-form">
          <label>
            {isShodan ? 'Search query' : 'Targets'}
            <textarea
              aria-label={`${scanType.label} targets`}
              placeholder={isShodan ? 'ssl.cert.subject.cn:example.com' : 'example.com, 10.0.0.0/24'}
              rows={3}
            />
          </label>
          {scanType.id === 'masscan' ? (
            <>
              <label>
                Ports
                <input aria-label="MASSCAN ports" defaultValue="80,443,8080" />
              </label>
              <label>
                Rate
                <input aria-label="MASSCAN rate" defaultValue="1000" type="number" />
              </label>
            </>
          ) : null}
          {scanType.id === 'dns' ? (
            <>
              <label>
                Record types
                <input aria-label="DNS record types" defaultValue="A,AAAA,MX,NS,TXT" />
              </label>
              <label>
                Resolver
                <input aria-label="DNS resolver" defaultValue="system" />
              </label>
            </>
          ) : null}
          {scanType.id === 'path' ? (
            <>
              <label>
                Wordlist
                <input aria-label="Path wordlist" defaultValue="common.txt" />
              </label>
              <label>
                Status filter
                <input aria-label="Path status filter" defaultValue="200,204,301,302,403" />
              </label>
            </>
          ) : null}
          {isShodan ? (
            <div className={`recon-integration-state ${hasShodanApiKey ? 'is-ready' : ''}`}>
              <ShieldCheck aria-hidden="true" size={16} strokeWidth={2.1} />
              <span>{hasShodanApiKey ? 'Shodan API key is stored in Settings.' : 'Add a Shodan API key in Settings before queueing lookups.'}</span>
            </div>
          ) : (
            <div className="recon-integration-state">
              <Radar aria-hidden="true" size={16} strokeWidth={2.1} />
              <span>Scanner tooling is installed; backend queue support for this scan type is staged for the next feature slice.</span>
            </div>
          )}
        </div>
        <div className="recon-form-actions">
          <button className="primary-button" disabled={!canQueue} type="button">
            <Play aria-hidden="true" size={15} strokeWidth={2.1} />
            <span>{canQueue ? 'Queue lookup' : 'Queue unavailable'}</span>
          </button>
          <button className="secondary-button" onClick={() => setActiveScanTypeId('')} type="button">
            Close
          </button>
        </div>
      </div>
    );
  }

  function toggleScriptCategory(category: string, isChecked: boolean): void {
    setForm((current) => {
      const nextCategories = isChecked
        ? [...current.scriptCategories, category]
        : current.scriptCategories.filter((item) => item !== category);
      return { ...current, scriptCategories: Array.from(new Set(nextCategories)) };
    });
  }

  function renderNmapScannerModal() {
    return (
      <form className="recon-nmap-modal" onSubmit={handleSubmit}>
        <div className="recon-modal-tabs" role="tablist" aria-label="NMAP configuration">
          {nmapModalTabs.map((tab) => {
            const TabIcon = tab.icon;
            const isSelected = activeNmapTab === tab.id;
            return (
              <button
                aria-controls={`nmap-tab-${tab.id}`}
                aria-selected={isSelected}
                className={`recon-modal-tab ${isSelected ? 'is-selected' : ''}`}
                key={tab.id}
                onClick={() => setActiveNmapTab(tab.id)}
                role="tab"
                type="button"
              >
                <TabIcon aria-hidden="true" size={14} strokeWidth={2.1} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        <div className="recon-modal-body recon-scrollbar">
          {activeNmapTab === 'targets' ? (
            <div className="recon-tab-panel recon-field-grid" id="nmap-tab-targets" role="tabpanel">
              <label className="recon-wide-field">
                Targets
                <textarea
                  aria-label="Scan targets"
                  onChange={(event) => setForm((current) => ({ ...current, targets: event.target.value }))}
                  rows={4}
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
                Technique
                <select
                  aria-label="NMAP scan technique"
                  onChange={(event) => setForm((current) => ({ ...current, scanTechnique: event.target.value }))}
                  value={form.scanTechnique}
                >
                  <option value="tcp-connect">TCP connect</option>
                  <option value="syn">SYN</option>
                  <option value="udp">UDP</option>
                </select>
              </label>
              <label>
                Timing
                <select
                  aria-label="NMAP timing template"
                  onChange={(event) => setForm((current) => ({ ...current, timingTemplate: event.target.value }))}
                  value={form.timingTemplate}
                >
                  {[0, 1, 2, 3, 4, 5].map((template) => (
                    <option key={template} value={template}>T{template}</option>
                  ))}
                </select>
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
            </div>
          ) : null}

          {activeNmapTab === 'detection' ? (
            <div className="recon-tab-panel recon-toggle-list" id="nmap-tab-detection" role="tabpanel">
              <label className="recon-toggle-row">
                <input
                  checked={form.serviceDetection === 'enabled'}
                  onChange={(event) => setForm((current) => ({ ...current, serviceDetection: event.target.checked ? 'enabled' : 'disabled' }))}
                  type="checkbox"
                />
                <span>
                  <strong>Service discovery</strong>
                  <small>NMAP -sV probes and version hints.</small>
                </span>
              </label>
              <label className="recon-toggle-row">
                <input
                  checked={form.osDetection === 'enabled'}
                  onChange={(event) => setForm((current) => ({ ...current, osDetection: event.target.checked ? 'enabled' : 'disabled' }))}
                  type="checkbox"
                />
                <span>
                  <strong>OS fingerprinting</strong>
                  <small>NMAP -O fingerprint collection.</small>
                </span>
              </label>
              <label className="recon-toggle-row">
                <input
                  checked={form.dnsResolution === 'enabled'}
                  onChange={(event) => setForm((current) => ({ ...current, dnsResolution: event.target.checked ? 'enabled' : 'disabled' }))}
                  type="checkbox"
                />
                <span>
                  <strong>DNS resolution</strong>
                  <small>Resolve names instead of forcing numeric output.</small>
                </span>
              </label>
            </div>
          ) : null}

          {activeNmapTab === 'scripts' ? (
            <div className="recon-tab-panel recon-script-panel" id="nmap-tab-scripts" role="tabpanel">
              <label className="recon-toggle-row">
                <input
                  checked={form.scriptScanEnabled === 'enabled'}
                  onChange={(event) => setForm((current) => ({ ...current, scriptScanEnabled: event.target.checked ? 'enabled' : 'disabled' }))}
                  type="checkbox"
                />
                <span>
                  <strong>Enable NSE scripts</strong>
                  <small>Run selected NMAP script categories after discovery.</small>
                </span>
              </label>
              <div className="recon-script-grid" aria-label="NMAP script categories">
                {scriptCategoryOptions.map((option) => (
                  <label className="recon-script-option" key={option.value}>
                    <input
                      checked={form.scriptCategories.includes(option.value)}
                      disabled={form.scriptScanEnabled !== 'enabled'}
                      onChange={(event) => toggleScriptCategory(option.value, event.target.checked)}
                      type="checkbox"
                    />
                    <span>
                      <strong>{option.label}</strong>
                      <small>{option.description}</small>
                    </span>
                  </label>
                ))}
              </div>
              <label className="recon-toggle-row recon-toggle-row--danger">
                <input
                  checked={form.allowDisruptiveScripts === 'enabled'}
                  disabled={form.scriptScanEnabled !== 'enabled'}
                  onChange={(event) => setForm((current) => ({ ...current, allowDisruptiveScripts: event.target.checked ? 'enabled' : 'disabled' }))}
                  type="checkbox"
                />
                <span>
                  <strong>Allow disruptive script categories</strong>
                  <small>Required for intrusive, DoS, exploit, and similar categories.</small>
                </span>
              </label>
            </div>
          ) : null}

          {activeNmapTab === 'routing' ? (
            <div className="recon-tab-panel recon-field-grid" id="nmap-tab-routing" role="tabpanel">
              <label className="recon-wide-field">
                Scanner routing
                <select
                  aria-label="Scanner routing"
                  onChange={(event) => setForm((current) => ({ ...current, executionTarget: event.target.value }))}
                  value={form.executionTarget}
                >
                  <option value="auto">Auto load-balanced</option>
                  <option value="distributed">Distribute across scanners</option>
                  {scannerWorkers.map((worker) => (
                    <option key={worker.id} value={`scanner:${worker.id}`}>
                      {worker.name} / {worker.status} / load {worker.current_load}/{worker.capacity}
                    </option>
                  ))}
                </select>
              </label>
              <div className="recon-routing-summary">
                <div>
                  <span>Available scanners</span>
                  <strong>{scannerWorkers.length}</strong>
                </div>
                <div>
                  <span>Online</span>
                  <strong>{scannerWorkers.filter((worker) => worker.status === 'online').length}</strong>
                </div>
                <div>
                  <span>Mode</span>
                  <strong>{form.executionTarget === 'distributed' ? 'Distributed' : form.executionTarget.startsWith('scanner:') ? 'Specific' : 'Auto'}</strong>
                </div>
              </div>
              <div className="recon-scanner-roster recon-scrollbar" aria-label="Scanner workers">
                {scannerWorkers.length === 0 ? (
                  <div className="recon-scanner-roster-row">
                    <strong>No scanners registered</strong>
                    <span>Embedded scanner will be created by the C2 API.</span>
                    <em>pending</em>
                  </div>
                ) : (
                  scannerWorkers.map((worker) => (
                    <div className="recon-scanner-roster-row" key={worker.id}>
                      <strong>{worker.name}</strong>
                      <span>{worker.origin} / {worker.version ?? 'unknown'}</span>
                      <small>{worker.current_load}/{worker.capacity}</small>
                      <em className={`is-${worker.status}`}>{worker.status}</em>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}
        </div>

        <div className="recon-modal-footer">
          <div className="recon-modal-status">
            {error ? <p className="task-queue-error" role="alert">{error}</p> : null}
            {message ? <p className="profile-status-message">{message}</p> : null}
          </div>
          <div className="recon-modal-actions">
            <button className="secondary-button" onClick={() => setActiveScanTypeId('')} type="button">
              Close
            </button>
            <button className="primary-button" disabled={isSubmitting} type="submit">
              <Play aria-hidden="true" size={15} strokeWidth={2.1} />
              <span>{isSubmitting ? 'Queueing' : 'Run scan'}</span>
            </button>
          </div>
        </div>
      </form>
    );
  }

  function renderScanTypeModal() {
    if (!activeScanType) {
      return null;
    }

    const ActiveIcon = activeScanType.icon;
    const isNmap = activeScanType.id === 'nmap';
    return (
      <ModalShell
        ariaLabel={`${activeScanType.label} launcher`}
        onClose={() => setActiveScanTypeId('')}
        subtitle={activeScanType.capability}
        title={activeScanType.label}
        variant="wide"
      >
        <div className="recon-scanner-modal">
          <div className="recon-scanner-modal-head">
            <div className="panel-icon" aria-hidden="true">
              <ActiveIcon size={18} strokeWidth={2} />
            </div>
            <p>{activeScanType.description}</p>
          </div>

          {isNmap ? renderNmapScannerModal() : (
            renderPlannedScannerModal(activeScanType)
          )}
        </div>
      </ModalShell>
    );
  }

  return (
    <AppShell description="Discovery tool orchestration" section="recon" title="Recon" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <div aria-busy={isLoading} className="recon-workspace">
          <section className="workspace-panel recon-scan-types-panel" aria-label="Recon scan types">
            <div className="panel-header">
              <div>
                <h2>Scanners</h2>
                <p className="muted-text">Embedded scanner / {portscanModule?.version ?? '0.1.0'}</p>
              </div>
              <div className="panel-icon" aria-hidden="true">
                <Compass size={18} strokeWidth={2} />
              </div>
            </div>

            <div className="recon-scan-type-list">
              {reconScanTypes.map((scanType) => {
                const Icon = scanType.icon;
                const status = scanType.id === 'shodan' && hasShodanApiKey ? 'Configured' : scanType.status;
                return (
                  <button
                    className="recon-scan-type-card"
                    key={scanType.id}
                    onClick={() => {
                      setActiveScanTypeId(scanType.id);
                      if (scanType.id === 'nmap') {
                        setActiveNmapTab('targets');
                      }
                      setError('');
                      setMessage('');
                    }}
                    type="button"
                  >
                    <Icon aria-hidden="true" size={16} strokeWidth={2.1} />
                    <span>
                      <strong>{scanType.label}</strong>
                      <small>{scanType.capability}</small>
                    </span>
                    <em className={status === 'Ready' || status === 'Configured' ? 'is-ready' : ''}>{status}</em>
                  </button>
                );
              })}
            </div>
            {error && !activeScanType ? <p className="task-queue-error" role="alert">{error}</p> : null}
            {message && !activeScanType ? <p className="profile-status-message">{message}</p> : null}
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
                    <span className="recon-job-main">
                      <strong>{scanJobTitle(job)}</strong>
                      <em>{job.module === 'builtin.serviceenum' ? 'Service enum' : 'Port scan'} / {scanJobSubtitle(job)}</em>
                    </span>
                    <small className={`scan-status scan-status--${job.status}`}>{job.status}</small>
                  </button>
                ))
              )}
            </div>
          </section>

          <section className="workspace-panel recon-result-panel" aria-label="Quick scan results">
            <div className="panel-header">
              <div>
                <h2>Quick results</h2>
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
      {renderScanTypeModal()}
    </AppShell>
  );
}
