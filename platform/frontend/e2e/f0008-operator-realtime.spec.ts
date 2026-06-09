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
  await expect(page.getByLabel('Realtime Connected')).toBeVisible({ timeout: 10_000 });
}

async function registerBeacon(hostname: string, eventId = Date.now()) {
  const api = await request.newContext();
  try {
    const response = await api.post(`${c2BaseURL}/api/v1/beacons/register`, {
      data: {
        architecture: 'x64',
        external_ip: '198.51.100.44',
        hostname,
        internal_ip: '10.44.0.8',
        machine_fingerprint_hash: `playwright-${hostname}-${eventId}`,
        os: 'Windows 11',
        pid: 4408,
      },
      timeout: 10_000,
    });
    expect(response.ok()).toBeTruthy();
  } finally {
    await api.dispose();
  }
}

test('C2 realtime connection updates Home after beacon registration', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/home`);
  await expect(page.getByLabel('Realtime Connected')).toBeVisible({ timeout: 10_000 });

  const eventId = Date.now();
  await registerBeacon(`playwright-realtime-one-${eventId}`, eventId);

  await expect(page.getByTestId('home-latest-realtime-event')).toHaveText('beacon.registered', { timeout: 2_000 });
  await expect.poll(async () => Number(await page.getByTestId('home-beacon-count').textContent()), { timeout: 2_000 }).toBeGreaterThan(0);
});

test('two operator tabs receive beacon realtime updates', async ({ page, context }) => {
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/home`);
  const secondPage = await context.newPage();
  await secondPage.goto(`${baseURL}/login`);
  await secondPage.getByLabel('Username').fill('admin');
  await secondPage.getByLabel('Password').fill('admin');
  await secondPage.getByRole('button', { name: 'Log in' }).click();
  await expect(secondPage).toHaveURL(/\/home$/);

  await expect(page.getByLabel('Realtime Connected')).toBeVisible({ timeout: 10_000 });
  await expect(secondPage.getByLabel('Realtime Connected')).toBeVisible({ timeout: 10_000 });

  const eventId = Date.now();
  await registerBeacon(`playwright-realtime-two-tabs-${eventId}`, eventId);

  await expect(page.getByTestId('home-latest-realtime-event')).toHaveText('beacon.registered', { timeout: 2_000 });
  await expect(secondPage.getByTestId('home-latest-realtime-event')).toHaveText('beacon.registered', { timeout: 2_000 });
});
