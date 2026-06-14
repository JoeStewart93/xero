import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import type { OperatorRealtimeEvent } from '../operatorRealtime';
import { TaskCompletionNotifier } from './TaskCompletionNotifier';

const mocks = vi.hoisted(() => ({
  useRealtime: vi.fn(),
}));

vi.mock('../useRealtime', () => ({
  useRealtime: mocks.useRealtime,
}));

const taskEvent: OperatorRealtimeEvent = {
  data: {
    task: {
      args: { command: 'hostname' },
      beacon_id: 'beacon-one',
      cancelled_at: null,
      completed_at: '2026-06-13T00:00:00Z',
      created_at: '2026-06-13T00:00:00Z',
      dispatched_at: null,
      id: 'task-one',
      module: 'shell',
      priority: 'normal',
      queued_at: '2026-06-13T00:00:00Z',
      running_at: null,
      status: 'completed',
      updated_at: '2026-06-13T00:00:00Z',
    },
  },
  id: 'task-event',
  occurred_at: '2026-06-13T00:00:00Z',
  scope: { beacon_id: 'beacon-one', task_id: 'task-one' },
  source: { role: 'c2', service: 'xero-c2-core' },
  type: 'task.completed',
  version: 1,
};

const resultEvent: OperatorRealtimeEvent = {
  data: {
    task_result: {
      artifacts: [],
      beacon_id: 'beacon-one',
      completed_at: '2026-06-13T00:00:01Z',
      created_at: '2026-06-13T00:00:00Z',
      error_message: null,
      exit_code: 0,
      expires_at: '2026-06-20T00:00:00Z',
      id: 'result-one',
      metadata: {},
      output_sha256: 'output-sha',
      output_size_bytes: 8,
      status: 'completed',
      stderr_sha256: 'stderr-sha',
      stderr_size_bytes: 0,
      stdout_sha256: 'stdout-sha',
      stdout_size_bytes: 8,
      task_id: 'task-one',
      timed_out: false,
      truncated: false,
      updated_at: '2026-06-13T00:00:01Z',
    },
  },
  id: 'result-event',
  occurred_at: '2026-06-13T00:00:01Z',
  scope: { beacon_id: 'beacon-one', task_id: 'task-one' },
  source: { role: 'c2', service: 'xero-c2-core' },
  type: 'task.result.completed',
  version: 1,
};

function Harness() {
  const location = useLocation();
  return (
    <>
      <TaskCompletionNotifier />
      <span data-testid="location">{location.pathname}{location.search}</span>
    </>
  );
}

describe('TaskCompletionNotifier', () => {
  it('shows completion toast away from Beacons and navigates to the completed task', async () => {
    const realtimeState = {
      activeBeaconCount: 1,
      beaconCount: 1,
      beacons: [{ hostname: 'beacon-alpha', id: 'beacon-one', status: 'online' }],
      error: '',
      latestEvent: taskEvent,
      offlineBeaconCount: 0,
      status: 'connected',
    };
    mocks.useRealtime.mockReturnValue(realtimeState);
    const rendered = render(
      <MemoryRouter initialEntries={['/home']}>
        <Harness />
      </MemoryRouter>,
    );

    mocks.useRealtime.mockReturnValue({ ...realtimeState, latestEvent: resultEvent });
    rendered.rerender(
      <MemoryRouter initialEntries={['/home']}>
        <Harness />
      </MemoryRouter>,
    );

    expect((await screen.findByTestId('task-completion-toast')).textContent).toContain('shell completed');
    expect(screen.getByTestId('task-completion-toast').textContent).toContain('beacon-alpha');

    fireEvent.click(screen.getByRole('button', { name: 'Open completed task' }));

    expect(screen.getByTestId('location').textContent).toBe('/beacons/beacon-one/commands?task_id=task-one');
  });
});
