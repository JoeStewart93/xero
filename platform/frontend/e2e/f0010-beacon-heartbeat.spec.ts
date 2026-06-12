import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { expect, request, test } from '@playwright/test';
import type { Page } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';
const c2BaseURL = process.env.PLAYWRIGHT_C2_BASE_URL ?? 'http://localhost:8001';
const c2Password = process.env.C2_CONNECT_PASSWORD ?? 'c2_password';
const c2PostgresDb = process.env.C2_POSTGRES_DB ?? 'xero_c2';
const c2PostgresUser = process.env.C2_POSTGRES_USER ?? 'xero_c2';
const platformRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

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

async function registerBeacon(fingerprint: string, hostname: string) {
  const api = await request.newContext();
  try {
    const response = await api.post(`${c2BaseURL}/api/v1/beacons/register`, {
      data: {
        architecture: 'x64',
        external_ip: '198.51.100.70',
        hostname,
        internal_ip: '10.70.0.10',
        machine_fingerprint_hash: fingerprint,
        os: 'Windows 11',
        pid: 7010,
      },
      timeout: 10_000,
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as { beacon_id: string; beacon_token: string };
  } finally {
    await api.dispose();
  }
}

async function heartbeatBeacon(beaconId: string, beaconToken: string, hostname?: string) {
  const api = await request.newContext();
  try {
    const response = await api.post(`${c2BaseURL}/api/v1/beacons/${beaconId}/heartbeat`, {
      data: hostname ? { hostname } : {},
      headers: { Authorization: `Bearer ${beaconToken}` },
      timeout: 10_000,
    });
    expect(response.ok()).toBeTruthy();
  } finally {
    await api.dispose();
  }
}

function ageBeaconPastStaleThreshold(beaconId: string) {
  execFileSync(
    'docker',
    [
      'compose',
      '-f',
      'docker-compose.c2.yml',
      'exec',
      '-T',
      'c2-postgres',
      'psql',
      '-U',
      c2PostgresUser,
      '-d',
      c2PostgresDb,
      '-c',
      `UPDATE beacons SET status = 'online', last_seen = NOW() - INTERVAL '5 minutes' WHERE id = '${beaconId}'`,
    ],
    { cwd: platformRoot, stdio: 'pipe' },
  );
}

test('beacon heartbeat updates Beacons overview and stale transition updates Home counts', async ({ page }) => {
  test.setTimeout(70_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const fingerprint = `playwright-f0010-${eventId}`;
  const hostname = `f0010-heartbeat-${eventId}`;
  const heartbeatHost = `f0010-heartbeat-updated-${eventId}`;

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/beacons`);

  const registered = await registerBeacon(fingerprint, hostname);
  const row = page.getByTestId(`beacon-row-${registered.beacon_id}`);
  await expect(row).toBeVisible({ timeout: 10_000 });
  await expect(row).toContainText(hostname);

  await heartbeatBeacon(registered.beacon_id, registered.beacon_token, heartbeatHost);
  await expect(row).toContainText(heartbeatHost);
  await expect(row).toContainText('online');
  await expect(page.getByTestId(`beacon-relative-${registered.beacon_id}`)).not.toHaveText('');

  ageBeaconPastStaleThreshold(registered.beacon_id);
  await expect(row).toContainText('offline', { timeout: 45_000 });

  await page.goto(`${baseURL}/home`);
  await expect.poll(async () => Number(await page.getByTestId('home-offline-beacon-count').textContent()), { timeout: 5_000 }).toBeGreaterThan(0);

  await heartbeatBeacon(registered.beacon_id, registered.beacon_token);
  await page.goto(`${baseURL}/beacons`);
  await expect(page.getByTestId(`beacon-row-${registered.beacon_id}`)).toContainText('online', { timeout: 10_000 });
});
