import { expect, request, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';
const c2BaseURL = process.env.PLAYWRIGHT_C2_BASE_URL ?? 'http://localhost:8001';
const c2Password = process.env.C2_CONNECT_PASSWORD ?? 'c2_password';

async function c2IsAvailable() {
  const api = await request.newContext();
  try {
    const response = await api.get(`${c2BaseURL}/health`, { timeout: 2_000 });
    return response.ok();
  } catch {
    return false;
  } finally {
    await api.dispose();
  }
}

async function loginAndConnectC2(page: Page) {
  await page.goto(`${baseURL}/login`);
  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page).toHaveURL(/\/home$/);

  await page.goto(`${baseURL}/settings`);
  await page.getByLabel('Backend URL').fill(c2BaseURL);
  await page.getByLabel('C2 password').fill(c2Password);
  await page.getByRole('button', { name: 'Connect', exact: true }).click();

  await expect(page.getByLabel(/C2 Connected/)).toBeVisible();
  await page.goto(`${baseURL}/home`);
  await expect(page.getByTestId('home-realtime-status')).toHaveText('connected', { timeout: 10_000 });
}

async function registerBeacon(fingerprint: string, hostname: string, os = 'Windows 11') {
  const api = await request.newContext();
  try {
    const response = await api.post(`${c2BaseURL}/api/v1/beacons/register`, {
      data: {
        architecture: 'x64',
        external_ip: '198.51.100.61',
        hostname,
        internal_ip: '10.61.0.9',
        machine_fingerprint_hash: fingerprint,
        os,
        pid: 6109,
      },
      timeout: 10_000,
    });
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    expect(payload.beacon_token).toBeTruthy();
    return payload as { beacon_id: string; beacon_token: string };
  } finally {
    await api.dispose();
  }
}

test('registered beacon appears in Beacons detail and updates on re-registration', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const fingerprint = `playwright-f0009-${Date.now()}`;
  const originalHost = `f0009-original-${Date.now()}`;
  const updatedHost = `f0009-updated-${Date.now()}`;

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/beacons`);

  await expect(page.getByRole('heading', { name: 'Beacon overview' })).toBeVisible();
  const original = await registerBeacon(fingerprint, originalHost);

  await expect(page.getByTestId(`beacon-row-${original.beacon_id}`)).toBeVisible({ timeout: 5_000 });
  await page.getByTestId(`beacon-row-${original.beacon_id}`).click();
  await expect(page.getByTestId('beacon-detail-hostname')).toHaveText(originalHost);
  await expect(page.getByTestId('beacon-detail-os')).toHaveText('Windows 11');

  const updated = await registerBeacon(fingerprint, updatedHost, 'Ubuntu 24.04');

  await expect(page.getByTestId('beacon-detail-hostname')).toHaveText(updatedHost, { timeout: 5_000 });
  await expect(page.getByTestId('beacon-detail-os')).toHaveText('Ubuntu 24.04');
  await expect(page.getByTestId(`beacon-row-${updated.beacon_id}`)).toContainText(updatedHost);
  await expect(page.getByTestId(`beacon-row-${updated.beacon_id}`)).not.toContainText(originalHost);

  await page.goto(`${baseURL}/home`);
  await expect(page.getByTestId('home-realtime-status')).toHaveText('connected', { timeout: 10_000 });
  const repeated = await registerBeacon(fingerprint, updatedHost, 'Ubuntu 24.04');
  await expect.poll(async () => Number(await page.getByTestId('home-beacon-count').textContent()), { timeout: 5_000 }).toBeGreaterThan(0);
  await expect(page.getByTestId('home-latest-realtime-event')).toContainText('beacon.', { timeout: 5_000 });
  expect(repeated.beacon_id).toBe(updated.beacon_id);
  expect(repeated.beacon_token).not.toBe(updated.beacon_token);
});
