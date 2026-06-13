import { expect, request, test } from '@playwright/test';
import type { Download } from '@playwright/test';

import {
  baseURL,
  c2BaseURL,
  c2IsAvailable,
  c2Token,
  loginAndConnectC2,
  registerBeacon,
} from './support/c2';

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

test('F0025 beacon management filters, exports, shows activity, and kills a beacon', async ({ page }) => {
  test.setTimeout(70_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const hostname = `f0025-beacon-${eventId}`;
  const command = `whoami-f0025-${eventId}`;

  await loginAndConnectC2(page);
  const accessToken = await c2Token();
  const registered = await registerBeacon(hostname);
  await createShellTask(accessToken, registered.beacon_id, command);

  await page.goto(`${baseURL}/beacons?status=online`);
  await page.getByLabel('Search beacons').fill(hostname);
  const row = page.getByTestId(`beacon-row-${registered.beacon_id}`);
  await expect(row).toBeVisible({ timeout: 10_000 });
  await row.click();
  await expect(page.getByTestId('beacon-detail-hostname')).toHaveText(hostname);
  await expect(page.getByTestId('beacon-detail-transport-mode')).toHaveText('REST');
  await expect(page.getByTestId('beacon-detail-transport-state')).toHaveText('Disconnected');
  await expect(page.getByTestId('beacon-activity-list')).toContainText(command, { timeout: 10_000 });

  await page.getByRole('button', { name: 'Offline' }).click();
  await expect(row).toBeHidden();
  await page.getByRole('button', { name: 'Online' }).click();
  await expect(row).toBeVisible();

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export visible beacons' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^xero-beacons-\d{4}-\d{2}-\d{2}\.csv$/);
  const csv = await downloadedText(download);
  expect(csv).toContain('hostname,os,status,last_seen,transport');
  expect(csv).toContain(hostname);

  await page.getByRole('button', { name: 'Kill beacon' }).first().click();
  const dialog = page.getByRole('dialog', { name: 'Kill beacon confirmation' });
  await expect(dialog).toContainText(`Remove ${hostname} from active inventory`);
  await dialog.getByRole('button', { name: 'Cancel' }).click();
  await expect(row).toBeVisible();

  await page.getByRole('button', { name: 'Kill beacon' }).first().click();
  await dialog.getByRole('button', { name: 'Kill beacon', exact: true }).click();
  await expect(row).toBeHidden({ timeout: 10_000 });
  await expect(page.getByText(`Removed ${hostname}; closed 0 sessions and cancelled 1 tasks.`)).toBeVisible();

  const api = await request.newContext();
  try {
    const activeList = await api.get(`${c2BaseURL}/api/v1/beacons`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      timeout: 10_000,
    });
    expect(activeList.ok()).toBeTruthy();
    const activePayload = (await activeList.json()) as { items: Array<{ id: string }> };
    expect(activePayload.items.some((item) => item.id === registered.beacon_id)).toBeFalsy();

    const historical = await api.get(`${c2BaseURL}/api/v1/beacons/${registered.beacon_id}?include_removed=true`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      timeout: 10_000,
    });
    expect(historical.ok()).toBeTruthy();
    const historicalPayload = (await historical.json()) as { removed_at: string | null };
    expect(historicalPayload.removed_at).toBeTruthy();
  } finally {
    await api.dispose();
  }
});
