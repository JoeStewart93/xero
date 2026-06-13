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

function renderProjectsPage(initialEntries = ['/projects']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
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

function seedProjects() {
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
}

describe('ProjectsPage', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    seedAuthenticatedSession();
  });

  it('creates projects from the top-bar wizard and manages targets in the project modal', () => {
    renderProjectsPage();

    expect(screen.getByLabelText('Active project scope').textContent).toContain('Global');
    expect(screen.queryByLabelText('Project name')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Create resource' }));
    fireEvent.click(screen.getByRole('menuitem', { name: /Project/ }));

    let wizard = screen.getByRole('dialog', { name: 'Create project wizard' });
    fireEvent.change(within(wizard).getByLabelText('Project name'), { target: { value: 'acme-external' } });
    fireEvent.click(within(wizard).getByRole('button', { name: 'Next' }));

    wizard = screen.getByRole('dialog', { name: 'Create project wizard' });
    fireEvent.change(within(wizard).getByLabelText('Target'), { target: { value: '10.0.0.999' } });
    fireEvent.click(within(wizard).getByRole('button', { name: 'Add' }));
    expect(within(wizard).getByRole('alert').textContent).toContain('Each octet must be between 0 and 255');

    fireEvent.change(within(wizard).getByLabelText('Target'), { target: { value: 'Example.COM' } });
    fireEvent.click(within(wizard).getByRole('button', { name: 'Add' }));
    expect(within(wizard).getByText('example.com')).toBeTruthy();

    fireEvent.change(within(wizard).getByLabelText('Target'), { target: { value: '10.0.0.1' } });
    fireEvent.click(within(wizard).getByRole('button', { name: 'Add' }));
    expect(within(wizard).getByText('10.0.0.1')).toBeTruthy();

    fireEvent.click(within(wizard).getByRole('button', { name: 'Next' }));
    wizard = screen.getByRole('dialog', { name: 'Create project wizard' });
    fireEvent.click(within(wizard).getByRole('button', { name: 'Create project' }));

    const projectRoster = screen.getByRole('region', { name: 'Project roster' });
    expect(within(projectRoster).getByRole('button', { name: /acme-external/i })).toBeTruthy();

    const manageDialog = screen.getByRole('dialog', { name: 'Manage project acme-external' });
    fireEvent.change(within(manageDialog).getByLabelText('Add target'), { target: { value: 'example.com' } });
    fireEvent.click(within(manageDialog).getByRole('button', { name: 'Add' }));
    expect(within(manageDialog).getByRole('alert').textContent).toContain('already in this project');

    fireEvent.click(within(manageDialog).getByRole('button', { name: 'Activate' }));
    expect(screen.getByLabelText('Active project scope').textContent).toContain('acme-external');

    fireEvent.click(within(manageDialog).getByRole('button', { name: 'Deactivate' }));
    expect(screen.getByLabelText('Active project scope').textContent).toContain('Global');
  });

  it('updates active scope from the top-bar selector and opens project attributes from roster rows', () => {
    seedProjects();
    renderProjectsPage();

    const scopeSelector = screen.getByLabelText('Active project scope') as HTMLButtonElement;
    expect(scopeSelector.textContent).toContain('project a');

    fireEvent.click(scopeSelector);
    fireEvent.click(screen.getByRole('option', { name: /project b/i }));

    expect(scopeSelector.textContent).toContain('project b');
    const activeScope = screen.getByRole('region', { name: 'Active scope' });
    expect(within(activeScope).getByText('project b')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /project b/i }));
    const manageDialog = screen.getByRole('dialog', { name: 'Manage project project b' });
    expect(within(manageDialog).getByText('Active scope')).toBeTruthy();
    expect(within(manageDialog).getByText('b.example.com')).toBeTruthy();

    fireEvent.click(scopeSelector);
    fireEvent.click(screen.getByRole('option', { name: /Global/i }));
    expect(scopeSelector.textContent).toContain('Global');
    expect(within(manageDialog).getByText('Inactive')).toBeTruthy();
  });

  it('deletes a project only after confirmation and falls back to Global when deleting active scope', () => {
    seedProjects();
    renderProjectsPage();

    fireEvent.click(screen.getByRole('button', { name: /project a/i }));
    const manageDialog = screen.getByRole('dialog', { name: 'Manage project project a' });
    fireEvent.click(within(manageDialog).getByRole('button', { name: 'Delete project' }));

    expect(screen.getByRole('dialog', { name: 'Delete project confirmation' })).toBeTruthy();
    expect(screen.getByText('Delete project a?')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByRole('dialog', { name: 'Delete project confirmation' })).toBeNull();
    expect(screen.getAllByText('project a').length).toBeGreaterThan(0);

    fireEvent.click(within(manageDialog).getByRole('button', { name: 'Delete project' }));
    fireEvent.click(within(screen.getByRole('dialog', { name: 'Delete project confirmation' })).getByRole('button', { name: 'Delete project' }));

    const projectRoster = screen.getByRole('region', { name: 'Project roster' });
    expect(within(projectRoster).queryByText('project a')).toBeNull();
    expect(within(projectRoster).getByText('project b')).toBeTruthy();
    expect(screen.getByLabelText('Active project scope').textContent).toContain('Global');
    expect(window.localStorage.getItem(ACTIVE_PROJECT_STORAGE_KEY)).toBeNull();
  });
});
