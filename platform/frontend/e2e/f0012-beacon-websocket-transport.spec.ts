import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

import { baseURL, c2IsAvailable, c2Token, getProtocolInfo, loginAndConnectC2, websocketUrl } from './support/c2';
import { encodeProtocolFrame } from './support/protocolFrame';

async function waitForSocketOpen(socket: WebSocket) {
  if (socket.readyState === WebSocket.OPEN) {
    return;
  }
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Beacon WebSocket did not open')), 10_000);
    socket.addEventListener(
      'open',
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
    socket.addEventListener(
      'error',
      () => {
        clearTimeout(timer);
        reject(new Error('Beacon WebSocket failed to open'));
      },
      { once: true },
    );
  });
}

async function waitForSocketMessage(socket: WebSocket) {
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Beacon WebSocket ACK was not received')), 10_000);
    socket.addEventListener(
      'message',
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
    socket.addEventListener(
      'close',
      () => {
        clearTimeout(timer);
        reject(new Error('Beacon WebSocket closed before ACK'));
      },
      { once: true },
    );
  });
}

async function closeSocket(socket: WebSocket) {
  if (socket.readyState === WebSocket.CLOSED) {
    return;
  }
  await new Promise<void>((resolve) => {
    const timer = setTimeout(resolve, 2_000);
    socket.addEventListener(
      'close',
      () => {
        clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
    socket.close(1000);
  });
}

async function activeWebSocketCount(page: Page): Promise<number> {
  const value = await page.getByTestId('transport-active-websockets').textContent();
  return Number(value ?? Number.NaN);
}

async function waitForNumericActiveWebSocketCount(page: Page): Promise<number> {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const count = await activeWebSocketCount(page);
    if (Number.isFinite(count)) {
      return count;
    }
    await page.waitForTimeout(100);
  }
  return Number.NaN;
}

async function reloadTransportStatus(page: Page): Promise<number> {
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes('/api/v1/transport') && response.status() === 200,
    { timeout: 5_000 },
  );
  await page.reload();
  await responsePromise;
  return waitForNumericActiveWebSocketCount(page);
}

test('F0012 WebSocket transport status and beacon detail update in UI', async ({ page }) => {
  test.setTimeout(70_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  const eventId = Date.now();
  const hostname = `f0012-websocket-${eventId}`;

  await loginAndConnectC2(page);
  const accessToken = await c2Token();
  const protocol = await getProtocolInfo(accessToken);
  expect(protocol.current_version).toBe(1);

  await page.goto(`${baseURL}/settings/infrastructure`);
  await expect(page.getByTestId('transport-status-panel')).toContainText('Active WebSockets');
  const initialCount = await waitForNumericActiveWebSocketCount(page);

  const socket = new WebSocket(websocketUrl('/ws/beacon'), ['xero.beacon.v1']);
  await waitForSocketOpen(socket);
  socket.send(
    await encodeProtocolFrame(protocol, 'REGISTER', {
      architecture: 'x64',
      external_ip: '198.51.100.112',
      hostname,
      internal_ip: '10.112.0.10',
      machine_fingerprint_hash: `playwright-f0012-${eventId}`,
      os: 'Windows 11',
      pid: 1212,
      supported_versions: [1],
    }),
  );
  await waitForSocketMessage(socket);

  await expect
    .poll(
      async () => {
        return reloadTransportStatus(page);
      },
      { timeout: 5_000 },
    )
    .toBeGreaterThan(initialCount);

  const connectedCount = await activeWebSocketCount(page);
  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(hostname);
  await expect(page.getByTestId('beacon-roster')).toContainText(hostname, { timeout: 10_000 });
  await expect(page.getByTestId('beacon-detail-hostname')).toHaveText(hostname);
  await expect(page.getByTestId('beacon-detail-transport-mode')).toHaveText('WebSocket');
  await expect(page.getByTestId('beacon-detail-transport-state')).toHaveText('Connected');

  await closeSocket(socket);
  await page.goto(`${baseURL}/settings/infrastructure`);
  await expect
    .poll(
      async () => {
        return reloadTransportStatus(page);
      },
      { timeout: 5_000 },
    )
    .toBeLessThan(connectedCount);
});
