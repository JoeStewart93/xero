import { expect, request, test } from '@playwright/test';
import type { Locator } from '@playwright/test';

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

async function numericText(locator: Locator) {
  const text = await locator.textContent();
  return Number((text || '0').trim());
}

test('dashboard shows summary cards and updates for live beacon registration', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 API is not available');

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/home`);
  await expect(page.getByRole('heading', { name: 'Beacon summary' })).toBeVisible();
  await expect(page.getByTestId('dashboard-c2-state')).toHaveText('connected');

  const total = page.getByTestId('dashboard-total-beacons');
  const beforeTotal = await numericText(total);
  const hostname = `f0024-dashboard-${Date.now()}`;

  await registerBeacon(hostname);

  await expect(page.getByText(`${hostname} online`)).toBeVisible({ timeout: 10_000 });
  await expect.poll(async () => numericText(total), { timeout: 10_000 }).toBeGreaterThanOrEqual(beforeTotal + 1);
  await page.getByRole('button', { name: 'Create resource' }).click();
  await expect(page.getByRole('menu', { name: 'Create resource' }).getByRole('menuitem', { name: /Task/ })).toHaveAttribute('href', '/beacons?module=shell');
});

test('dashboard recent tasks shows a completed C2 task', async ({ page }) => {
  test.setTimeout(70_000);
  test.skip(!(await c2IsAvailable()), 'C2 API is not available');

  const eventId = Date.now();
  const hostname = `f0024-task-${eventId}`;
  const command = `printf f0024-task-${eventId}`;
  const stdout = `f0024-task-${eventId}`;

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

  await page.goto(`${baseURL}/home`);
  const recentTasks = page.getByRole('region', { name: 'Recent tasks' });
  await expect(recentTasks.getByRole('heading', { name: 'Recent tasks' })).toBeVisible();
  await expect(recentTasks.getByText(command, { exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(recentTasks.getByText('completed').first()).toBeVisible();
});
