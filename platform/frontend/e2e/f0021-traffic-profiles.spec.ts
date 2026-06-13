import { expect, request, test } from '@playwright/test';

import { baseURL, c2BaseURL, c2IsAvailable, c2Token, loginAndConnectC2 } from './support/c2';

test('operator creates and assigns a traffic profile against live C2', async ({ page }) => {
  test.skip(!(await c2IsAvailable()), 'C2 API is not available');

  const api = await request.newContext();
  const accessToken = await c2Token();
  const unique = Date.now();
  const profileName = `E2E Traffic ${unique}`;
  const hostname = `f0021-profile-${unique}`;
  let profileId = '';
  let beaconId = '';

  try {
    await loginAndConnectC2(page);
    await page.goto(`${baseURL}/settings/profiles`);
    await expect(page.getByRole('heading', { name: 'Traffic profiles' })).toBeVisible();

    await page.getByRole('button', { name: /New profile/ }).click();
    await page.getByLabel('Name').fill(profileName);
    await page.getByLabel('Template key').fill('e2e');
    await page.getByLabel('Sleep seconds').fill('9');
    await page.getByLabel('Jitter').fill('0.15');
    await page.getByLabel('User-Agent').fill(`F0021-E2E/${unique}`);
    await page.getByLabel('Traffic profile headers').fill(`X-Profile: f0021-${unique}`);
    await page.getByRole('button', { name: /Create profile/ }).click();
    await expect(page.getByText(`${profileName} saved as version 1.`)).toBeVisible();

    const profilesResponse = await api.get(`${c2BaseURL}/api/v1/traffic-profiles`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(profilesResponse.ok()).toBeTruthy();
    const profiles = (await profilesResponse.json()) as { items: Array<{ id: string; name: string }> };
    profileId = profiles.items.find((profile) => profile.name === profileName)?.id ?? '';
    expect(profileId).toBeTruthy();

    await page.goto(`${baseURL}/beacons`);
    await expect(page.getByRole('heading', { name: 'Beacon overview' })).toBeVisible();
    const registerResponse = await api.post(`${c2BaseURL}/api/v1/beacons/register`, {
      data: {
        architecture: 'x64',
        external_ip: '198.51.100.121',
        hostname,
        internal_ip: '10.121.0.10',
        machine_fingerprint_hash: `f0021-${unique}`,
        os: 'Windows 11',
        pid: 2121,
      },
    });
    expect(registerResponse.ok()).toBeTruthy();
    const registered = (await registerResponse.json()) as { beacon_id: string; beacon_token: string };
    beaconId = registered.beacon_id;

    await expect(page.getByTestId('beacon-detail-hostname')).toHaveText(hostname);
    await page.getByLabel('Beacon traffic profile').selectOption(profileId);
    await expect(page.getByText(`Assigned ${profileName}.`)).toBeVisible();

    const heartbeatResponse = await api.post(`${c2BaseURL}/api/v1/beacons/${beaconId}/heartbeat`, {
      data: { hostname, internal_ip: '10.121.0.10', os: 'Windows 11', pid: 2121 },
      headers: { Authorization: `Bearer ${registered.beacon_token}` },
    });
    expect(heartbeatResponse.ok()).toBeTruthy();
    const heartbeat = (await heartbeatResponse.json()) as {
      profile: { config: { headers: Record<string, string>; user_agent: string }; id: string };
      sleep: number;
    };
    expect(heartbeat.sleep).toBe(9);
    expect(heartbeat.profile.id).toBe(profileId);
    expect(heartbeat.profile.config.user_agent).toBe(`F0021-E2E/${unique}`);
    expect(heartbeat.profile.config.headers['X-Profile']).toBe(`f0021-${unique}`);
  } finally {
    if (beaconId) {
      await api.delete(`${c2BaseURL}/api/v1/beacons/${beaconId}/profile`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      }).catch(() => undefined);
    }
    if (profileId) {
      await api.delete(`${c2BaseURL}/api/v1/traffic-profiles/${profileId}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      }).catch(() => undefined);
    }
    await api.dispose();
  }
});
