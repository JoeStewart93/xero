import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';

import { App } from '../App';
import { AuthProvider } from '../auth';
import { AUTH_STORAGE_KEY } from '../authStorage';
import { C2ConnectionProvider } from '../c2Connection';
import { RealtimeProvider } from '../realtime';
import { C2_CONNECTION_STORAGE_KEY } from '../c2ConnectionStorage';
import { ACTIVE_PROJECT_STORAGE_KEY, PROJECT_STORAGE_KEY } from '../projectScopeStorage';

function renderProjectsPage() {
  return render(
    <MemoryRouter initialEntries={['/projects']}>
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

describe('ProjectsPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    seedAuthenticatedSession();
  });

  it('auto-detects domains and IPs, rejects invalid IPs, and activates one project scope', () => {
    renderProjectsPage();

    fireEvent.change(screen.getByLabelText('Project name'), { target: { value: 'acme-external' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create project' }));

    const projectRoster = screen.getByRole('region', { name: 'Project roster' });
    expect(within(projectRoster).getByRole('button', { name: /acme-external/i })).toBeTruthy();
    expect(screen.queryByLabelText('Type')).toBeNull();

    fireEvent.change(screen.getByLabelText('Target'), { target: { value: '10.0.0.999' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add to acme-external' }));

    expect(screen.getByRole('alert').textContent).toContain('Each octet must be between 0 and 255');
    expect(screen.queryByText('10.0.0.999')).toBeNull();

    fireEvent.change(screen.getByLabelText('Target'), { target: { value: 'Example.COM' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add to acme-external' }));
    expect(screen.getByText('example.com')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Target'), { target: { value: '10.0.0.1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add to acme-external' }));
    expect(screen.getByText('10.0.0.1')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Target'), { target: { value: 'example.com' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add to acme-external' }));
    expect(screen.getByRole('alert').textContent).toContain('already in this project');

    fireEvent.click(screen.getByRole('button', { name: 'Activate' }));

    const activeScope = screen.getByRole('complementary', { name: 'Project actions' });
    expect(within(activeScope).getByText('acme-external')).toBeTruthy();
    const selectedProjectDetail = screen.getByRole('region', { name: 'Selected project detail' });
    expect(within(selectedProjectDetail).getByText('Active scope')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Deactivate' }));

    expect(within(selectedProjectDetail).getByText('Inactive')).toBeTruthy();
    expect(within(selectedProjectDetail).getByRole('button', { name: 'Activate' })).toBeTruthy();
  });

  it('updates the active project scope from the top-bar selector', () => {
    window.localStorage.setItem(
      PROJECT_STORAGE_KEY,
      JSON.stringify([
        {
          id: 'project-a',
          name: 'project a',
          targets: [
            { id: 'target-a-domain', type: 'domain', value: 'a.example.com' },
            { id: 'target-a-ip', type: 'ip', value: '10.0.0.1' },
          ],
        },
        {
          id: 'project-b',
          name: 'project b',
          targets: [{ id: 'target-b-domain', type: 'domain', value: 'b.example.com' }],
        },
      ]),
    );
    window.localStorage.setItem(ACTIVE_PROJECT_STORAGE_KEY, 'project-a');

    renderProjectsPage();

    const scopeSelector = screen.getByLabelText('Active project scope') as HTMLButtonElement;
    expect(scopeSelector.textContent).toContain('project a');

    fireEvent.click(scopeSelector);
    fireEvent.click(screen.getByRole('option', { name: /project b/i }));

    expect(scopeSelector.textContent).toContain('project b');
    const activeScope = screen.getByRole('complementary', { name: 'Project actions' });
    expect(within(activeScope).getByText('project b')).toBeTruthy();
    const selectedProjectDetail = screen.getByRole('region', { name: 'Selected project detail' });
    expect(within(selectedProjectDetail).getByRole('heading', { name: 'project b' })).toBeTruthy();
    expect(within(selectedProjectDetail).getByText('Active scope')).toBeTruthy();
  });
});
