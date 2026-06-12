import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import { AuthProvider } from '../auth';
import { AUTH_STORAGE_KEY } from '../authStorage';
import { C2ConnectionProvider } from '../c2Connection';
import { C2_CONNECTION_STORAGE_KEY } from '../c2ConnectionStorage';
import { ACTIVE_PROJECT_STORAGE_KEY, PROJECT_STORAGE_KEY } from '../projectScopeStorage';
import { RealtimeProvider } from '../realtime';

function seedAuthenticatedSession() {
  window.sessionStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({
      accessToken: 'test-token',
      expiresAt: new Date(Date.now() + 60_000).toISOString(),
      operator: {
        created_at: new Date().toISOString(),
        id: '00000000-0000-0000-0000-000000000001',
        is_enabled: true,
        role: 'admin',
        username: 'admin',
      },
      tokenType: 'bearer',
    }),
  );
}

function seedC2Connection() {
  window.localStorage.setItem(
    C2_CONNECTION_STORAGE_KEY,
    JSON.stringify({
      accessToken: 'c2-token',
      baseUrl: 'http://localhost:18001',
      connectedAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 60_000).toISOString(),
      service: 'xero-c2-core',
      serviceRole: 'c2',
      status: 'ready',
      tokenType: 'bearer',
    }),
  );
}

function seedActiveProject() {
  window.localStorage.setItem(
    PROJECT_STORAGE_KEY,
    JSON.stringify([
      {
        id: 'project-a',
        name: 'project a',
        targets: [{ id: 'target-a-ip', type: 'ip', value: '10.0.0.1' }],
      },
    ]),
  );
  window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, 'project-a');
}

function renderRoute(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <C2ConnectionProvider>
        <AuthProvider>
          <RealtimeProvider>
            <App />
          </RealtimeProvider>
        </AuthProvider>
      </C2ConnectionProvider>
    </MemoryRouter>,
  );
}

describe('StubSectionPage', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 })),
    );
    window.localStorage.clear();
    window.sessionStorage.clear();
    seedAuthenticatedSession();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders the expanded primary navigation shell', () => {
    renderRoute('/home');

    const primaryNav = screen.getByLabelText('Primary');
    for (const label of ['Home', 'Projects', 'Recon', 'Beacons', 'Exploits', 'Payloads', 'Assets', 'Reports', 'Loot', 'Settings']) {
      expect(within(primaryNav).getByText(label)).toBeTruthy();
    }
    expect(within(primaryNav).queryByText('Inventory')).toBeNull();
    expect(within(primaryNav).queryByText('Reporting')).toBeNull();
  });

  it('uses Overview under Beacons and Infrastructure under Settings', () => {
    seedC2Connection();

    renderRoute('/beacons/sessions');

    expect(screen.getByRole('navigation', { name: 'Beacons sections' }).textContent).toContain('Overview');
    expect(screen.getByText('Session workspaces')).toBeTruthy();
    expect(screen.getByText('Active and recent shell, file browser, and Windows Registry Explorer interactions will appear here.')).toBeTruthy();
  });

  it('shows C2-required state on operational stubs when disconnected', () => {
    renderRoute('/exploits');

    expect(screen.getByRole('heading', { name: 'Xero C2 backend required' })).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'Exploits sections' }).textContent).toContain('Browser');
  });

  it('renders stub rows and opens a planned modal when connected and scoped', () => {
    seedC2Connection();
    seedActiveProject();

    renderRoute('/payloads');

    expect(screen.getByRole('heading', { name: 'Payloads' })).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'Payloads sections' }).textContent).toContain('Traffic Shaping');
    expect(screen.getByText('Generator workspace')).toBeTruthy();
    expect(within(screen.getByRole('complementary', { name: 'Payloads context' })).getByText('project a')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Open builder' }));

    expect(screen.getByRole('dialog', { name: 'Payload builder stub' })).toBeTruthy();
    expect(screen.getByText('Configure arguments, target scope, and output handling in a later feature.')).toBeTruthy();

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(screen.queryByRole('dialog', { name: 'Payload builder stub' })).toBeNull();
  });

  it('uses the side-panel modal variant for asset detail stubs', () => {
    seedC2Connection();
    seedActiveProject();

    renderRoute('/assets/hosts');

    fireEvent.click(screen.getByRole('button', { name: 'Open asset detail' }));

    expect(screen.getByRole('dialog', { name: 'Asset detail stub' })).toBeTruthy();
    expect(document.querySelector('.modal-shell--side')).toBeTruthy();
  });

  it('renders Infrastructure from the canonical route and legacy settings route', async () => {
    seedC2Connection();

    const canonical = renderRoute('/settings/infrastructure');
    expect(await screen.findByRole('heading', { name: 'C2 infrastructure' })).toBeTruthy();
    canonical.unmount();

    renderRoute('/settings/c2');
    expect(await screen.findByRole('heading', { name: 'C2 infrastructure' })).toBeTruthy();
    expect(screen.getByRole('navigation', { name: 'Settings sections' }).textContent).toContain('Infrastructure');
  });
});
