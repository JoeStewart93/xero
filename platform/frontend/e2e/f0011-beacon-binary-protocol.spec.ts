import { expect, test } from '@playwright/test';

import { baseURL, c2IsAvailable, c2Token, getProtocolInfo, loginAndConnectC2, postProtocolFrame } from './support/c2';
import { encodeProtocolFrame } from './support/protocolFrame';

test('F0011 protocol status, security event, and binary registration render in UI', async ({ page }) => {
  test.setTimeout(70_000);
  test.skip(!(await c2IsAvailable()), 'C2 backend stack is not available');

  await loginAndConnectC2(page);
  const accessToken = await c2Token();
  const protocol = await getProtocolInfo(accessToken);
  expect(protocol.current_version).toBe(1);
  expect(protocol.frame_harness_enabled).toBeTruthy();

  await page.goto(`${baseURL}/settings/infrastructure`);
  await expect(page.getByTestId('protocol-status-panel')).toContainText('v1');
  await expect(page.getByTestId('protocol-status-panel')).toContainText('X25519-HKDF-SHA256');

  const tamperedFrame = await encodeProtocolFrame(protocol, 'HEARTBEAT', {
    beacon_id: '11111111-1111-1111-1111-111111111111',
  });
  tamperedFrame[tamperedFrame.length - 1] ^= 0x01;
  const tampered = await postProtocolFrame(accessToken, tamperedFrame);
  expect(tampered.status()).toBe(401);

  await page.reload();
  await expect(page.getByTestId('protocol-security-events')).toContainText('protocol.hmac_mismatch');
  await expect(page.getByTestId('protocol-security-events')).toContainText('Frame HMAC verification failed');

  const eventId = Date.now();
  const hostname = `f0011-protocol-${eventId}`;
  const frame = await encodeProtocolFrame(protocol, 'REGISTER', {
    architecture: 'x64',
    external_ip: '198.51.100.111',
    hostname,
    internal_ip: '10.111.0.10',
    machine_fingerprint_hash: `playwright-f0011-${eventId}`,
    os: 'Windows 11',
    pid: 1111,
    supported_versions: [1],
  });
  const registered = await postProtocolFrame(accessToken, frame);
  expect(registered.ok()).toBeTruthy();

  await page.goto(`${baseURL}/beacons`);
  await page.getByLabel('Search beacons').fill(hostname);
  await expect(page.getByTestId('beacon-roster')).toContainText(hostname, { timeout: 10_000 });
  await expect(page.getByTestId('beacon-detail-hostname')).toHaveText(hostname);
  await expect(page.getByTestId('beacon-detail-protocol-version')).toHaveText('v1');
});
