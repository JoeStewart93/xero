import { expect, request } from '@playwright/test';
import type { Page } from '@playwright/test';

import type { ProtocolInfo } from './protocolFrame';

export const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';
export const c2BaseURL = process.env.PLAYWRIGHT_C2_BASE_URL ?? 'http://localhost:8001';
export const c2Password = process.env.C2_CONNECT_PASSWORD ?? 'c2_password';

export function websocketUrl(path: string): string {
  const url = new URL(c2BaseURL);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = path;
  url.search = '';
  return url.toString();
}

export async function c2IsAvailable() {
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

export async function c2Token() {
  const api = await request.newContext();
  try {
    const response = await api.post(`${c2BaseURL}/api/v1/c2/connect`, {
      data: { password: c2Password },
      timeout: 10_000,
    });
    expect(response.ok()).toBeTruthy();
    const payload = (await response.json()) as { access_token: string };
    return payload.access_token;
  } finally {
    await api.dispose();
  }
}

export async function getProtocolInfo(accessToken: string): Promise<ProtocolInfo> {
  const api = await request.newContext();
  try {
    const response = await api.get(`${c2BaseURL}/api/v1/protocol`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      timeout: 10_000,
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as ProtocolInfo;
  } finally {
    await api.dispose();
  }
}

export async function postProtocolFrame(accessToken: string, frame: Buffer) {
  const api = await request.newContext();
  try {
    return await api.post(`${c2BaseURL}/api/v1/protocol/frames`, {
      data: frame,
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/octet-stream',
      },
      timeout: 10_000,
    });
  } finally {
    await api.dispose();
  }
}

export async function registerBeacon(hostname: string) {
  const api = await request.newContext();
  try {
    const eventId = Date.now();
    const response = await api.post(`${c2BaseURL}/api/v1/beacons/register`, {
      data: {
        architecture: 'x64',
        external_ip: '198.51.100.113',
        hostname,
        internal_ip: '10.113.0.10',
        machine_fingerprint_hash: `playwright-${hostname}-${eventId}`,
        os: 'Windows 11',
        pid: 1313,
      },
      timeout: 10_000,
    });
    expect(response.ok()).toBeTruthy();
    return (await response.json()) as { beacon_id: string; beacon_token: string };
  } finally {
    await api.dispose();
  }
}

export async function postLongPollFrame(beaconId: string, beaconToken: string, frame: Buffer) {
  const api = await request.newContext();
  try {
    return await api.post(`${c2BaseURL}/api/v1/beacons/${beaconId}/frame`, {
      data: frame,
      headers: {
        Authorization: `Bearer ${beaconToken}`,
        'Content-Type': 'application/octet-stream',
      },
      timeout: 10_000,
    });
  } finally {
    await api.dispose();
  }
}

export async function startLongPoll(beaconId: string, beaconToken: string, timeoutSeconds = 3) {
  const api = await request.newContext();
  const responsePromise = api.get(`${c2BaseURL}/api/v1/beacons/${beaconId}/poll?timeout_seconds=${timeoutSeconds}`, {
    headers: { Authorization: `Bearer ${beaconToken}` },
    timeout: (timeoutSeconds + 5) * 1000,
  });
  return {
    response: responsePromise.finally(async () => {
      await api.dispose();
    }),
  };
}

export async function loginAndConnectC2(page: Page) {
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
