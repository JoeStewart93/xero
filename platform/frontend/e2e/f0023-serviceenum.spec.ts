import { expect, test } from '@playwright/test';

import { baseURL, c2IsAvailable, loginAndConnectC2 } from './support/c2';

test('operator runs service enumeration from an open port scan result', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 API is not available');

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/recon`);
  await expect(page.getByRole('heading', { name: 'Port scan' })).toBeVisible();

  await page.getByLabel('Scan targets').fill('127.0.0.1');
  await page.getByLabel('Port range').fill('8000');
  await page.getByLabel('Timeout ms').fill('500');
  await page.getByLabel('Max threads').fill('2');
  await page.getByRole('button', { name: /Run scan/ }).click();

  const openEndpoint = page.getByRole('row').filter({ hasText: '127.0.0.1:8000' });
  await expect(openEndpoint).toContainText('open', { timeout: 15_000 });
  await openEndpoint.getByRole('button', { name: 'Enum' }).click();
  await expect(page.getByText('Service enumeration queued.')).toBeVisible();

  const serviceEndpoint = page.getByRole('row').filter({ hasText: '127.0.0.1:8000' });
  await expect(serviceEndpoint).toContainText('http', { timeout: 15_000 });
  await expect(page.getByText(/confidence/i)).toBeVisible();
  await expect(page.getByText('embedded-c2')).toBeVisible();
});
