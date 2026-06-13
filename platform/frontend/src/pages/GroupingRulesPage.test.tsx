import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { GroupingRulesPage } from './GroupingRulesPage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  getGroupingRules: vi.fn(),
  rerunGrouping: vi.fn(),
  updateGroupingRules: vi.fn(),
}));

vi.mock('../api', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  getGroupingRules: apiMocks.getGroupingRules,
  rerunGrouping: apiMocks.rerunGrouping,
  updateGroupingRules: apiMocks.updateGroupingRules,
}));

vi.mock('../useAuth', () => ({
  useAuth: mocks.useAuth,
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: mocks.useC2Connection,
}));

const defaultRules = [
  {
    config: { prefix_length: 24 },
    created_at: '2026-06-13T05:00:00Z',
    enabled: true,
    id: 'rule-subnet',
    rule_key: 'subnet',
    updated_at: '2026-06-13T05:00:00Z',
    updated_by: 'system',
    version: 1,
  },
  {
    config: { include_workgroups: true },
    created_at: '2026-06-13T05:00:00Z',
    enabled: true,
    id: 'rule-domain',
    rule_key: 'domain',
    updated_at: '2026-06-13T05:00:00Z',
    updated_by: 'system',
    version: 1,
  },
  {
    config: { require_version: true },
    created_at: '2026-06-13T05:00:00Z',
    enabled: true,
    id: 'rule-os',
    rule_key: 'os',
    updated_at: '2026-06-13T05:00:00Z',
    updated_by: 'system',
    version: 1,
  },
] as const;

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/settings/grouping']}>
      <Routes>
        <Route path="/settings/grouping" element={<GroupingRulesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('GroupingRulesPage', () => {
  beforeEach(() => {
    apiMocks.getGroupingRules.mockResolvedValue({ items: defaultRules });
    apiMocks.rerunGrouping.mockResolvedValue({ added: 1, assets_processed: 3, purge_disabled: false, removed: 0, touched: 2 });
    apiMocks.updateGroupingRules.mockResolvedValue({ items: defaultRules });
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

    renderPage();

    expect(screen.getByRole('heading', { name: 'Xero C2 backend required' })).toBeTruthy();
    expect(apiMocks.getGroupingRules).not.toHaveBeenCalled();
  });

  it('renders grouping rules and updates rule state', async () => {
    renderPage();

    expect(await screen.findByText('Subnet grouping')).toBeTruthy();
    fireEvent.click(screen.getAllByRole('button', { name: 'Disable' })[0]);

    await waitFor(() => {
      expect(apiMocks.updateGroupingRules).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        [{ config: { prefix_length: 24 }, enabled: false, rule_key: 'subnet' }],
        { rerun: true },
      );
    });
  });

  it('updates subnet prefix and manually reruns grouping', async () => {
    renderPage();

    const prefixInput = await screen.findByLabelText('Prefix length');
    fireEvent.change(prefixInput, { target: { value: '16' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply Prefix' }));
    fireEvent.click(screen.getByRole('button', { name: 'Rerun' }));

    await waitFor(() => {
      expect(apiMocks.updateGroupingRules).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        [{ config: { prefix_length: 16 }, rule_key: 'subnet' }],
        { rerun: true },
      );
      expect(apiMocks.rerunGrouping).toHaveBeenCalledWith('http://localhost:18001', 'c2-token');
    });
  });
});
