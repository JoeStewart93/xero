import { FormEvent, useState } from 'react';
import { Cable, Settings } from 'lucide-react';

import { DEFAULT_C2_BASE_URL } from '../api';
import { AppShell } from '../components/AppShell';
import { useC2Connection } from '../useC2Connection';

export function SettingsPage() {
  const { checkConnection, connection, disconnect, error, isChecking } = useC2Connection();
  const [baseUrl, setBaseUrl] = useState(connection?.baseUrl ?? DEFAULT_C2_BASE_URL);
  const [password, setPassword] = useState('');

  async function handleConnect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await checkConnection(baseUrl, password);
      setPassword('');
    } catch {
      // The connection context surfaces the error for the form.
    }
  }

  return (
    <AppShell description="Workspace preferences" section="settings" title="Settings">
      <div className="settings-grid">
        <section className="workspace-panel settings-panel" aria-label="Xero C2 backend connection">
          <div className="panel-header">
            <div>
              <h2>Xero C2 backend</h2>
              <p className="muted-text">Authenticate to a local or remote C2 Core before running lifecycle workflows.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <Cable size={18} strokeWidth={2} />
            </div>
          </div>

          <form className="workspace-form" onSubmit={handleConnect}>
            <label>
              Backend URL
              <input
                name="baseUrl"
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="http://localhost:8001"
                value={baseUrl}
              />
            </label>
            <label>
              C2 password
              <input
                autoComplete="current-password"
                name="c2Password"
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Configured on the C2 backend"
                type="password"
                value={password}
              />
            </label>
            <div className="button-row">
              <button className="primary-button" disabled={isChecking || Boolean(connection)} type="submit">
                {isChecking ? 'Checking...' : 'Connect'}
              </button>
              <button className={connection ? 'danger-button' : 'secondary-button'} disabled={!connection || isChecking} onClick={disconnect} type="button">
                Disconnect
              </button>
            </div>
          </form>

          {error && (
            <p className="alert-message alert-message--inline" role="alert">
              {error}
            </p>
          )}

          <div className="dashboard-list connection-list">
            <div className="dashboard-row">
              <span>Status</span>
              <strong>{connection ? 'Connected' : 'Disconnected'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Service</span>
              <strong>{connection?.service ?? '-'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Role</span>
              <strong>{connection?.serviceRole ?? '-'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Endpoint</span>
              <strong>{connection?.baseUrl ?? '-'}</strong>
            </div>
            <div className="dashboard-row">
              <span>Token expires</span>
              <strong>{connection ? new Date(connection.expiresAt).toLocaleString() : '-'}</strong>
            </div>
          </div>
        </section>

        <section className="workspace-panel settings-panel" aria-label="Workspace settings">
          <div className="panel-header">
            <div>
              <h2>Workspace settings</h2>
              <p className="muted-text">Local administrative controls.</p>
            </div>
            <div className="panel-icon" aria-hidden="true">
              <Settings size={18} strokeWidth={2} />
            </div>
          </div>

          <div className="dashboard-list">
            <div className="dashboard-row">
              <span>Account status</span>
              <strong>Enabled</strong>
            </div>
            <div className="dashboard-row">
              <span>Access mode</span>
              <strong>Local</strong>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
