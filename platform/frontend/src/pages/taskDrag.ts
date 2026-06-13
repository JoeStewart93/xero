import type { DragEvent } from 'react';

import type { Beacon } from '../api';

export const BEACON_DRAG_MIME = 'application/x-xero-beacon-id';

export function writeBeaconDragData(event: DragEvent<HTMLElement>, beacon: Beacon): void {
  event.dataTransfer.effectAllowed = 'copy';
  event.dataTransfer.setData(BEACON_DRAG_MIME, beacon.id);
  event.dataTransfer.setData('text/plain', beacon.id);
}
