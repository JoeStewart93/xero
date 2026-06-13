import { expect, test } from '@playwright/test';

import { baseURL, c2IsAvailable, loginAndConnectC2, registerBeacon } from './support/c2';

test('F0031 shows automatic asset groups and grouping rules through live C2', async ({ page }) => {
  test.setTimeout(60_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const suffix = Date.now();
  const hostOne = `f0031-group-one-${suffix}.corp.local`;
  const hostTwo = `f0031-group-two-${suffix}.corp.local`;
  await registerBeacon(hostOne, {
    internal_ip: '10.131.5.10',
    machine_fingerprint_hash: `f0031-group-one-${suffix}`,
    os: 'Windows 11',
  });
  await registerBeacon(hostTwo, {
    internal_ip: '10.131.5.20',
    machine_fingerprint_hash: `f0031-group-two-${suffix}`,
    os: 'Windows 11',
  });

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/assets`);

  await expect(page.getByRole('complementary', { name: 'Automatic asset groups' })).toContainText('Subnet 10.131.5.0/24');
  await page.getByRole('button', { name: /Subnet 10\.131\.5\.0\/24/ }).click();

  const table = page.getByRole('table');
  await expect(table).toContainText(hostOne);
  await expect(table).toContainText(hostTwo);
  await expect(page.getByRole('complementary', { name: 'Asset detail' })).toContainText('Subnet 10.131.5.0/24');

  await page.goto(`${baseURL}/settings/grouping`);
  await expect(page.getByRole('heading', { name: 'Asset grouping' })).toBeVisible();
  await expect(page.getByText('Subnet grouping')).toBeVisible();
  await expect(page.getByText('Domain and workgroup grouping')).toBeVisible();
  await expect(page.getByText('OS grouping')).toBeVisible();
  await page.getByRole('button', { name: 'Rerun' }).click();
  await expect(page.getByText(/Rerun processed/)).toBeVisible();
});
