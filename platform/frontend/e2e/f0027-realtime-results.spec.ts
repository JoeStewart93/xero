import { createHash } from 'crypto';

import { expect, request, test } from '@playwright/test';

import {
  baseURL,
  c2BaseURL,
  c2IsAvailable,
  c2Token,
  getProtocolInfo,
  loginAndConnectC2,
  pollLongPollFrameBody,
  postLongPollFrame,
  registerBeacon,
} from './support/c2';
import { createProtocolFixture } from './support/protocolFrame';

interface DeliveredTask {
  id: string;
}

async function createShellTask(accessToken: string, beaconId: string, command: string) {
  const api = await request.newContext();
  try {
    const response = await api.post(`${c2BaseURL}/api/v1/tasks`, {
      data: {
        args: { command, shell_type: 'auto', timeout_seconds: 60 },
        beacon_id: beaconId,
        module: 'shell',
        priority: 'normal',
      },
      headers: { Authorization: `Bearer ${accessToken}` },
      timeout: 10_000,
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as { id: string };
  } finally {
    await api.dispose();
  }
}

function sha256(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

test('F0027 task result chunks stream before completion and completion toast links back to detail', async ({ page }) => {
  test.setTimeout(110_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const hostname = `f0027-stream-${eventId}`;
  const command = `printf f0027-stream-${eventId}`;
  const firstChunk = Array.from(
    { length: 40 },
    (_, index) => `f0027-stream-${eventId}-chunk-one-${index}\n`,
  ).join('');
  const secondChunk = `f0027-stream-${eventId}-chunk-two\n`;
  const stdout = `${firstChunk}${secondChunk}`;
  const uploadId = `f0027-upload-${eventId}`;

  await loginAndConnectC2(page);
  const accessToken = await c2Token();
  const protocol = await getProtocolInfo(accessToken);
  const fixture = await createProtocolFixture(protocol);
  const registered = await registerBeacon(hostname);
  const heartbeat = await postLongPollFrame(
    registered.beacon_id,
    registered.beacon_token,
    await fixture.encode('HEARTBEAT', { beacon_id: registered.beacon_id, hostname }),
  );
  expect(heartbeat.ok()).toBeTruthy();

  const task = await createShellTask(accessToken, registered.beacon_id, command);
  const taskPollResponse = await pollLongPollFrameBody(registered.beacon_id, registered.beacon_token, 2);
  expect(taskPollResponse.status).toBe(200);
  const pollAck = await fixture.decode(taskPollResponse.body);
  expect((pollAck.payload.task as DeliveredTask).id).toBe(task.id);

  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(hostname);
  const taskPanel = page.getByTestId('task-execution-panel');
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText(command, { timeout: 10_000 });
  await taskPanel.getByTestId(`task-row-${task.id}`).click();
  await expect(taskPanel.getByTestId('stream-output-panel')).toBeVisible();

  const firstResult = await postLongPollFrame(
    registered.beacon_id,
    registered.beacon_token,
    await fixture.encode('TASK_RESULT', {
      beacon_id: registered.beacon_id,
      chunk: firstChunk,
      chunk_index: 0,
      chunk_sha256: sha256(firstChunk),
      exit_code: 0,
      status: 'completed',
      stream: 'stdout',
      stream_sha256: sha256(stdout),
      stream_size_bytes: Buffer.byteLength(stdout, 'utf8'),
      task_id: task.id,
      total_chunks: 2,
      upload_id: uploadId,
    }),
  );
  expect(firstResult.ok()).toBeTruthy();
  await expect(taskPanel.getByTestId('stream-output-buffer')).toContainText(firstChunk, { timeout: 10_000 });
  await taskPanel.getByTestId('stream-output-buffer').evaluate((element) => {
    element.scrollTop = 0;
    element.dispatchEvent(new Event('scroll', { bubbles: true }));
  });
  await expect(taskPanel.getByRole('button', { name: 'Resume stream auto-scroll' })).toBeVisible();

  await page.goto(`${baseURL}/home`);
  const finalResult = await postLongPollFrame(
    registered.beacon_id,
    registered.beacon_token,
    await fixture.encode('TASK_RESULT', {
      beacon_id: registered.beacon_id,
      chunk: secondChunk,
      chunk_index: 1,
      chunk_sha256: sha256(secondChunk),
      exit_code: 0,
      result_final: true,
      status: 'completed',
      stderr: '',
      stream: 'stdout',
      stream_sha256: sha256(stdout),
      stream_size_bytes: Buffer.byteLength(stdout, 'utf8'),
      task_id: task.id,
      timed_out: false,
      total_chunks: 2,
      truncated: false,
      upload_id: uploadId,
    }),
  );
  expect(finalResult.ok()).toBeTruthy();

  const toast = page.getByTestId('task-completion-toast');
  await expect(toast).toContainText('shell completed', { timeout: 10_000 });
  await expect(toast).toContainText(hostname);
  await toast.getByLabel('Open completed task').click();

  await expect(page).toHaveURL(new RegExp(`/beacons\\?beacon_id=${registered.beacon_id}&task_id=${task.id}`));
  await expect(page.getByTestId('stream-output-buffer')).toContainText(firstChunk, { timeout: 10_000 });
  await expect(page.getByTestId('stream-output-buffer')).toContainText(secondChunk, { timeout: 10_000 });
});
