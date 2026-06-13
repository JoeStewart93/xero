import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { encodeLaunchArgs } from '../modules/moduleCatalog';
import { ReconPage } from './ReconPage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
  useRealtime: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  createScanJob: vi.fn(),
  getModules: vi.fn(),
  getScanJob: vi.fn(),
  getScanJobs: vi.fn(),
  getScanResultChunks: vi.fn(),
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: mocks.useC2Connection,
}));

vi.mock('../useAuth', () => ({
  useAuth: mocks.useAuth,
}));

vi.mock('../useRealtime', () => ({
  useRealtime: mocks.useRealtime,
}));

vi.mock('../api', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  createScanJob: apiMocks.createScanJob,
  getModules: apiMocks.getModules,
  getScanJob: apiMocks.getScanJob,
  getScanJobs: apiMocks.getScanJobs,
  getScanResultChunks: apiMocks.getScanResultChunks,
}));

const completedScan = {
  actor_subject: 'operator-one',
  args: {
    execution_target: 'auto',
    max_threads: 8,
    port_range: '80,443',
    targets: ['127.0.0.1'],
    timeout_ms: 1000,
  },
  completed_at: '2026-06-13T05:00:00Z',
  created_at: '2026-06-13T05:00:00Z',
  error_message: null,
  execution_target_requested: 'auto',
  execution_target_resolved: 'embedded-c2',
  id: 'scan-one',
  module: 'builtin.portscan',
  progress_completed: 2,
  progress_total: 2,
  queued_at: '2026-06-13T05:00:00Z',
  results: [
    { host: '127.0.0.1', latency_ms: 2.5, port: 80, state: 'open' },
    { host: '127.0.0.1', latency_ms: 1.1, port: 443, state: 'closed' },
  ],
  started_at: '2026-06-13T05:00:00Z',
  state_counts: { closed: 1, filtered: 0, open: 1 },
  status: 'completed',
  summary: { duration_ms: 20.4, hosts_scanned: 1, open_count: 1, ports_scanned: 2 },
  updated_at: '2026-06-13T05:00:00Z',
  worker_id: 'worker-one',
};

function renderPage(initialEntries = ['/recon']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ReconPage />
    </MemoryRouter>,
  );
}

