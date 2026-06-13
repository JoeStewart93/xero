import type { DashboardActivityItem, DashboardSummary, Task } from './api';
import type { OperatorRealtimeEvent } from './operatorRealtime';

const MAX_DASHBOARD_ITEMS = 10;

function eventTime(event: OperatorRealtimeEvent): string {
  return event.occurred_at || new Date().toISOString();
}

function taskFromEvent(event: OperatorRealtimeEvent): Task | null {
  const task = event.data.task;
  if (!task || typeof task !== 'object') {
    return null;
  }
  return task as Task;
}

function taskResultTaskId(event: OperatorRealtimeEvent): string | null {
  const result = event.data.task_result;
  if (!result || typeof result !== 'object' || !('task_id' in result)) {
    return null;
  }
  return typeof result.task_id === 'string' ? result.task_id : null;
}

function beaconFromEvent(event: OperatorRealtimeEvent): { hostname?: string; id?: string; status?: string } | null {
  const beacon = event.data.beacon;
  if (!beacon || typeof beacon !== 'object') {
    return null;
  }
  return beacon as { hostname?: string; id?: string; status?: string };
}

function commandLabel(task: Task | null): string {
  const command = task?.args?.command;
  return typeof command === 'string' && command.trim() ? ` ${command.trim()}` : '';
}

export function activityFromRealtimeEvent(event: OperatorRealtimeEvent): DashboardActivityItem | null {
  const beacon = beaconFromEvent(event);
  if (beacon?.id && event.type.startsWith('beacon.')) {
    return {
      beacon_id: beacon.id,
      detail: event.type,
      id: `rt-${event.id}`,
      label: `${beacon.hostname || 'Beacon'} ${beacon.status || 'updated'}`,
      occurred_at: eventTime(event),
      status: beacon.status || null,
      task_id: null,
      type: event.type,
    };
  }

  const task = taskFromEvent(event);
  if (task && event.type.startsWith('task.')) {
    return {
      beacon_id: task.beacon_id,
      detail: event.type,
      id: `rt-${event.id}`,
      label: `Task${commandLabel(task)} ${task.status}`,
      occurred_at: eventTime(event),
      status: task.status,
      task_id: task.id,
      type: event.type,
    };
  }

  const resultTaskId = taskResultTaskId(event);
  if (resultTaskId && event.type.startsWith('task.result.')) {
    return {
      beacon_id: event.scope.beacon_id || null,
      detail: event.type,
      id: `rt-${event.id}`,
      label: 'Task result received',
      occurred_at: eventTime(event),
      status: event.type.replace('task.result.', ''),
      task_id: resultTaskId,
      type: event.type,
    };
  }

  if (event.type.startsWith('system.realtime.')) {
    return {
      beacon_id: null,
      detail: event.type,
      id: `rt-${event.id}`,
      label: event.type === 'system.realtime.recovered' ? 'Realtime recovered' : 'Realtime degraded',
      occurred_at: eventTime(event),
      status: event.type.endsWith('recovered') ? 'connected' : 'degraded',
      task_id: null,
      type: event.type,
    };
  }

  return null;
}

function upsertTask(tasks: Task[], nextTask: Task): Task[] {
  const next = [nextTask, ...tasks.filter((task) => task.id !== nextTask.id)];
  next.sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at));
  return next.slice(0, MAX_DASHBOARD_ITEMS);
}

function prependActivity(items: DashboardActivityItem[], item: DashboardActivityItem): DashboardActivityItem[] {
  if (items.some((current) => current.id === item.id)) {
    return items;
  }
  return [item, ...items].slice(0, MAX_DASHBOARD_ITEMS);
}

function applyBeaconCounts(summary: DashboardSummary, event: OperatorRealtimeEvent): DashboardSummary['beacons'] {
  const beacon = beaconFromEvent(event);
  if (!beacon?.id) {
    return summary.beacons;
  }

  const status = (beacon.status || '').toLowerCase();
  if (event.type === 'beacon.registered') {
    return {
      offline: summary.beacons.offline + (status === 'offline' ? 1 : 0),
      online: summary.beacons.online + (status === 'online' ? 1 : 0),
      total: summary.beacons.total + 1,
    };
  }

  if (event.type === 'beacon.status.changed') {
    if (status === 'online') {
      return {
        offline: Math.max(0, summary.beacons.offline - 1),
        online: summary.beacons.online + 1,
        total: summary.beacons.total,
      };
    }
    if (status === 'offline') {
      return {
        offline: summary.beacons.offline + 1,
        online: Math.max(0, summary.beacons.online - 1),
        total: summary.beacons.total,
      };
    }
  }

  return {
    ...summary.beacons,
  };
}

export function applyDashboardRealtimeEvent(summary: DashboardSummary, event: OperatorRealtimeEvent): DashboardSummary {
  const activity = activityFromRealtimeEvent(event);
  const task = taskFromEvent(event);

  return {
    ...summary,
    beacons: applyBeaconCounts(summary, event),
    recent_activity: activity ? prependActivity(summary.recent_activity, activity) : summary.recent_activity,
    recent_tasks: task ? upsertTask(summary.recent_tasks, task) : summary.recent_tasks,
  };
}
