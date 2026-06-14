import { TerminalSquare } from 'lucide-react';
import { Link } from 'react-router-dom';

import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';
import { formatRelativeTime } from './beaconDisplay';

export function BeaconsSessionsPage() {
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const beacons = realtime.beacons.filter((beacon) => !beacon.removed_at);

  return (
    <AppShell description="Cross-beacon session overview" section="beacons" title="Beacons" wide>
      {!connection ? (
        <C2RequiredPanel />
      ) : (
        <section className="workspace-panel workspace-panel--flat" aria-label="Beacon sessions">
          {beacons.length === 0 ? (
            <div className="beacon-empty-state">
              <TerminalSquare aria-hidden="true" size={20} strokeWidth={2} />
              <div>
                <strong>No beacons registered.</strong>
                <span>Sessions appear when beacons connect and operators open interactive workspaces.</span>
              </div>
            </div>
          ) : (
            <table className="beacon-registry-table">
              <thead>
                <tr>
                  <th scope="col">Host</th>
                  <th scope="col">Status</th>
                  <th scope="col">Last heartbeat</th>
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {beacons.map((beacon) => (
                  <tr key={beacon.id}>
                    <td>{beacon.hostname}</td>
                    <td>{beacon.status}</td>
                    <td>{formatRelativeTime(beacon.last_seen)}</td>
                    <td>
                      <Link className="secondary-button" to={`/beacons/${beacon.id}/session`}>
                        Open session
                      </Link>
                      <Link className="secondary-button" to={`/beacons/${beacon.id}/files`}>
                        Files
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </AppShell>
  );
}
