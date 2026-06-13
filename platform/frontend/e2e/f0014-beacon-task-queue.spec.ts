import { expect, test } from '@playwright/test';

import {
  baseURL,
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
  args: {
    command?: string;
    shell_type?: string;
    timeout_seconds?: number;
  };
  beacon_id: string;
  id: string;
  module: string;
  priority: string;
  status: string;
}

function asDeliveredTask(value: unknown): DeliveredTask {
  expect(value).toBeTruthy();
  expect(typeof value).toBe('object');
  return value as DeliveredTask;
}

test('F0014 command queue dispatches and cancels shell tasks', async ({ page }) => {
  test.setTimeout(80_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const hostname = `f0014-task-${eventId}`;
  const firstCommand = `whoami-${eventId}`;
  const secondCommand = `hostname-${eventId}`;

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

  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(hostname);
  const row = page.getByTestId(`beacon-row-${registered.beacon_id}`);
  await expect(row).toBeVisible({ timeout: 10_000 });
  const taskPanel = page.getByTestId('task-execution-panel');
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText('No tasks queued for this beacon.');

  await taskPanel.getByLabel('Shell command').fill(firstCommand);
  await taskPanel.getByLabel('Shell type').selectOption('powershell');
  await taskPanel.getByLabel('Task priority').selectOption('urgent');
  await taskPanel.getByLabel('Timeout seconds').fill('45');
  await taskPanel.getByRole('button', { name: /^Queue$/ }).click();
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText(firstCommand, { timeout: 10_000 });
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText('queued');

  const taskPollResponse = await pollLongPollFrameBody(registered.beacon_id, registered.beacon_token, 2);
  expect(taskPollResponse.status).toBe(200);
  const pollAck = await fixture.decode(taskPollResponse.body);
  expect(pollAck.messageType).toBe('ACK');
  const deliveredTask = asDeliveredTask(pollAck.payload.task);
  expect(deliveredTask.beacon_id).toBe(registered.beacon_id);
  expect(deliveredTask.module).toBe('shell');
  expect(deliveredTask.priority).toBe('urgent');
  expect(deliveredTask.status).toBe('dispatched');
  expect(deliveredTask.args.command).toBe(firstCommand);
  expect(deliveredTask.args.shell_type).toBe('powershell');
  expect(deliveredTask.args.timeout_seconds).toBe(45);

  await taskPanel.getByRole('button', { name: /Refresh/ }).click();
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText('dispatched', { timeout: 10_000 });

  await taskPanel.getByLabel('Shell command').fill(secondCommand);
  await taskPanel.getByLabel('Shell type').selectOption('cmd');
  await taskPanel.getByLabel('Task priority').selectOption('high');
  await taskPanel.getByLabel('Timeout seconds').fill('30');
  await taskPanel.getByRole('button', { name: /^Queue$/ }).click();
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText(secondCommand, { timeout: 10_000 });
  await taskPanel.getByLabel(`Cancel task ${secondCommand}`).click();
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText('cancelled', { timeout: 10_000 });

  const emptyPollResponse = await pollLongPollFrameBody(registered.beacon_id, registered.beacon_token, 1);
  expect(emptyPollResponse.status).toBe(204);
});
