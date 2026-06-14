import { useCallback, useEffect, useRef, useState } from 'react';
import { Bell, ExternalLink, X } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';

import type { Task } from '../api';
import { taskFromRealtimeEvent, taskResultFromRealtimeEvent } from '../operatorRealtime';
import { useRealtime } from '../useRealtime';

interface TaskCompletionToast {
  beaconId: string;
  beaconLabel: string;
  eventId: string;
  module: string;
  taskId: string;
}

function taskBeaconLabel(task: Task | undefined, beaconId: string, realtimeBeacons: ReturnType<typeof useRealtime>['beacons']): string {
  const beacon = realtimeBeacons.find((item) => item.id === beaconId);
  if (beacon) {
    return beacon.hostname;
  }
  return task?.beacon_id ? task.beacon_id.slice(0, 8) : beaconId.slice(0, 8);
}

function shouldNotifyAwayFromTask(pathname: string): boolean {
  return !pathname.startsWith('/beacons/') || document.hidden;
}

export function TaskCompletionNotifier() {
  const realtime = useRealtime();
  const location = useLocation();
  const navigate = useNavigate();
  const taskCache = useRef(new Map<string, Task>());
  const notifiedEventIds = useRef(new Set<string>());
  const [toast, setToast] = useState<TaskCompletionToast | null>(null);

  const navigateToTask = useCallback((nextToast: TaskCompletionToast): void => {
    navigate(`/beacons/${nextToast.beaconId}/commands?task_id=${encodeURIComponent(nextToast.taskId)}`);
    setToast(null);
  }, [navigate]);

  useEffect(() => {
    if (!toast) {
      return undefined;
    }
    const handle = window.setTimeout(() => setToast(null), 8_000);
    return () => window.clearTimeout(handle);
  }, [toast]);

  useEffect(() => {
    const event = realtime.latestEvent;
    if (!event) {
      return;
    }

    const task = taskFromRealtimeEvent(event);
    if (task) {
      taskCache.current.set(task.id, task);
    }

    const result = taskResultFromRealtimeEvent(event);
    if (event.type !== 'task.result.completed' || !result || notifiedEventIds.current.has(event.id)) {
      return;
    }
    notifiedEventIds.current.add(event.id);
    if (!shouldNotifyAwayFromTask(location.pathname)) {
      return;
    }

    const cachedTask = taskCache.current.get(result.task_id);
    const nextToast: TaskCompletionToast = {
      beaconId: result.beacon_id,
      beaconLabel: taskBeaconLabel(cachedTask, result.beacon_id, realtime.beacons),
      eventId: event.id,
      module: cachedTask?.module ?? 'task',
      taskId: result.task_id,
    };
    setToast(nextToast);

    if (typeof Notification === 'undefined') {
      return;
    }
    const title = `${nextToast.module} completed`;
    const body = `Result from ${nextToast.beaconLabel}`;
    if (Notification.permission === 'granted') {
      const notification = new Notification(title, { body, tag: nextToast.eventId });
      notification.onclick = () => navigateToTask(nextToast);
      return;
    }
    if (Notification.permission === 'default') {
      void Notification.requestPermission().then((permission) => {
        if (permission !== 'granted') {
          return;
        }
        const notification = new Notification(title, { body, tag: nextToast.eventId });
        notification.onclick = () => navigateToTask(nextToast);
      });
    }
  }, [location.pathname, navigateToTask, realtime.beacons, realtime.latestEvent]);

  if (!toast) {
    return null;
  }

  return (
    <div aria-live="polite" className="task-completion-toast" data-testid="task-completion-toast" role="status">
      <Bell aria-hidden="true" size={16} strokeWidth={2.1} />
      <button className="task-completion-toast-main" onClick={() => navigateToTask(toast)} type="button">
        <strong>{toast.module} completed</strong>
        <span>{toast.beaconLabel}</span>
      </button>
      <button aria-label="Open completed task" className="task-completion-toast-icon" onClick={() => navigateToTask(toast)} type="button">
        <ExternalLink aria-hidden="true" size={14} strokeWidth={2.1} />
      </button>
      <button aria-label="Dismiss task notification" className="task-completion-toast-icon" onClick={() => setToast(null)} type="button">
        <X aria-hidden="true" size={14} strokeWidth={2.1} />
      </button>
    </div>
  );
}
