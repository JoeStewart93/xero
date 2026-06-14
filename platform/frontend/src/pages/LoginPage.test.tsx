import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import { AuthProvider } from '../auth';
import { AUTH_STORAGE_KEY } from '../authStorage';
import { C2ConnectionProvider } from '../c2Connection';
import { RealtimeProvider } from '../realtime';

function renderApp(path = '/login') {
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

function mockFetch(status = 200) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/ready')) {
      return new Response(
        JSON.stringify({
          checks: {
            postgres: { status: 'healthy' },
            redis: { status: 'healthy' },
          },
          service: 'xero-bff',
          status: 'ready',
        }),
        { status: 200 },
      );
    }
    if (url.endsWith('/auth/login')) {
      if (status !== 200) {
        return new Response(JSON.stringify({ detail: 'Invalid username or password' }), { status });
      }
      return new Response(
        JSON.stringify({
          access_token: 'test-token',
          token_type: 'bearer',
          expires_at: new Date(Date.now() + 60_000).toISOString(),
          operator: {
            id: '00000000-0000-0000-0000-000000000001',
            username: 'operator',
            role: 'operator',
            is_enabled: true,
            created_at: new Date().toISOString(),
          },
        }),
        { status: 200 },
      );
    }

    return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 });
  });
}

function mockReadyUnauthorized() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/api/v1/ready')) {
      return new Response(JSON.stringify({ detail: 'Token expired' }), { status: 401 });
    }
    return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 });
  });
}

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

describe('LoginPage', () => {
  it('renders the operator login form and health link', () => {
    renderApp();

    expect(screen.getByRole('region', { name: 'Xero operator login' })).toBeTruthy();
    expect(screen.queryByRole('heading', { name: 'Xero' })).toBeNull();
    expect(screen.getByLabelText('Username')).toBeTruthy();
    expect(screen.getByLabelText('Password')).toBeTruthy();
    expect(screen.queryByRole('link', { name: 'System health' })).toBeNull();
    expect(screen.queryByText('C2 offensive security platform.')).toBeNull();
    expect(screen.queryByText('Access')).toBeNull();
    expect(screen.queryByText('Observe')).toBeNull();
    expect(screen.queryByText('Local-first operator workspace')).toBeNull();
  });

  it('stores the token and redirects to home after valid login', async () => {
    vi.stubGlobal('fetch', mockFetch());
    renderApp();

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'operator' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'operator_password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }));

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Home' })).toBeTruthy();
    });
    expect(window.sessionStorage.getItem(AUTH_STORAGE_KEY)).toContain('test-token');
  });

  it('shows an error and does not store a token for invalid credentials', async () => {
    vi.stubGlobal('fetch', mockFetch(401));
    renderApp();

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'operator' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toContain('Invalid username or password.');
    });
    expect(window.sessionStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });

  it('redirects unauthenticated project access to login', () => {
    renderApp('/projects');

    expect(screen.getByRole('region', { name: 'Xero operator login' })).toBeTruthy();
    expect(screen.getByLabelText('Username')).toBeTruthy();
  });

  it('shows the authenticated shell navigation for a stored session', async () => {
    seedAuthenticatedSession();
    vi.stubGlobal('fetch', mockFetch());

    renderApp('/home');

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Home' })).toBeTruthy();
    });

    const primaryNav = screen.getByLabelText('Primary');
    for (const label of ['Home', 'Projects', 'Recon', 'Beacons', 'Exploits', 'Payloads', 'Assets', 'Reports', 'Loot', 'Settings']) {
      expect(within(primaryNav).getByText(label)).toBeTruthy();
    }
    expect(screen.getByLabelText('System').textContent).toContain('Health');
  });

  it('clears auth state and redirects to login when an authenticated API request returns 401', async () => {
    seedAuthenticatedSession();
    vi.stubGlobal('fetch', mockReadyUnauthorized());

    renderApp('/health');

    await waitFor(() => {
      expect(screen.getByRole('region', { name: 'Xero operator login' })).toBeTruthy();
    });
    expect(window.sessionStorage.getItem(AUTH_STORAGE_KEY)).toBeNull();
  });
});
