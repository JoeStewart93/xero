import { expect, test } from '@playwright/test';

import { baseURL, c2IsAvailable, loginAndConnectC2 } from './support/c2';

test('F0028 Inventory module browser launches port scan handoff through live C2', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/assets`);

  await expect(page.getByRole('heading', { name: 'Inventory' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Port Scan/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Service Enumeration/ })).toBeVisible();

  await page.getByLabel('Search modules').fill('service');
  await expect(page.getByRole('button', { name: /Service Enumeration/ })).toBeVisible();
  await expect(page.getByRole('button', { name: /Port Scan/ })).toHaveCount(0);

  await page.getByLabel('Search modules').fill('');
  await page.getByRole('button', { name: /Port Scan/ }).click();
  await expect(page.getByRole('table')).toContainText('targets');
  await expect(page.getByText('"port_range": "22,80,443"')).toBeVisible();

  await page.getByRole('button', { name: /Open in Recon/ }).click();

  await expect(page).toHaveURL(/\/recon\?module=builtin\.portscan/);
  await expect(page.getByText('Port scan loaded from Inventory.')).toBeVisible();
  await expect(page.getByLabel('Scan targets')).toHaveValue('127.0.0.1');
  await expect(page.getByLabel('Port range')).toHaveValue('22,80,443');
  await expect(page.getByLabel('Execution target')).toHaveValue('auto');
});
