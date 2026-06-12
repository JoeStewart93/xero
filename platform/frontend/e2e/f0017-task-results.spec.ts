import { expect, request, test } from '@playwright/test';
import type { Download } from '@playwright/test';

import {
  baseURL,
  c2BaseURL,
  c2IsAvailable,
  c2Token,
  getProtocolInfo,
  loginAndConnectC2,
  postLongPollFrame,
  registerBeacon,
  startLongPoll,
} from './support/c2';
import { encodeProtocolFrame } from './support/protocolFrame';

async function createShellTask(accessToken: string, beaconId: string, command: string) {
  const api = await request.newContext();
  try {
    const response = await api.post(`${c2BaseURL}/api/v1/tasks`, {
      data: {
        args: { command },
        beacon_id: beaconId,
        module: 'shell',
        priority: 'urgent',
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

async function downloadedText(download: Download) {
  const stream = await download.createReadStream();
  expect(stream).toBeTruthy();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString('utf8');
}

test('F0017 task result panel renders output and downloads combined text', async ({ page }) => {
  test.setTimeout(70_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const hostname = `f0017-result-${eventId}`;
  const command = `printf f0017-result-${eventId}`;
  const stdout = `f0017-result-${eventId}`;

  await loginAndConnectC2(page);
  const accessToken = await c2Token();
  const protocol = await getProtocolInfo(accessToken);
  const registered = await registerBeacon(hostname);

  const heartbeatFrame = await encodeProtocolFrame(protocol, 'HEARTBEAT', {
    beacon_id: registered.beacon_id,
    hostname,
  });
  const heartbeat = await postLongPollFrame(registered.beacon_id, registered.beacon_token, heartbeatFrame);
  expect(heartbeat.ok()).toBeTruthy();

  const task = await createShellTask(accessToken, registered.beacon_id, command);

  const taskPoll = await startLongPoll(registered.beacon_id, registered.beacon_token, 2);
  const taskPollResponse = await taskPoll.response;
  expect(taskPollResponse.status()).toBe(200);

  const resultFrame = await encodeProtocolFrame(protocol, 'TASK_RESULT', {
    beacon_id: registered.beacon_id,
    exit_code: 0,
    status: 'completed',
    stderr: '',
    stdout,
    task_id: task.id,
  });
  const result = await postLongPollFrame(registered.beacon_id, registered.beacon_token, resultFrame);
  expect(result.ok()).toBeTruthy();

  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(hostname);
  await expect(page.getByTestId('beacon-roster')).toContainText(hostname, { timeout: 10_000 });
  await page.getByTestId(`beacon-row-${registered.beacon_id}`).dblclick();

  await expect(page.getByRole('dialog', { name: `Host operations for ${hostname}` })).toBeVisible();
  await expect(page.getByTestId('beacon-task-list')).toContainText(command);
  await page.getByRole('button', { name: `View result for ${command}` }).click();

  await expect(page.getByTestId('task-result-panel')).toContainText(stdout);
  await expect(page.getByTestId('task-result-panel')).toContainText('Exit 0');

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download combined result' }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toBe(`${task.id}-combined.txt`);
  expect(await downloadedText(download)).toBe(stdout);
});
