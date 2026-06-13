import { useCallback, useEffect, useMemo, useReducer, useRef } from 'react';

import { getTaskResultChunks } from './api';
import type { TaskResultChunk } from './api';
import type { C2Connection } from './c2ConnectionContext';
import type { OperatorRealtimeEvent, RealtimeStatus } from './operatorRealtime';
import { taskResultChunkFromRealtimeEvent } from './operatorRealtime';

export type TaskResultStreamName = TaskResultChunk['stream'];

export interface TaskResultStreamBuffer {
  chunks: TaskResultChunk[];
  isComplete: boolean;
  taskId: string;
}

interface TaskResultStreamState {
  byTask: Record<string, TaskResultStreamBuffer>;
}

type TaskResultStreamAction =
  | { chunks: TaskResultChunk[]; type: 'chunks' }
  | { taskId: string; type: 'clear' }
  | { taskId: string; type: 'complete' };

const streamOrder: TaskResultStreamName[] = ['stdout', 'stderr'];

function emptyBuffer(taskId: string): TaskResultStreamBuffer {
  return { chunks: [], isComplete: false, taskId };
}

function chunkKey(chunk: TaskResultChunk): string {
  return `${chunk.stream}:${chunk.upload_id}:${chunk.sequence}`;
}

function compareChunks(left: TaskResultChunk, right: TaskResultChunk): number {
  const streamDelta = streamOrder.indexOf(left.stream) - streamOrder.indexOf(right.stream);
  if (streamDelta !== 0) {
    return streamDelta;
  }
  const uploadDelta = left.upload_id.localeCompare(right.upload_id);
  if (uploadDelta !== 0) {
    return uploadDelta;
  }
  return left.sequence - right.sequence;
}

export function appendTaskResultChunks(
  buffer: TaskResultStreamBuffer,
  chunks: TaskResultChunk[],
): TaskResultStreamBuffer {
  const seen = new Set(buffer.chunks.map(chunkKey));
  const nextChunks = [...buffer.chunks];
  for (const chunk of chunks) {
    const key = chunkKey(chunk);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    nextChunks.push(chunk);
  }
  nextChunks.sort(compareChunks);
  return { ...buffer, chunks: nextChunks };
}

export function taskStreamText(buffer: TaskResultStreamBuffer, stream: TaskResultStreamName): string {
  return buffer.chunks
    .filter((chunk) => chunk.stream === stream)
    .map((chunk) => chunk.chunk)
    .join('');
}

export function lastSequenceForStream(buffer: TaskResultStreamBuffer | undefined, stream: TaskResultStreamName): number {
  if (!buffer) {
    return -1;
  }
  return buffer.chunks
    .filter((chunk) => chunk.stream === stream)
    .reduce((highest, chunk) => Math.max(highest, chunk.sequence), -1);
}

function reducer(state: TaskResultStreamState, action: TaskResultStreamAction): TaskResultStreamState {
  if (action.type === 'clear') {
    const current = state.byTask[action.taskId] ?? emptyBuffer(action.taskId);
    return {
      byTask: {
        ...state.byTask,
        [action.taskId]: { ...current, chunks: [] },
      },
    };
  }
  if (action.type === 'complete') {
    const current = state.byTask[action.taskId] ?? emptyBuffer(action.taskId);
    return {
      byTask: {
        ...state.byTask,
        [action.taskId]: { ...current, isComplete: true },
      },
    };
  }

  const byTask = { ...state.byTask };
  for (const chunk of action.chunks) {
    byTask[chunk.task_id] = appendTaskResultChunks(byTask[chunk.task_id] ?? emptyBuffer(chunk.task_id), [chunk]);
  }
  return { byTask };
}

export function useTaskResultStreams({
  activeTaskIds,
  connection,
  latestEvent,
  realtimeStatus,
}: {
  activeTaskIds: string[];
  connection: C2Connection;
  latestEvent: OperatorRealtimeEvent | null;
  realtimeStatus?: RealtimeStatus;
}) {
  const [state, dispatch] = useReducer(reducer, { byTask: {} });
  const stateRef = useRef(state);
  const activeTaskIdsKey = useMemo(() => Array.from(new Set(activeTaskIds)).sort().join('|'), [activeTaskIds]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const backfillTask = useCallback(async (taskId: string) => {
    const current = stateRef.current.byTask[taskId];
    const responses = await Promise.all(streamOrder.map((stream) => (
      getTaskResultChunks(connection.baseUrl, connection.accessToken, taskId, {
        afterSequence: lastSequenceForStream(current, stream),
        stream,
      })
    )));
    const chunks = responses.flatMap((response) => response.items);
    if (chunks.length > 0) {
      dispatch({ chunks, type: 'chunks' });
    }
  }, [connection.accessToken, connection.baseUrl]);

  useEffect(() => {
    const chunk = latestEvent ? taskResultChunkFromRealtimeEvent(latestEvent) : null;
    if (chunk) {
      dispatch({ chunks: [chunk], type: 'chunks' });
      return;
    }
    if (latestEvent?.type === 'task.result.completed' && latestEvent.scope.task_id) {
      dispatch({ taskId: latestEvent.scope.task_id, type: 'complete' });
    }
  }, [latestEvent]);

  useEffect(() => {
    if (realtimeStatus && realtimeStatus !== 'connected') {
      return;
    }
    const taskIds = activeTaskIdsKey ? activeTaskIdsKey.split('|').filter(Boolean) : [];
    for (const taskId of taskIds) {
      void backfillTask(taskId).catch(() => undefined);
    }
  }, [activeTaskIdsKey, backfillTask, realtimeStatus]);

  const streamForTask = useCallback((taskId: string): TaskResultStreamBuffer => (
    state.byTask[taskId] ?? emptyBuffer(taskId)
  ), [state.byTask]);

  const clearTaskStream = useCallback((taskId: string) => {
    dispatch({ taskId, type: 'clear' });
  }, []);

  return {
    backfillTask,
    clearTaskStream,
    streamForTask,
  };
}
