import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TrafficProfilesPage } from './TrafficProfilesPage';

const mocks = vi.hoisted(() => ({
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
}));

const apiMocks = vi.hoisted(() => ({
  archiveTrafficProfile: vi.fn(),
  cloneTrafficProfile: vi.fn(),
  createTrafficProfile: vi.fn(),
  getTrafficProfiles: vi.fn(),
  getTrafficProfileVersions: vi.fn(),
  rollbackTrafficProfile: vi.fn(),
  updateTrafficProfile: vi.fn(),
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: mocks.useC2Connection,
}));

vi.mock('../useAuth', () => ({
  useAuth: mocks.useAuth,
}));

vi.mock('../api', async (importOriginal) => ({
  ...((await importOriginal()) as object),
  archiveTrafficProfile: apiMocks.archiveTrafficProfile,
  cloneTrafficProfile: apiMocks.cloneTrafficProfile,
  createTrafficProfile: apiMocks.createTrafficProfile,
  getTrafficProfiles: apiMocks.getTrafficProfiles,
  getTrafficProfileVersions: apiMocks.getTrafficProfileVersions,
  rollbackTrafficProfile: apiMocks.rollbackTrafficProfile,
  updateTrafficProfile: apiMocks.updateTrafficProfile,
}));

const profile = {
  config: {
    headers: { 'X-Profile': 'enabled' },
    jitter: 0.2,
    padding: { enabled: true, max_bytes: 64, min_bytes: 8 },
    paths: {
      frame: '/cdn-cgi/xero/{beacon_id}/frame',
      poll: '/cdn-cgi/xero/{beacon_id}/collect',
      register: '/cdn-cgi/xero/register',
      websocket: '/cdn-cgi/xero/ws',
    },
    sleep_seconds: 30,
    user_agent: 'Profile UA',
  },
  created_at: '2026-06-08T14:00:00Z',
  current_version: 1,
  description: 'Profile description',
  id: 'profile-one',
  is_archived: false,
  is_template: false,
  name: 'Profile one',
  template: 'custom',
  updated_at: '2026-06-08T14:00:00Z',
};

function renderPage() {
  return render(
    <MemoryRouter>
      <TrafficProfilesPage />
    </MemoryRouter>,
  );
}

describe('TrafficProfilesPage', () => {
  beforeEach(() => {
    apiMocks.getTrafficProfiles.mockResolvedValue({ items: [profile] });
    apiMocks.getTrafficProfileVersions.mockResolvedValue({
      items: [{ config: profile.config, created_at: profile.created_at, created_by: 'operator', id: 'version-one', profile_id: profile.id, version: 1 }],
    });
    apiMocks.createTrafficProfile.mockResolvedValue({ ...profile, id: 'profile-two', name: 'Created profile' });
    apiMocks.cloneTrafficProfile.mockResolvedValue({ ...profile, id: 'profile-copy', name: 'Profile one copy' });
    apiMocks.updateTrafficProfile.mockResolvedValue({ ...profile, current_version: 2, name: 'Profile one tuned' });
    apiMocks.rollbackTrafficProfile.mockResolvedValue({ ...profile, current_version: 2 });
    apiMocks.archiveTrafficProfile.mockResolvedValue({ ...profile, is_archived: true });
    mocks.useC2Connection.mockReturnValue({
      connection: {
        accessToken: 'c2-token',
        baseUrl: 'http://localhost:18001',
        connectedAt: '2026-06-08T00:00:00Z',
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
        operator: { created_at: '2026-06-08T00:00:00Z', id: 'operator-1', is_enabled: true, role: 'admin', username: 'admin' },
        tokenType: 'bearer',
      },
    });
  });

  it('loads profiles and saves a new custom profile', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('Profile one')).toBeTruthy();
    });

    fireEvent.click(screen.getByRole('button', { name: /New profile/ }));
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Created profile' } });
    fireEvent.change(screen.getByLabelText('User-Agent'), { target: { value: 'Created UA' } });
    fireEvent.click(screen.getByRole('button', { name: /Create profile/ }));

    await waitFor(() => {
      expect(apiMocks.createTrafficProfile).toHaveBeenCalledWith(
        'http://localhost:18001',
        'c2-token',
        expect.objectContaining({
          config: expect.objectContaining({ user_agent: 'Created UA' }),
          name: 'Created profile',
        }),
      );
    });
  });
});
