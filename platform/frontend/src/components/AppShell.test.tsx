import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ACTIVE_PROJECT_STORAGE_KEY, PROJECT_STORAGE_KEY } from '../projectScopeStorage';
import { AppShell } from './AppShell';

const mocks = vi.hoisted(() => ({
  logout: vi.fn(),
  useAuth: vi.fn(),
  useC2Connection: vi.fn(),
}));

vi.mock('../useAuth', () => ({
  useAuth: mocks.useAuth,
}));

vi.mock('../useC2Connection', () => ({
  useC2Connection: mocks.useC2Connection,
}));

const session = {
  accessToken: 'local-token',
  expiresAt: '2099-01-01T00:00:00Z',
  operator: { created_at: '2026-06-13T06:00:00Z', id: 'operator-1', is_enabled: true, role: 'admin', username: 'admin' },
  tokenType: 'bearer',
};

function renderShell() {
  return render(
    <MemoryRouter>
      <AppShell description="Test shell" section="home" title="Home">
        <div>Shell content</div>
      </AppShell>
    </MemoryRouter>,
  );
}

describe('AppShell', () => {
  beforeEach(() => {
    window.localStorage.clear();
    mocks.logout.mockReset();
    mocks.useAuth.mockReturnValue({ logout: mocks.logout, session });
    mocks.useC2Connection.mockReturnValue({
      connection: {
        accessToken: 'c2-token',
        baseUrl: 'http://localhost:18001',
        connectedAt: '2026-06-13T06:00:00Z',
        expiresAt: '2099-01-01T00:00:00Z',
        service: 'xero-c2-core',
        serviceRole: 'c2',
        status: 'connected',
        tokenType: 'bearer',
      },
    });
  });

  it('opens create actions from the top bar and routes tasking to the modal-ready URL', () => {
    renderShell();

    fireEvent.click(screen.getByRole('button', { name: 'Create resource' }));

    const menu = screen.getByRole('menu', { name: 'Create resource' });
    expect(within(menu).getByRole('menuitem', { name: /Project/ }).getAttribute('href')).toBe('/projects?create=1');
    expect(within(menu).getByRole('menuitem', { name: /Task/ }).getAttribute('href')).toBe('/beacons?module=shell');
    expect(within(menu).getByRole('menuitem', { name: /Target/ }).getAttribute('href')).toBe('/projects?create=1');
    expect(within(menu).getByRole('menuitem', { name: /Resource/ }).getAttribute('href')).toBe('/assets');
  });

  it('opens notification management without wiring a backend notification system', () => {
    renderShell();

    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }));

    const menu = screen.getByRole('menu', { name: 'Notifications' });
    expect(within(menu).getByText('No notifications')).toBeTruthy();
    expect(within(menu).getByRole('menuitem', { name: 'Manage notifications' }).getAttribute('href')).toBe('/settings/notifications');
  });

  it('keeps Global scope visible and closes shell menus on outside click and Escape', () => {
    window.localStorage.setItem(PROJECT_STORAGE_KEY, JSON.stringify([{ id: 'project-a', name: 'project a', targets: [] }]));
    window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, 'project-a');

    renderShell();

    expect(screen.getByLabelText('Active project scope').textContent).toContain('project a');

    fireEvent.click(screen.getByRole('button', { name: 'Create resource' }));
    expect(screen.getByRole('menu', { name: 'Create resource' })).toBeTruthy();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('menu', { name: 'Create resource' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Notifications' }));
    expect(screen.getByRole('menu', { name: 'Notifications' })).toBeTruthy();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('menu', { name: 'Notifications' })).toBeNull();

    fireEvent.click(screen.getByLabelText('Active project scope'));
    fireEvent.click(screen.getByRole('option', { name: /Global/ }));
    expect(screen.getByLabelText('Active project scope').textContent).toContain('Global');
  });
});
