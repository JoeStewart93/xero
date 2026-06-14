import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ShieldCheck } from 'lucide-react';
import { Link, Navigate, NavLink, useParams, useSearchParams } from 'react-router-dom';

import {
  assignBeaconTrafficProfile,
  clearBeaconTrafficProfile,
  getTrafficProfiles,
  killBeacon,
} from '../api';
import type { Beacon, TrafficProfile } from '../api';
import { AppShell } from '../components/AppShell';
import { C2RequiredPanel } from '../components/C2RequiredPanel';
import { decodeLaunchArgs } from '../modules/moduleCatalog';
import { useC2Connection } from '../useC2Connection';
import { useRealtime } from '../useRealtime';
import {
  BeaconControlsPanel,
  hostOperations,
  KillBeaconModal,
  ShellSessionPanel,
  FileBrowserPanel,
} from './BeaconsPage';
import { formatRelativeTime } from './beaconDisplay';
import { RegistrySessionPanel } from './RegistrySessionPanel';
import { TaskExecutionPanel } from './TaskExecutionPanel';

const routableOperations = new Set(['commands', 'controls', 'session', 'files', 'registry']);

function activeClass(baseClass: string, isActive: boolean) {
  return isActive ? `${baseClass} is-active` : baseClass;
}

export function BeaconWorkspacePage() {
  const { beaconId = '', operation = 'commands' } = useParams();
  const [searchParams] = useSearchParams();
  const { connection } = useC2Connection();
  const realtime = useRealtime();
  const [profileOverrides, setProfileOverrides] = useState<Record<string, Beacon>>({});
  const [trafficProfiles, setTrafficProfiles] = useState<TrafficProfile[]>([]);
  const [profileError, setProfileError] = useState('');
  const [profileMessage, setProfileMessage] = useState('');
  const [isLoadingProfiles, setIsLoadingProfiles] = useState(false);
  const [assigningProfile, setAssigningProfile] = useState(false);
  const [killTarget, setKillTarget] = useState<Beacon | null>(null);
  const [killError, setKillError] = useState('');
  const [isKillingBeacon, setIsKillingBeacon] = useState(false);
  const [removedBeaconIds, setRemovedBeaconIds] = useState<Set<string>>(() => new Set());

  const beacon = useMemo(() => {
    const found = realtime.beacons.find((item) => item.id === beaconId && !item.removed_at && !removedBeaconIds.has(item.id));
    return found ? profileOverrides[found.id] ?? found : null;
  }, [beaconId, profileOverrides, realtime.beacons, removedBeaconIds]);

  const routeModuleId = searchParams.get('module') ?? '';
  const routeModuleArgs = useMemo(() => decodeLaunchArgs(searchParams.get('args')), [searchParams]);
  const routeTaskId = searchParams.get('task_id') ?? '';

  const activeOperationKey = routableOperations.has(operation) ? operation : 'commands';
  const activeOperation = hostOperations.find((item) => item.key === activeOperationKey) ?? hostOperations[0];
  const ActiveIcon = activeOperation.icon;

  const loadTrafficProfiles = useCallback(async () => {
    if (!connection) {
      setTrafficProfiles([]);
      return;
    }
    setIsLoadingProfiles(true);
    try {
      const response = await getTrafficProfiles(connection.baseUrl, connection.accessToken);
      setTrafficProfiles(response.items);
      setProfileError('');
    } catch (caught) {
      setProfileError(caught instanceof Error ? caught.message : 'Unable to load traffic profiles.');
    } finally {
      setIsLoadingProfiles(false);
    }
  }, [connection]);

  useEffect(() => {
    if (activeOperationKey === 'controls') {
      void loadTrafficProfiles();
    }
  }, [activeOperationKey, loadTrafficProfiles]);

  async function handleConfirmKillBeacon(): Promise<void> {
    if (!connection || !killTarget) {
      return;
    }
    setIsKillingBeacon(true);
    setKillError('');
    try {
      const response = await killBeacon(connection.baseUrl, connection.accessToken, killTarget.id);
      setRemovedBeaconIds((current) => new Set(current).add(response.beacon.id));
      setKillTarget(null);
    } catch (caught) {
      setKillError(caught instanceof Error ? caught.message : 'Unable to kill beacon.');
    } finally {
      setIsKillingBeacon(false);
    }
  }

  async function handleAssignProfile(targetBeaconId: string, profileId: string): Promise<void> {
    if (!connection) {
      return;
    }
    setAssigningProfile(true);
    setProfileError('');
    setProfileMessage('');
    try {
      const updated = profileId
        ? await assignBeaconTrafficProfile(connection.baseUrl, connection.accessToken, targetBeaconId, profileId)
        : await clearBeaconTrafficProfile(connection.baseUrl, connection.accessToken, targetBeaconId);
      setProfileOverrides((current) => ({ ...current, [updated.id]: updated }));
      setProfileMessage(profileId ? `Assigned ${updated.profile_name ?? 'traffic profile'}.` : 'Cleared traffic profile assignment.');
    } catch (caught) {
      setProfileError(caught instanceof Error ? caught.message : 'Unable to update beacon profile.');
    } finally {
      setAssigningProfile(false);
    }
  }

  if (!connection) {
    return (
      <AppShell description="Beacon workspace" section="beacons" title="Beacons" wide>
        <C2RequiredPanel />
      </AppShell>
    );
  }

  if (!beaconId) {
    return <Navigate to="/beacons" replace />;
  }

  if (!routableOperations.has(operation)) {
    return <Navigate to={`/beacons/${beaconId}/commands`} replace />;
  }

  if (!beacon) {
    return (
      <AppShell description="Beacon workspace" section="beacons" title="Beacons" wide>
        <section className="workspace-panel workspace-panel--flat planned-section-empty">
          <h2>Beacon not found</h2>
          <p className="muted-text">This beacon is not available in the current roster.</p>
          <Link className="secondary-button" to="/beacons">
            <ArrowLeft aria-hidden="true" size={14} strokeWidth={2} />
            <span>Back to roster</span>
          </Link>
        </section>
      </AppShell>
    );
  }

  return (
    <AppShell description={`${beacon.hostname} workspace`} section="beacons" title="Beacons" wide>
      <section aria-label={`Host operations for ${beacon.hostname}`} className="beacon-workspace-page">
        <header className="beacon-workspace-header">
          <Link aria-label="Back to beacon roster" className="beacon-workspace-back" to="/beacons">
            <ArrowLeft aria-hidden="true" size={15} strokeWidth={2.2} />
            <span>Roster</span>
          </Link>
          <div>
            <h2>{beacon.hostname}</h2>
            <p className="muted-text">
              {beacon.os} / {beacon.internal_ip} / last heartbeat {formatRelativeTime(beacon.last_seen)}
            </p>
          </div>
        </header>

        <div className="beacon-workspace-body">
          <nav aria-label="Host operations" className="beacon-operation-rail">
            {hostOperations
              .filter((item) => routableOperations.has(item.key))
              .map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    className={({ isActive }) => activeClass('beacon-operation-option', isActive)}
                    end={false}
                    key={item.key}
                    to={`/beacons/${beaconId}/${item.key}`}
                  >
                    <Icon aria-hidden="true" size={16} strokeWidth={2.1} />
                    <span>
                      <strong>{item.label}</strong>
                      <small>{item.status}</small>
                    </span>
                  </NavLink>
                );
              })}
          </nav>

          <div className="beacon-operation-detail" data-testid="beacon-operation-detail">
            <div className="beacon-operation-detail-head">
              <div className="panel-icon" aria-hidden="true">
                <ActiveIcon size={18} strokeWidth={2} />
              </div>
              <div>
                <h3>{activeOperation.label}</h3>
                <p>{activeOperation.description}</p>
              </div>
            </div>

            {activeOperationKey === 'commands' ? (
              <TaskExecutionPanel
                beacons={[beacon]}
                connection={connection}
                initialArgs={routeModuleArgs}
                initialBeaconId={beacon.id}
                initialModuleId={routeModuleId || undefined}
                initialTaskId={routeTaskId || undefined}
                latestEvent={realtime.latestEvent}
                lockTargetBeacon
                realtimeStatus={realtime.status}
                title="Command queue"
              />
            ) : activeOperationKey === 'controls' ? (
              <BeaconControlsPanel
                assigningProfile={assigningProfile}
                beacon={beacon}
                isLoadingProfiles={isLoadingProfiles}
                onAssignProfile={(id, profileId) => void handleAssignProfile(id, profileId)}
                onLoadProfiles={() => void loadTrafficProfiles()}
                onRequestKill={(target) => {
                  setKillError('');
                  setKillTarget(target);
                }}
                profileError={profileError}
                profileMessage={profileMessage}
                trafficProfiles={trafficProfiles}
              />
            ) : activeOperationKey === 'session' ? (
              <ShellSessionPanel beacon={beacon} connection={connection} />
            ) : activeOperationKey === 'files' ? (
              <FileBrowserPanel beacon={beacon} connection={connection} />
            ) : activeOperationKey === 'registry' ? (
              <RegistrySessionPanel beacon={beacon} connection={connection} />
            ) : (
              <div className="beacon-operation-locked">
                <ShieldCheck aria-hidden="true" size={17} strokeWidth={2} />
                <div>
                  <strong>Planned.</strong>
                  <span>This operation is not available yet.</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {killTarget ? (
        <KillBeaconModal
          beacon={killTarget}
          error={killError}
          isKilling={isKillingBeacon}
          onCancel={() => {
            if (!isKillingBeacon) {
              setKillTarget(null);
              setKillError('');
            }
          }}
          onConfirm={() => void handleConfirmKillBeacon()}
        />
      ) : null}
    </AppShell>
  );
}

export function BeaconWorkspaceRedirectPage() {
  const { beaconId = '' } = useParams();
  return <Navigate to={`/beacons/${beaconId}/commands`} replace />;
}
