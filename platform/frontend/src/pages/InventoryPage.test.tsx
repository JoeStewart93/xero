import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ModuleDefinition } from '../api';
import { decodeLaunchArgs } from '../modules/moduleCatalog';
import { InventoryPage } from './InventoryPage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  getModules: vi.fn(),
}));

vi.mock('../api', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  getModules: apiMocks.getModules,
}));

vi.mock('../useAuth', () => ({
  useAuth: mocks.useAuth,
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: mocks.useC2Connection,
}));

const portscanModule: ModuleDefinition = {
  args_schema: {
    properties: {
      execution_target: { default: 'auto', enum: ['auto'], type: 'string' },
      max_threads: { default: 32, minimum: 1, type: 'integer' },
      port_range: { default: '80,443', type: 'string' },
      targets: { items: { type: 'string' }, type: 'array' },
      timeout_ms: { default: 1000, minimum: 50, type: 'integer' },
    },
    required: ['targets', 'port_range'],
    type: 'object',
  },
  author: 'Xero',
  category: 'scanning',
  description: 'Run a TCP connect scan against target hosts.',
  example: {
    args: {
      execution_target: 'auto',
      max_threads: 32,
      port_range: '22,80,443',
      targets: ['127.0.0.1'],
      timeout_ms: 1000,
    },
    module: 'builtin.portscan',
  },
  execution_kind: 'scan-job',
  id: 'builtin.portscan',
  name: 'Port Scan',
  required_capabilities: ['tcp-connect'],
  result_schema: {},
  source: 'builtin',
  status: 'enabled',
  supported_execution_targets: ['auto'],
  tags: ['recon', 'tcp'],
  version: '0.1.0',
};

const shellModule: ModuleDefinition = {
  args_schema: {
    properties: {
      command: { minLength: 1, type: 'string' },
      shell_type: { default: 'auto', enum: ['auto', 'bash', 'cmd', 'powershell'], type: 'string' },
      timeout_seconds: { default: 60, minimum: 1, type: 'integer' },
    },
    required: ['command'],
    type: 'object',
  },
  author: 'Xero',
  category: 'utility',
  description: 'Queue a shell command for an active beacon.',
  example: { args: { command: 'whoami', shell_type: 'auto', timeout_seconds: 60 }, module: 'shell' },
  execution_kind: 'beacon-task',
  id: 'shell',
  name: 'Shell Command',
  required_capabilities: [],
  result_schema: {},
  source: 'builtin',
  status: 'enabled',
  supported_execution_targets: ['beacon'],
  tags: ['command'],
  version: '1.0.0',
};

const pluginModule: ModuleDefinition = {
  args_schema: {
    properties: {
      target: { type: 'string' },
    },
    required: ['target'],
    type: 'object',
  },
  author: 'Acme Labs',
  category: 'post-exploitation',
  description: 'Demonstrates plugin metadata in the inventory.',
  disabled_reason: 'Plugin runtime is not connected.',
  example: { args: { target: 'beacon-alpha' }, module: 'plugin.acme.demo' },
  execution_kind: 'beacon-task',
  id: 'plugin.acme.demo',
  name: 'Acme Plugin Demo',
  plugin_id: 'acme-demo',
  required_capabilities: [],
  result_schema: {},
  source: 'plugin',
  status: 'disabled',
  supported_execution_targets: ['beacon'],
  tags: ['plugin'],
  updated_at: '2026-06-13T05:00:00Z',
  version: '0.2.0',
};

function LocationProbe() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const args = decodeLaunchArgs(params.get('args'));
  return (
    <div data-testid="location-probe">
      <span>{location.pathname}</span>
      <span>{params.get('module')}</span>
      <span>{JSON.stringify(args)}</span>
    </div>
  );
}

function renderInventory(initialEntries = ['/assets']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/assets" element={<InventoryPage />} />
        <Route path="/recon" element={<LocationProbe />} />
        <Route path="/beacons" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('InventoryPage', () => {
  beforeEach(() => {
    apiMocks.getModules.mockResolvedValue({ items: [portscanModule, shellModule, pluginModule] });
    mocks.useAuth.mockReturnValue({
      logout: vi.fn(),
      session: {
        accessToken: 'local-token',
        expiresAt: '2099-01-01T00:00:00Z',
        operator: { created_at: '2026-06-13T00:00:00Z', id: 'operator-1', is_enabled: true, role: 'admin', username: 'admin' },
        tokenType: 'bearer',
      },
    });
    mocks.useC2Connection.mockReturnValue({
      checkConnection: vi.fn(),
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
      disconnect: vi.fn(),
      error: '',
      isChecking: false,
    });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('requires an active C2 connection', () => {
    mocks.useC2Connection.mockReturnValue({
      checkConnection: vi.fn(),
      connection: null,
      disconnect: vi.fn(),
      error: '',
      isChecking: false,
    });

    renderInventory();

    expect(screen.getByRole('heading', { name: 'Xero C2 backend required' })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Inventory' })).toBeNull();
  });

  it('renders and filters the C2 module catalog', async () => {
    renderInventory();

    expect(await screen.findByRole('button', { name: /Port Scan/ })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Shell Command/ })).toBeTruthy();
    expect(screen.getByText('3 modules available')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Search modules'), { target: { value: 'shell' } });

    expect(screen.getByRole('button', { name: /Shell Command/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Port Scan/ })).toBeNull();

    fireEvent.change(screen.getByLabelText('Search modules'), { target: { value: '' } });
    fireEvent.change(screen.getByLabelText('Filter module category'), { target: { value: 'scanning' } });

    expect(screen.getByRole('button', { name: /Port Scan/ })).toBeTruthy();
    expect(screen.queryByRole('button', { name: /Shell Command/ })).toBeNull();
  });

  it('shows schema, plugin metadata, and copyable example JSON', async () => {
    renderInventory();

    fireEvent.click(await screen.findByRole('button', { name: /Acme Plugin Demo/ }));

    expect(screen.getAllByText('Acme Labs').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Plugin').length).toBeGreaterThan(0);
    expect(screen.getAllByText('disabled').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Updated/).length).toBeGreaterThan(0);
    expect(screen.getByRole('alert').textContent).toContain('Plugin runtime is not connected.');
    expect(within(screen.getByRole('table')).getByText('target')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));

    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining('"plugin.acme.demo"'));
    });
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeTruthy();
  });

  it('opens compatible scan modules in Recon with encoded example args', async () => {
    renderInventory();

    fireEvent.click(await screen.findByRole('button', { name: /Port Scan/ }));
    fireEvent.click(screen.getByRole('button', { name: /Open in Recon/ }));

    const probe = await screen.findByTestId('location-probe');
    expect(probe.textContent).toContain('/recon');
    expect(probe.textContent).toContain('builtin.portscan');
    expect(probe.textContent).toContain('"targets":["127.0.0.1"]');
    expect(probe.textContent).toContain('"port_range":"22,80,443"');
  });
});
