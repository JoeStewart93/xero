import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { BeaconsDeployPage } from './BeaconsDeployPage';

const apiMocks = vi.hoisted(() => ({
  createBeaconBuild: vi.fn(),
  downloadBeaconBuildArtifact: vi.fn(),
  getBeaconBuilds: vi.fn(),
  getBeaconBuildTargets: vi.fn(),
}));

const hookMocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
}));

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return {
    ...actual,
    createBeaconBuild: apiMocks.createBeaconBuild,
    downloadBeaconBuildArtifact: apiMocks.downloadBeaconBuildArtifact,
    getBeaconBuilds: apiMocks.getBeaconBuilds,
    getBeaconBuildTargets: apiMocks.getBeaconBuildTargets,
  };
});

vi.mock('../useAuth', () => ({
  useAuth: hookMocks.useAuth,
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: hookMocks.useC2Connection,
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <BeaconsDeployPage />
    </MemoryRouter>,
  );
}

const succeededBuild = {
  artifact_available: true,
  artifact_filename: 'xero-beacon-linux-amd64.bin',
  artifact_sha256: 'abc123',
  artifact_size: 2048,
  completed_at: '2026-06-12T12:00:00Z',
  config: { c2_url: 'http://localhost:8001' },
  created_at: '2026-06-12T12:00:00Z',
  error_message: null,
  id: 'build-one',
  logs_tail: 'ok',
  profile_name: 'default',
  started_at: '2026-06-12T12:00:00Z',
  status: 'succeeded',
  target_arch: 'amd64',
  target_os: 'linux',
  updated_at: '2026-06-12T12:00:00Z',
};

describe('BeaconsDeployPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    hookMocks.useAuth.mockReturnValue({
      logout: vi.fn(),
      session: {
        accessToken: 'local-token',
        expiresAt: '2099-01-01T00:00:00Z',
        operator: { created_at: '2026-06-09T00:00:00Z', id: 'operator-1', is_enabled: true, role: 'admin', username: 'admin' },
        tokenType: 'bearer',
      },
    });
    hookMocks.useC2Connection.mockReturnValue({
      checkConnection: vi.fn(),
      connection: {
        accessToken: 'c2-token',
        baseUrl: 'http://localhost:8001',
        connectedAt: '2026-06-09T00:00:00Z',
        expiresAt: '2099-01-01T00:00:00Z',
        service: 'xero-c2-core',
        serviceRole: 'c2',
        status: 'connected',
        tokenType: 'bearer',
      },
      disconnect: vi.fn(),
      error: '',
      isChecking: false,
    });
    apiMocks.getBeaconBuildTargets.mockResolvedValue({
      items: [
        { arch: 'amd64', extension: '.bin', label: 'Linux amd64', os: 'linux' },
        { arch: 'amd64', extension: '.exe', label: 'Windows amd64', os: 'windows' },
      ],
    });
    apiMocks.getBeaconBuilds.mockResolvedValue({ items: [succeededBuild] });
    apiMocks.createBeaconBuild.mockResolvedValue({
      ...succeededBuild,
      artifact_filename: 'ops-beacon.exe',
      id: 'build-two',
      profile_name: 'ops',
      target_os: 'windows',
    });
    apiMocks.downloadBeaconBuildArtifact.mockResolvedValue(new Blob(['artifact']));
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:artifact'),
      revokeObjectURL: vi.fn(),
    });
  });

  it('shows the C2 required panel while disconnected', () => {
    hookMocks.useC2Connection.mockReturnValue({
      checkConnection: vi.fn(),
      connection: null,
      disconnect: vi.fn(),
      error: '',
      isChecking: false,
    });

    renderPage();

    expect(screen.getByRole('heading', { name: 'Xero C2 backend required' })).toBeTruthy();
    expect(apiMocks.getBeaconBuildTargets).not.toHaveBeenCalled();
  });

  it('loads build targets and recent build history', async () => {
    renderPage();

    await waitFor(() => expect(apiMocks.getBeaconBuildTargets).toHaveBeenCalledWith('http://localhost:8001', 'c2-token'));
    expect(apiMocks.getBeaconBuilds).toHaveBeenCalledWith('http://localhost:8001', 'c2-token');
    expect(screen.getByRole('heading', { name: 'Deploy builder' })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Linux amd64/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Windows amd64/ })).toBeTruthy();
    expect(within(screen.getByTestId('beacon-build-list')).getByText('xero-beacon-linux-amd64')).toBeTruthy();
    expect(within(screen.getByTestId('beacon-build-list')).queryByText('xero-beacon-linux-amd64.bin')).toBeNull();
    expect(screen.getByText('Succeeded')).toBeTruthy();
  });

  it('submits a beacon build request', async () => {
    renderPage();

    await screen.findByRole('button', { name: /Windows amd64/ });
    fireEvent.click(screen.getByRole('button', { name: /Windows amd64/ }));
    fireEvent.change(screen.getByLabelText('Profile'), { target: { value: 'ops' } });
    fireEvent.change(screen.getByLabelText('Sleep'), { target: { value: '15' } });
    fireEvent.change(screen.getByLabelText('Jitter'), { target: { value: '0.2' } });
    fireEvent.change(screen.getByLabelText('Artifact name'), { target: { value: 'ops-beacon' } });
    fireEvent.click(screen.getByRole('button', { name: 'Build beacon' }));

    await waitFor(() =>
      expect(apiMocks.createBeaconBuild).toHaveBeenCalledWith('http://localhost:8001', 'c2-token', {
        c2_url: 'http://localhost:8001',
        config_mode: 'all',
        fallback_longpoll_enabled: true,
        jitter: 0.2,
        output_name: 'ops-beacon',
        profile_name: 'ops',
        sleep_seconds: 15,
        target_arch: 'amd64',
        target_os: 'windows',
      }),
    );
    expect(await screen.findByText(/ops \/ 2.0 KiB/)).toBeTruthy();
  });

  it('downloads a completed build artifact', async () => {
    renderPage();

    await screen.findByText('xero-beacon-linux-amd64');
    const anchorClick = vi.fn();
    const anchor = { click: anchorClick } as unknown as HTMLAnchorElement;
    vi.spyOn(document, 'createElement').mockReturnValue(anchor);
    fireEvent.click(screen.getByRole('button', { name: 'Download xero-beacon-linux-amd64.bin' }));

    await waitFor(() => expect(apiMocks.downloadBeaconBuildArtifact).toHaveBeenCalledWith('http://localhost:8001', 'c2-token', 'build-one'));
    expect(anchor.download).toBe('xero-beacon-linux-amd64.bin');
    expect(anchorClick).toHaveBeenCalledTimes(1);
  });

  it('marks succeeded builds without a local artifact as unavailable', async () => {
    apiMocks.getBeaconBuilds.mockResolvedValue({
      items: [{ ...succeededBuild, artifact_available: false }],
    });
    renderPage();

    expect(await screen.findByText('Artifact missing')).toBeTruthy();
    expect(screen.getByText('Artifact is missing from local C2 storage. Rebuild to recreate it.')).toBeTruthy();
    const downloadButton = screen.getByRole('button', { name: 'Download xero-beacon-linux-amd64.bin' }) as HTMLButtonElement;
    expect(downloadButton.disabled).toBe(true);
    fireEvent.click(downloadButton);

    expect(apiMocks.downloadBeaconBuildArtifact).not.toHaveBeenCalled();
  });
});
