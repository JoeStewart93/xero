import { expect, request, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';

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

async function dragBeaconToTarget(page: Page, row: Locator, dropTarget: Locator) {
  const dataTransfer = await page.evaluateHandle(() => new DataTransfer());
  try {
    await row.dispatchEvent('dragstart', { dataTransfer });
    await dropTarget.dispatchEvent('dragover', { dataTransfer });
    await dropTarget.dispatchEvent('drop', { dataTransfer });
  } finally {
    await dataTransfer.dispose();
  }
}

function asDeliveredTask(value: unknown): DeliveredTask {
  expect(value).toBeTruthy();
  expect(typeof value).toBe('object');
  return value as DeliveredTask;
}

test('F0026 task execution UI creates, targets, completes, and filters tasks', async ({ page }) => {
  test.setTimeout(100_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const alphaHost = `f0026-task-${eventId}-alpha`;
  const betaHost = `f0026-task-${eventId}-beta`;
  const completedCommand = `printf f0026-complete-${eventId}`;
  const failedCommand = `f0026-failed-${eventId}`;
  const stdout = `f0026-complete-${eventId}`;

  await loginAndConnectC2(page);
  const accessToken = await c2Token();
  const protocol = await getProtocolInfo(accessToken);
  const fixture = await createProtocolFixture(protocol);
  const alpha = await registerBeacon(alphaHost);
  const beta = await registerBeacon(betaHost);
  const betaHeartbeat = await postLongPollFrame(
    beta.beacon_id,
    beta.beacon_token,
    await fixture.encode('HEARTBEAT', { beacon_id: beta.beacon_id, hostname: betaHost }),
  );
  expect(betaHeartbeat.ok()).toBeTruthy();

  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(`f0026-task-${eventId}`);
  const alphaRow = page.getByTestId(`beacon-row-${alpha.beacon_id}`);
  const betaRow = page.getByTestId(`beacon-row-${beta.beacon_id}`);
  await expect(alphaRow).toBeVisible({ timeout: 10_000 });
  await expect(betaRow).toBeVisible({ timeout: 10_000 });

  const taskPanel = page.getByTestId('task-execution-panel');
  await expect(taskPanel.getByLabel('Task module')).toHaveValue('shell');
  await expect(taskPanel.getByRole('option', { name: 'Port Scan' })).toHaveCount(0);
  await expect(taskPanel.getByRole('button', { name: /^Queue$/ })).toBeDisabled();

  await dragBeaconToTarget(page, betaRow, taskPanel.getByTestId('beacon-task-drop-target'));
  await expect(taskPanel.getByTestId('beacon-task-target-chip')).toContainText(betaHost);

  await taskPanel.getByLabel('Shell command').fill(completedCommand);
  await taskPanel.getByLabel('Shell type').selectOption('powershell');
  await taskPanel.getByLabel('Task priority').selectOption('urgent');
  await taskPanel.getByLabel('Timeout seconds').fill('45');
  await taskPanel.getByRole('button', { name: /^Queue$/ }).click();
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText(completedCommand, { timeout: 10_000 });

  const taskPollResponse = await pollLongPollFrameBody(beta.beacon_id, beta.beacon_token, 2);
  expect(taskPollResponse.status).toBe(200);
  const pollAck = await fixture.decode(taskPollResponse.body);
  const deliveredTask = asDeliveredTask(pollAck.payload.task);
  expect(deliveredTask.beacon_id).toBe(beta.beacon_id);
  expect(deliveredTask.args.command).toBe(completedCommand);
  expect(deliveredTask.args.shell_type).toBe('powershell');
  expect(deliveredTask.args.timeout_seconds).toBe(45);

  const completedResult = await postLongPollFrame(
    beta.beacon_id,
    beta.beacon_token,
    await fixture.encode('TASK_RESULT', {
      beacon_id: beta.beacon_id,
      exit_code: 0,
      status: 'completed',
      stderr: '',
      stdout,
      task_id: deliveredTask.id,
      timed_out: false,
      truncated: false,
    }),
  );
  expect(completedResult.ok()).toBeTruthy();

  await expect(taskPanel.getByLabel(`View result for ${completedCommand}`)).toBeVisible({ timeout: 10_000 });
  await taskPanel.getByLabel(`View result for ${completedCommand}`).click();
  await expect(taskPanel.getByTestId('task-result-panel')).toContainText(stdout, { timeout: 10_000 });
  await expect(taskPanel.getByTestId('task-result-panel')).toContainText('Exit 0');

  const failedTask = await createShellTask(accessToken, beta.beacon_id, failedCommand);
  const failedPollResponse = await pollLongPollFrameBody(beta.beacon_id, beta.beacon_token, 2);
  expect(failedPollResponse.status).toBe(200);
  const failedPollAck = await fixture.decode(failedPollResponse.body);
  expect(asDeliveredTask(failedPollAck.payload.task).id).toBe(failedTask.id);

  const failedResult = await postLongPollFrame(
    beta.beacon_id,
    beta.beacon_token,
    await fixture.encode('TASK_RESULT', {
      beacon_id: beta.beacon_id,
      error_message: 'Process exited with status 1.',
      exit_code: 1,
      status: 'failed',
      stderr: 'denied',
      stdout: '',
      task_id: failedTask.id,
      timed_out: false,
      truncated: false,
    }),
  );
  expect(failedResult.ok()).toBeTruthy();

  await taskPanel.getByRole('button', { name: /Refresh/ }).click();
  await taskPanel.getByLabel('Filter task status').selectOption('failed');
  await expect(taskPanel.getByTestId('beacon-task-list')).toContainText(failedCommand, { timeout: 10_000 });
  await expect(taskPanel.getByTestId('beacon-task-list')).not.toContainText(completedCommand);
  await taskPanel.getByLabel(`View result for ${failedCommand}`).click();
  await expect(taskPanel.getByTestId('task-failure-reason')).toContainText('Process exited with status 1.');
  await expect(taskPanel.getByTestId('task-result-panel')).toContainText('denied');
});
