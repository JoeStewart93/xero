import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { Asset } from '../api';
import { InventoryPage } from './InventoryPage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  getAsset: vi.fn(),
  getAssetGroups: vi.fn(),
  getAssets: vi.fn(),
}));

vi.mock('../api', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  getAsset: apiMocks.getAsset,
  getAssetGroups: apiMocks.getAssetGroups,
  getAssets: apiMocks.getAssets,
}));

vi.mock('../useAuth', () => ({
  useAuth: mocks.useAuth,
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: mocks.useC2Connection,
}));

const beaconAsset: Asset = {
  asset_type: 'beacon_host',
  created_at: '2026-06-13T05:00:00Z',
  display_name: 'alpha.corp.local',
  domain: 'corp.local',
  first_seen: '2026-06-13T05:00:00Z',
  groups: [
    {
      criterion_type: 'subnet',
      criterion_value: '10.20.0.0/24',
      group_key: 'subnet:10.20.0.0/24',
      id: 'group-subnet',
      name: 'Subnet 10.20.0.0/24',
      source: 'auto',
      type: 'auto',
    },
  ],
  hostname: 'alpha.corp.local',
  id: 'asset-alpha',
  identifiers: [
    {
      first_seen: '2026-06-13T05:00:00Z',
      id: 'identifier-one',
      kind: 'ip',
      last_seen: '2026-06-13T05:00:00Z',
      normalized_value: '10.20.0.5',
      source: 'beacon',
      value: '10.20.0.5',
    },
  ],
  last_seen: '2026-06-13T05:10:00Z',
  linked_beacons: [
    {
      beacon_id: 'beacon-one',
      first_seen: '2026-06-13T05:00:00Z',
      hostname: 'alpha.corp.local',
      id: 'link-one',
      last_seen: '2026-06-13T05:10:00Z',
      machine_fingerprint_hash: 'fingerprint-one',
      status: 'online',
    },
  ],
  metadata: { architecture: 'x64', status: 'online' },
  observations: [
    {
      beacon_id: 'beacon-one',
      id: 'observation-one',
      observation_type: 'beacon.registered',
      observed_at: '2026-06-13T05:10:00Z',
      payload: {},
      scan_job_id: null,
      scan_result_chunk_id: null,
      source: 'beacon',
    },
  ],
  os: 'Windows 11',
  primary_ip: '10.20.0.5',
  relationships: [],
  role: 'beacon',
  source: 'beacon',
  updated_at: '2026-06-13T05:10:00Z',
};

const serviceAsset: Asset = {
  asset_type: 'service',
  created_at: '2026-06-13T05:00:00Z',
  display_name: 'ssh on 10.20.0.5:22',
  domain: null,
  first_seen: '2026-06-13T05:00:00Z',
  hostname: null,
  id: 'asset-service',
  identifiers: [],
  last_seen: '2026-06-13T05:11:00Z',
  linked_beacons: [],
  metadata: { port: 22, service_guess: 'ssh' },
  observations: [],
  os: null,
  primary_ip: '10.20.0.5',
  relationships: [
    {
      asset_id: 'asset-service',
      direction: 'inbound',
      first_seen: '2026-06-13T05:11:00Z',
      id: 'relationship-one',
      last_seen: '2026-06-13T05:11:00Z',
      metadata: { port: 22 },
      related_asset_id: 'asset-alpha',
      related_asset_name: 'alpha.corp.local',
      relationship_type: 'exposes_service',
      scan_job_id: 'scan-one',
      source: 'scan',
    },
  ],
  role: 'ssh',
  source: 'scan',
  updated_at: '2026-06-13T05:11:00Z',
};

