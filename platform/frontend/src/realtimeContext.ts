import { createContext } from 'react';

import type { Beacon } from './api';
import type { OperatorRealtimeEvent, RealtimeStatus } from './operatorRealtime';

export interface RealtimeContextValue {
  activeBeaconCount: number;
  beaconCount: number;
  beacons: Beacon[];
  error: string;
  latestEvent: OperatorRealtimeEvent | null;
  offlineBeaconCount: number;
  status: RealtimeStatus;
}

export const RealtimeContext = createContext<RealtimeContextValue | undefined>(undefined);
