import { expect, request, test } from '@playwright/test';

import { baseURL, c2BaseURL, c2IsAvailable, c2Token, loginAndConnectC2 } from './support/c2';

test.setTimeout(210_000);

test('F0015 deploy wizard builds and downloads a Go beacon artifact', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  await loginAndConnectC2(page);
  await page.goto(`${baseURL}/beacons/deploy`);
  await expect(page.getByRole('heading', { name: 'Deploy builder' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Linux amd64/ })).toBeVisible();

  const outputName = `pw-go-beacon-${Date.now()}`;
  await page.getByRole('textbox', { name: 'Profile' }).fill('playwright');
  await page.getByLabel('Artifact name').fill(outputName);
  await page.getByRole('button', { name: 'Build beacon' }).click();
  await expect(page.getByTestId('beacon-build-list')).toContainText(outputName);

  const accessToken = await c2Token();
  const api = await request.newContext();
  try {
    await expect
      .poll(
        async () => {
          const response = await api.get(`${c2BaseURL}/api/v1/beacon-builds?limit=10`, {
            headers: { Authorization: `Bearer ${accessToken}` },
            timeout: 10_000,
          });
          if (!response.ok()) {
            return 'api-error';
          }
          const builds = (await response.json()) as { items: Array<{ artifact_filename: string | null; status: string }> };
          return builds.items.find((build) => build.artifact_filename?.startsWith(outputName))?.status ?? 'missing';
        },
        { timeout: 180_000 },
      )
      .toBe('succeeded');
  } finally {
    await api.dispose();
  }

  await page.getByRole('button', { name: 'Refresh' }).click();
  await expect(page.getByTestId('beacon-build-list')).toContainText('Succeeded');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: `Download ${outputName}` }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(outputName);
});
