import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import {
  baseURL,
  c2IsAvailable,
  c2Token,
  getProtocolInfo,
  loginAndConnectC2,
  postLongPollFrame,
  registerBeacon,
  startLongPoll,
} from './support/c2';
import { encodeProtocolFrame } from './support/protocolFrame';

async function activeLongPollCount(page: Page): Promise<number> {
  const value = await page.getByTestId('transport-active-longpolls').textContent();
  return Number(value ?? Number.NaN);
}

async function waitForNumericActiveLongPollCount(page: Page): Promise<number> {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const count = await activeLongPollCount(page);
    if (Number.isFinite(count)) {
      return count;
    }
    await page.waitForTimeout(100);
  }
  return Number.NaN;
}

async function reloadLongPollTransportStatus(page: Page): Promise<number> {
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes('/api/v1/transport') && response.status() === 200,
    { timeout: 5_000 },
  );
  await page.reload();
  await responsePromise;
  return waitForNumericActiveLongPollCount(page);
}

test('F0013 long-poll frame POST and active poll status render in UI', async ({ page }) => {
  test.setTimeout(70_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const hostname = `f0013-longpoll-${eventId}`;

  await loginAndConnectC2(page);
  const accessToken = await c2Token();
  const protocol = await getProtocolInfo(accessToken);
  const registered = await registerBeacon(hostname);

  const frame = await encodeProtocolFrame(protocol, 'HEARTBEAT', {
    beacon_id: registered.beacon_id,
    hostname,
  });
  const framePost = await postLongPollFrame(registered.beacon_id, registered.beacon_token, frame);
  expect(framePost.ok()).toBeTruthy();

  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(hostname);
  await expect(page.getByTestId('beacon-roster')).toContainText(hostname, { timeout: 10_000 });
  await expect(page.getByTestId('beacon-detail-hostname')).toHaveText(hostname);
  await expect(page.getByTestId('beacon-detail-transport-mode')).toHaveText('Long-poll');
  await expect(page.getByTestId('beacon-detail-transport-state')).toHaveText('Disconnected');

  await page.goto(`${baseURL}/settings/infrastructure`);
  await expect(page.getByTestId('transport-status-panel')).toContainText('Active long-polls');
  const initialCount = await waitForNumericActiveLongPollCount(page);

  const heldPoll = await startLongPoll(registered.beacon_id, registered.beacon_token, 3);
  await expect
    .poll(
      async () => {
        return reloadLongPollTransportStatus(page);
      },
      { timeout: 5_000 },
    )
    .toBeGreaterThan(initialCount);

  const activeCount = await activeLongPollCount(page);
  const pollResponse = await heldPoll.response;
  expect(pollResponse.status()).toBe(204);

  await expect
    .poll(
      async () => {
        return reloadLongPollTransportStatus(page);
      },
      { timeout: 5_000 },
    )
    .toBeLessThan(activeCount);
});
