import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { App } from '../App';
import { AuthProvider } from '../auth';
import { AUTH_STORAGE_KEY } from '../authStorage';
import { C2ConnectionProvider } from '../c2Connection';
import { RealtimeProvider } from '../realtime';
import { C2_CONNECTION_STORAGE_KEY } from '../c2ConnectionStorage';

function renderSettingsPage() {
  return render(
    <MemoryRouter initialEntries={['/settings']}>
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

describe('SettingsPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    seedAuthenticatedSession();
  });

  it('enables connect and grays out disconnect while disconnected', () => {
    renderSettingsPage();

    const connect = screen.getByRole('button', { name: 'Connect' }) as HTMLButtonElement;
    const disconnect = screen.getByRole('button', { name: 'Disconnect' }) as HTMLButtonElement;

    expect(connect.disabled).toBe(false);
    expect(connect.className).toContain('primary-button');
    expect(disconnect.disabled).toBe(true);
    expect(disconnect.className).toContain('secondary-button');
    expect(screen.getByText('Disconnected')).toBeTruthy();
  });

  it('grays out connect and enables red disconnect while connected', () => {
    seedC2Connection();
    renderSettingsPage();

    const connect = screen.getByRole('button', { name: 'Connect' }) as HTMLButtonElement;
    const disconnect = screen.getByRole('button', { name: 'Disconnect' }) as HTMLButtonElement;

    expect(connect.disabled).toBe(true);
    expect(disconnect.disabled).toBe(false);
    expect(disconnect.className).toContain('danger-button');
    expect(screen.getByText('Connected')).toBeTruthy();

    fireEvent.click(disconnect);

    const nextConnect = screen.getByRole('button', { name: 'Connect' }) as HTMLButtonElement;
    const nextDisconnect = screen.getByRole('button', { name: 'Disconnect' }) as HTMLButtonElement;
    expect(nextConnect.disabled).toBe(false);
    expect(nextDisconnect.disabled).toBe(true);
    expect(nextDisconnect.className).toContain('secondary-button');
    expect(screen.getByText('Disconnected')).toBeTruthy();
  });
});
