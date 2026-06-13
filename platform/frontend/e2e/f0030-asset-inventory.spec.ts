import { expect, test } from '@playwright/test';

import { baseURL, c2IsAvailable, loginAndConnectC2, registerBeacon } from './support/c2';

test('F0030 shows beacon-created assets through the live C2 inventory UI', async ({ page }) => {
  test.setTimeout(45_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const hostname = `f0030-asset-${Date.now()}.corp.local`;
  const registered = await registerBeacon(hostname);

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/assets`);
  await page.getByLabel('Search assets').fill(hostname);

  const table = page.getByRole('table');
  await expect(table).toContainText(hostname, { timeout: 10_000 });
  await expect(table).toContainText('Beacon host');
  await expect(table).toContainText('10.113.0.10');

  const detail = page.getByRole('complementary', { name: 'Asset detail' });
  await expect(detail).toContainText(hostname);
  await expect(detail).toContainText(registered.beacon_id);
  await expect(detail).toContainText('beacon.registered');
});
