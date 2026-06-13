import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { TaskResultChunk } from '../api';
import { StreamOutput } from './StreamOutput';

function chunk(value: string, sequence = 0): TaskResultChunk {
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
    total_chunks: 2,
    upload_id: 'upload-one',
  };
}

describe('StreamOutput', () => {
  it('renders chunks, pauses follow mode on manual scroll up, and clears the buffer', () => {
    const onClear = vi.fn();
    render(<StreamOutput chunks={[chunk('line one\n')]} isComplete={false} onClear={onClear} stream="stdout" />);

    const buffer = screen.getByTestId('stream-output-buffer');
    expect(buffer.textContent).toContain('line one');

    Object.defineProperty(buffer, 'scrollHeight', { configurable: true, value: 500 });
    Object.defineProperty(buffer, 'clientHeight', { configurable: true, value: 100 });
    buffer.scrollTop = 0;
    fireEvent.scroll(buffer);

    expect(screen.getByRole('button', { name: 'Resume stream auto-scroll' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Clear stream buffer' }));

    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
