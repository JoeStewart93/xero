import { expect, test } from '@playwright/test';

import { baseURL, c2IsAvailable, loginAndConnectC2 } from './support/c2';

test('operator runs an embedded port scan against live C2', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 API is not available');

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/recon`);
  await expect(page.getByRole('heading', { name: 'Port scan' })).toBeVisible();

  await page.getByLabel('Scan targets').fill('127.0.0.1');
  await page.getByLabel('Port range').fill('8000,65534');
  await page.getByLabel('Timeout ms').fill('500');
  await page.getByLabel('Max threads').fill('2');
  await page.getByRole('button', { name: /Run scan/ }).click();
  await expect(page.getByText('Port scan queued.')).toBeVisible();

  const openEndpoint = page.getByRole('row').filter({ hasText: '127.0.0.1:8000' });
  await expect(openEndpoint).toContainText('open', { timeout: 15_000 });
  await expect(page.getByText('embedded-c2')).toBeVisible();
  await expect(page.getByLabel('Scan progress', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Port scan progress output')).toContainText('127.0.0.1:8000 open');
});
