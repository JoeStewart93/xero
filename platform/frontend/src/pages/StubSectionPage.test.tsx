import { render, screen, within } from '@testing-library/react';
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
    for (const label of ['Home', 'Projects', 'Recon', 'Beacons', 'Modules', 'Assets', 'Settings']) {
      expect(within(primaryNav).getByText(label)).toBeTruthy();
    }
  });

  it('uses Roster and Sessions under Beacons', async () => {
    seedC2Connection();

    renderRoute('/beacons/sessions');

    expect(screen.getByRole('navigation', { name: 'Beacons sections' }).textContent).toContain('Roster');
    expect(screen.getByRole('navigation', { name: 'Beacons sections' }).textContent).toContain('Sessions');
    expect(await screen.findByText('No beacons registered.')).toBeTruthy();
  });

  it('shows C2-required state on operational planned sections when disconnected', () => {
    renderRoute('/exploits');

    expect(screen.getByRole('heading', { name: 'Xero C2 backend required' })).toBeTruthy();
    expect(screen.queryByRole('navigation', { name: 'Exploits sections' })).toBeNull();
  });

  it('renders planned empty states instead of stub tables when connected', () => {
    seedC2Connection();
    seedActiveProject();

    renderRoute('/exploits');

    expect(screen.getByText('This section is planned. No operations can be dispatched from this surface yet.')).toBeTruthy();
  });

  it('keeps traffic profiles out of Settings and redirects legacy profile URLs into Traffic Patterns', async () => {
    seedC2Connection();
    seedActiveProject();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/traffic-profiles')) {
          return new Response(JSON.stringify({ items: [] }), { status: 200 });
        }
        return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 });
      }),
    );

    renderRoute('/settings');
    expect(screen.getByRole('navigation', { name: 'Settings sections' })).toBeTruthy();
    expect(screen.getByRole('link', { name: 'Connection' })).toBeTruthy();

    renderRoute('/settings/profiles');
    expect(await screen.findByRole('heading', { name: 'Traffic Patterns' })).toBeTruthy();
    expect(await screen.findByRole('dialog', { name: 'Traffic profiles' })).toBeTruthy();
  });

  it('redirects removed asset facet routes back to inventory', async () => {
    seedC2Connection();
    seedActiveProject();

    renderRoute('/assets/hosts');
    expect(await screen.findByLabelText('Automatic asset groups')).toBeTruthy();
  });
});