function renderInventory() {
  return render(
    <MemoryRouter initialEntries={['/assets']}>
      <Routes>
        <Route path="/assets" element={<InventoryPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('InventoryPage', () => {
  beforeEach(() => {
    apiMocks.getAsset.mockResolvedValue(beaconAsset);
    apiMocks.getAssetGroups.mockResolvedValue({
      items: [
        {
          created_at: '2026-06-13T05:00:00Z',
          criterion_type: 'subnet',
          criterion_value: '10.20.0.0/24',
          description: 'Assets observed inside 10.20.0.0/24',
          group_key: 'subnet:10.20.0.0/24',
          id: 'group-subnet',
          member_count: 2,
          metadata: { prefix_length: 24 },
          name: 'Subnet 10.20.0.0/24',
          parent_id: null,
          rule_id: 'rule-subnet',
          type: 'auto',
          updated_at: '2026-06-13T05:00:00Z',
        },
      ],
      limit: 100,
      offset: 0,
      total: 1,
    });
    apiMocks.getAssets.mockResolvedValue({ items: [beaconAsset, serviceAsset], limit: 25, offset: 0, total: 2 });
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
    expect(apiMocks.getAssets).not.toHaveBeenCalled();
  });

  it('renders assets and selected asset detail', async () => {
    renderInventory();

    expect((await screen.findAllByText('alpha.corp.local')).length).toBeGreaterThan(0);
    expect(screen.getByText('ssh on 10.20.0.5:22')).toBeTruthy();
    expect(screen.getByText('2 assets tracked')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Subnet 10.20.0.0\/24/ })).toBeTruthy();
    expect(apiMocks.getAssets).toHaveBeenCalledWith('http://localhost:18001', 'c2-token', {
      groupId: undefined,
      limit: 25,
      offset: 0,
      q: undefined,
      source: 'all',
      type: 'all',
    });

    await waitFor(() => expect(apiMocks.getAsset).toHaveBeenCalledWith('http://localhost:18001', 'c2-token', 'asset-alpha'));
    const detail = screen.getByRole('complementary', { name: 'Asset detail' });
    expect(within(detail).getByText('Windows 11')).toBeTruthy();
    expect(within(detail).getByRole('link', { name: 'beacon-o' })).toBeTruthy();
    expect(within(detail).getByText('beacon.registered')).toBeTruthy();
    expect(within(detail).getByText('Subnet 10.20.0.0/24')).toBeTruthy();
  });

  it('filters by search, type, and source', async () => {
    renderInventory();
    await screen.findAllByText('alpha.corp.local');

    fireEvent.change(screen.getByLabelText('Search assets'), { target: { value: 'ssh' } });
    fireEvent.change(screen.getByLabelText('Filter asset type'), { target: { value: 'service' } });
    fireEvent.change(screen.getByLabelText('Filter asset source'), { target: { value: 'scan' } });

    await waitFor(() => {
      expect(apiMocks.getAssets).toHaveBeenLastCalledWith('http://localhost:18001', 'c2-token', {
        groupId: undefined,
        limit: 25,
        offset: 0,
        q: 'ssh',
        source: 'scan',
        type: 'service',
      });
    });
  });

  it('filters assets by selected automatic group', async () => {
    renderInventory();

    fireEvent.click(await screen.findByRole('button', { name: /Subnet 10.20.0.0\/24/ }));

    await waitFor(() => {
      expect(apiMocks.getAssets).toHaveBeenLastCalledWith('http://localhost:18001', 'c2-token', {
        groupId: 'group-subnet',
        limit: 25,
        offset: 0,
        q: undefined,
        source: 'all',
        type: 'all',
      });
    });
  });

  it('selects a service asset and shows relationships', async () => {
    apiMocks.getAsset.mockResolvedValueOnce(beaconAsset).mockResolvedValueOnce(serviceAsset);
    renderInventory();

    fireEvent.click(await screen.findByText('ssh on 10.20.0.5:22'));

    await waitFor(() => expect(apiMocks.getAsset).toHaveBeenLastCalledWith('http://localhost:18001', 'c2-token', 'asset-service'));
    const detail = screen.getByRole('complementary', { name: 'Asset detail' });
    expect(within(detail).getByText('exposes_service')).toBeTruthy();
    expect(within(detail).getByText('alpha.corp.local')).toBeTruthy();
    expect(within(detail).getByText('service_guess')).toBeTruthy();
  });
});
