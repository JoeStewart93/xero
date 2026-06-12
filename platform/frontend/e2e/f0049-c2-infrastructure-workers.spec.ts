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
}

test('Infrastructure shows workers and creates a scanner pairing token', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/settings/infrastructure`);

  await expect(page.getByRole('heading', { name: 'C2 infrastructure' })).toBeVisible();
  await expect(page.getByText('Embedded C2 beacon handler')).toBeVisible();
  await expect(page.getByText('Embedded C2 scanner')).toBeVisible();

  const scannerPanel = page.getByRole('region', { name: 'Scanners' });
  await scannerPanel.getByRole('button', { name: 'Add external' }).click();
  await page.getByLabel('Worker name').fill(`playwright-scanner-${Date.now()}`);
  await page.getByRole('button', { name: 'Create token' }).click();

  await expect(page.getByTestId('pairing-result')).toContainText('Worker startup command');
  await expect(page.getByTestId('pairing-result')).toContainText('WORKER_PAIRING_TOKEN=');
  await expect(page.getByTestId('pairing-result')).toContainText('docker-compose.scanner.yml');
});
