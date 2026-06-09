import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Beacon, getC2Beacons } from './api';
import { OperatorRealtimeClient, OperatorRealtimeEvent, RealtimeStatus } from './operatorRealtime';
import { RealtimeContext } from './realtimeContext';
import { useAuth } from './useAuth';
import { useC2Connection } from './useC2Connection';

function beaconFromEvent(event: OperatorRealtimeEvent): Beacon | null {
  const beacon = event.data.beacon;
  if (!beacon || typeof beacon !== 'object') {
    return null;
  }
  return beacon as Beacon;
}

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const { connection } = useC2Connection();
  const [beacons, setBeacons] = useState<Beacon[]>([]);
  const [error, setError] = useState('');
  const [latestEvent, setLatestEvent] = useState<OperatorRealtimeEvent | null>(null);
  const [status, setStatus] = useState<RealtimeStatus>('disconnected');
  const seenEventIds = useRef(new Set<string>());
  const isRealtimeEnabled = Boolean(session && connection);

  const reconcileBeacons = useCallback(async () => {
    if (!connection) {
      return;
    }
    try {
      const response = await getC2Beacons(connection.baseUrl, connection.accessToken);
      setBeacons(response.items);
      setError('');
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Unable to reconcile realtime state.';
      setError(message);
    }
  }, [connection]);

  useEffect(() => {
    if (!session || !connection) {
      seenEventIds.current.clear();
      return undefined;
    }
    if (typeof WebSocket === 'undefined') {
      return undefined;
    }

    const client = new OperatorRealtimeClient({
      accessToken: connection.accessToken,
      baseUrl: connection.baseUrl,
      onEvent: (event) => {
        if (seenEventIds.current.has(event.id)) {
          return;
        }
        seenEventIds.current.add(event.id);
        setLatestEvent(event);
        const beacon = beaconFromEvent(event);
        if (beacon) {
          setBeacons((current) => {
            const next = current.filter((item) => item.id !== beacon.id);
            return [beacon, ...next];
          });
        }
      },
      onReconnect: reconcileBeacons,
      onStatusChange: (nextStatus, nextError = '') => {
        setStatus(nextStatus);
        setError(nextError);
      },
    });
    client.start();
    return () => client.stop();
  }, [connection, reconcileBeacons, session]);

  const value = useMemo(
    () => {
      const activeBeaconCount = beacons.filter((beacon) => beacon.status.toLowerCase() === 'online').length;
      const offlineBeaconCount = beacons.filter((beacon) => beacon.status.toLowerCase() === 'offline').length;

      if (!isRealtimeEnabled) {
        return {
          activeBeaconCount: 0,
          beaconCount: 0,
          beacons: [],
          error: '',
          latestEvent: null,
          offlineBeaconCount: 0,
          status: 'disconnected' as RealtimeStatus,
        };
      }

      return {
        activeBeaconCount,
        beaconCount: beacons.length,
        beacons,
        error,
        latestEvent,
        offlineBeaconCount,
        status,
      };
    },
    [beacons, error, isRealtimeEnabled, latestEvent, status],
  );

  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}
