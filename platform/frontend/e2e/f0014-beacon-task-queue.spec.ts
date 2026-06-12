import { expect, test } from '@playwright/test';

import {
  baseURL,
  c2IsAvailable,
  c2Token,
  getProtocolInfo,
  loginAndConnectC2,
  postProtocolFrameBody,
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

  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(hostname);
  const row = page.getByTestId(`beacon-row-${registered.beacon_id}`);
  await expect(row).toBeVisible({ timeout: 10_000 });
  await row.dblclick();
  await expect(page.getByRole('dialog', { name: `Host operations for ${hostname}` })).toBeVisible();
  await expect(page.getByTestId('beacon-task-list')).toContainText('No tasks queued for this beacon.');

  await page.getByLabel('Shell command').fill(firstCommand);
  await page.getByLabel('Shell type').selectOption('powershell');
  await page.getByLabel('Task priority').selectOption('urgent');
  await page.getByLabel('Timeout seconds').fill('45');
  await page.getByRole('button', { name: /^Queue$/ }).click();
  await expect(page.getByTestId('beacon-task-list')).toContainText(firstCommand, { timeout: 10_000 });
  await expect(page.getByTestId('beacon-task-list')).toContainText('queued');

  const pollResponse = await postProtocolFrameBody(
    accessToken,
    await fixture.encode('TASK_POLL', {
      beacon_id: registered.beacon_id,
    }),
  );
  expect(pollResponse.ok).toBeTruthy();
  const pollAck = await fixture.decode(pollResponse.body);
  expect(pollAck.messageType).toBe('ACK');
  const deliveredTask = asDeliveredTask(pollAck.payload.task);
  expect(deliveredTask.beacon_id).toBe(registered.beacon_id);
  expect(deliveredTask.module).toBe('shell');
  expect(deliveredTask.priority).toBe('urgent');
  expect(deliveredTask.status).toBe('dispatched');
  expect(deliveredTask.args.command).toBe(firstCommand);
  expect(deliveredTask.args.shell_type).toBe('powershell');
  expect(deliveredTask.args.timeout_seconds).toBe(45);

  await page.getByRole('button', { name: /Refresh/ }).click();
  await expect(page.getByTestId('beacon-task-list')).toContainText('dispatched', { timeout: 10_000 });

  await page.getByLabel('Shell command').fill(secondCommand);
  await page.getByLabel('Shell type').selectOption('cmd');
  await page.getByLabel('Task priority').selectOption('high');
  await page.getByLabel('Timeout seconds').fill('30');
  await page.getByRole('button', { name: /^Queue$/ }).click();
  await expect(page.getByTestId('beacon-task-list')).toContainText(secondCommand, { timeout: 10_000 });
  await page.getByRole('button', { name: `Cancel task ${secondCommand}` }).click();
  await expect(page.getByTestId('beacon-task-list')).toContainText('cancelled', { timeout: 10_000 });

  const emptyPollResponse = await postProtocolFrameBody(
    accessToken,
    await fixture.encode('TASK_POLL', {
      beacon_id: registered.beacon_id,
    }),
  );
  expect(emptyPollResponse.ok).toBeTruthy();
  const emptyPollAck = await fixture.decode(emptyPollResponse.body);
  expect(emptyPollAck.messageType).toBe('ACK');
  expect(emptyPollAck.payload.task).toBeNull();
});