describe('ReconPage', () => {
  beforeEach(() => {
    apiMocks.getModules.mockResolvedValue({
      items: [
        { id: 'builtin.portscan', name: 'Port Scan', version: '0.1.0' },
        { id: 'builtin.serviceenum', name: 'Service Enumeration', version: '0.1.0' },
      ],
    });
    apiMocks.getScanJobs.mockResolvedValue({ items: [completedScan] });
    apiMocks.getScanJob.mockResolvedValue(completedScan);
    apiMocks.getScanResultChunks.mockResolvedValue({ items: [] });
    apiMocks.createScanJob.mockResolvedValue({ ...completedScan, id: 'scan-two', status: 'queued' });
    mocks.useC2Connection.mockReturnValue({
      connection: {
        accessToken: 'c2-token',
        baseUrl: 'http://localhost:18001',
        connectedAt: '2026-06-13T00:00:00Z',
        expiresAt: '2099-01-01T00:00:00Z',
        service: 'xero-c2-core',
        serviceRole: 'c2',
        status: 'connected',
        tokenType: 'bearer',
      },
    });
    mocks.useAuth.mockReturnValue({
      logout: vi.fn(),
      session: {
        accessToken: 'local-token',
        expiresAt: '2099-01-01T00:00:00Z',
        operator: { created_at: '2026-06-13T00:00:00Z', id: 'operator-1', is_enabled: true, role: 'admin', username: 'admin' },
        tokenType: 'bearer',
      },
    });
    mocks.useRealtime.mockReturnValue({
      activeBeaconCount: 0,
      beaconCount: 0,
      beacons: [],
      error: '',
      latestEvent: null,
      offlineBeaconCount: 0,
      status: 'connected',
    });
  });

  it('loads scan jobs and queues a port scan', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/scan-one/)).toBeTruthy();
    });
    expect(screen.getByText('127.0.0.1:80')).toBeTruthy();
    expect(within(screen.getByRole('table')).getByText('open')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /NMAP port scan/ }));
    fireEvent.change(screen.getByLabelText('Scan targets'), { target: { value: '127.0.0.1' } });
    fireEvent.change(screen.getByLabelText('Port range'), { target: { value: '8000,9000' } });
    fireEvent.click(screen.getByRole('button', { name: /Run scan/ }));

    await waitFor(() => {
      expect(apiMocks.createScanJob).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        expect.objectContaining({
          execution_target: 'auto',
          port_range: '8000,9000',
          targets: ['127.0.0.1'],
        }),
      );
    });
  });

  it('loads port scan args from Inventory launch query params', async () => {
    const launchArgs = encodeLaunchArgs({
      max_threads: 4,
      port_range: '22,443',
      targets: ['127.0.0.1', 'localhost'],
      timeout_ms: 750,
    });

    renderPage([`/recon?module=builtin.portscan&args=${launchArgs}`]);

    expect(await screen.findByText('Port scan loaded from Inventory.')).toBeTruthy();
    expect((screen.getByLabelText('Scan targets') as HTMLTextAreaElement).value).toBe('127.0.0.1,localhost');
    expect((screen.getByLabelText('Port range') as HTMLInputElement).value).toBe('22,443');
    expect((screen.getByLabelText('Timeout ms') as HTMLInputElement).value).toBe('750');
    expect((screen.getByLabelText('Max threads') as HTMLInputElement).value).toBe('4');
  });

  it('queues service enumeration from an open port scan result', async () => {
    apiMocks.createScanJob.mockResolvedValue({
      ...completedScan,
      args: {
        execution_target: 'auto',
        host: '127.0.0.1',
        ports: [80],
        probe_timeout_ms: 1000,
        source_scan_job_id: 'scan-one',
      },
      id: 'service-enum-one',
      module: 'builtin.serviceenum',
      results: [],
      status: 'queued',
      summary: {},
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('127.0.0.1:80')).toBeTruthy();
    });
    const enumButton = screen.getAllByRole('button', { name: 'Enum' }).find((button) => !(button as HTMLButtonElement).disabled);
    expect(enumButton).toBeTruthy();
    fireEvent.click(enumButton as HTMLButtonElement);

    await waitFor(() => {
      expect(apiMocks.createScanJob).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        'builtin.serviceenum',
        expect.objectContaining({
          execution_target: 'auto',
          host: '127.0.0.1',
          ports: [80],
          source_scan_job_id: 'scan-one',
        }),
      );
    });
  });

  it('renders service enumeration details and TLS expiry warning', async () => {
    apiMocks.getScanJobs.mockResolvedValue({
      items: [
        {
          ...completedScan,
          args: {
            execution_target: 'auto',
            host: '127.0.0.1',
            ports: [443],
            probe_timeout_ms: 1000,
            source_scan_job_id: 'scan-one',
          },
          id: 'service-enum-one',
          module: 'builtin.serviceenum',
          results: [
            {
              banner: '',
              confidence: 0.9,
              error: null,
              evidence: [{ type: 'http.response', value: 'HTTP/1.1 200 OK' }],
              host: '127.0.0.1',
              latency_ms: 4.2,
              port: 443,
              service_guess: 'https',
              status: 'identified',
              tls: {
                issuer_cn: 'lab.local',
                not_after: new Date(Date.now() + 7 * 86_400_000).toISOString(),
                not_before: '2026-06-13T00:00:00Z',
                sans: ['lab.local'],
                serial_number: '123',
                subject_cn: 'lab.local',
              },
              transport: 'tcp',
            },
          ],
          state_counts: { error: 0, identified: 1, skipped: 0, timeout: 0, unknown: 0 },
          summary: { duration_ms: 8.4, host: '127.0.0.1', identified_count: 1, ports_enumerated: 1 },
        },
      ],
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('https')).toBeTruthy();
    });
    expect(screen.getByText('90% confidence')).toBeTruthy();
    expect(screen.getByText(/lab.local/).className).toContain('tls-expiry-badge--warning');
  });

  it('renders line-by-line port scan progress chunks', async () => {
    apiMocks.getScanResultChunks.mockResolvedValue({
      items: [
        {
          created_at: '2026-06-13T05:00:01Z',
          emitted_at: '2026-06-13T05:00:01Z',
          id: 'chunk-one',
          kind: 'progress',
          payload: {
            results: [
              { host: '127.0.0.1', latency_ms: 2.5, port: 80, state: 'open' },
              { host: '127.0.0.1', latency_ms: 1.1, port: 443, state: 'closed' },
            ],
            state_counts: { closed: 1, filtered: 0, open: 1 },
          },
          probes_completed: 2,
          probes_total: 2,
          scan_job_id: 'scan-one',
          sequence: 1,
        },
      ],
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/scan-one/)).toBeTruthy();
    });

    await waitFor(() => {
      const output = screen.getByTestId('stream-output-buffer').textContent;
      expect(output).toContain('[1] 2/2 127.0.0.1:80 open 2.5ms');
      expect(output).toContain('[1] 2/2 127.0.0.1:443 closed 1.1ms');
    });
    expect(screen.getByText('Live progress')).toBeTruthy();
  });
});
