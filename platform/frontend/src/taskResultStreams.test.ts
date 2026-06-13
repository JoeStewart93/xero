import { describe, expect, it } from 'vitest';

import type { TaskResultChunk } from './api';
import {
  appendTaskResultChunks,
  lastSequenceForStream,
  taskStreamText,
  type TaskResultStreamBuffer,
} from './taskResultStreams';

function chunk(sequence: number, value: string, overrides: Partial<TaskResultChunk> = {}): TaskResultChunk {
  return {
    beacon_id: 'beacon-one',
    chunk: value,
    chunk_sha256: `sha-${sequence}`,
    created_at: '2026-06-13T00:00:00Z',
    id: `chunk-${sequence}`,
    received_at: '2026-06-13T00:00:00Z',
    sequence,
    stream: 'stdout',
    stream_sha256: null,
    stream_size_bytes: null,
    task_id: 'task-one',
    task_result_id: 'result-one',
    total_chunks: 3,
    upload_id: 'upload-one',
    ...overrides,
  };
}

function buffer(): TaskResultStreamBuffer {
  return { chunks: [], isComplete: false, taskId: 'task-one' };
}

describe('taskResultStreams', () => {
  it('appends ordered chunks and ignores duplicate stream/upload sequences', () => {
    const first = appendTaskResultChunks(buffer(), [chunk(1, 'two\n'), chunk(0, 'one\n')]);
    const deduped = appendTaskResultChunks(first, [chunk(1, 'duplicate\n')]);

    expect(taskStreamText(deduped, 'stdout')).toBe('one\ntwo\n');
    expect(deduped.chunks).toHaveLength(2);
    expect(lastSequenceForStream(deduped, 'stdout')).toBe(1);
  });

  it('keeps stdout and stderr buffers independent', () => {
    const next = appendTaskResultChunks(buffer(), [
      chunk(0, 'out\n'),
      chunk(0, 'err\n', { id: 'chunk-err', stream: 'stderr' }),
    ]);

    expect(taskStreamText(next, 'stdout')).toBe('out\n');
    expect(taskStreamText(next, 'stderr')).toBe('err\n');
    expect(lastSequenceForStream(next, 'stderr')).toBe(0);
  });
});
