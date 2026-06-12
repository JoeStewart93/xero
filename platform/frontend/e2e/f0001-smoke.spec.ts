import { expect, test } from '@playwright/test';

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000';

test('login page loads without backend connection errors', async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleErrors.push(message.text());
    }
  });

  await page.goto(`${baseURL}/login`);

  await expect(page.getByRole('region', { name: 'Xero operator login' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Xero' })).toHaveCount(0);
  await expect(page.getByLabel('Username')).toBeVisible();
  await expect(page.getByLabel('Password')).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test('root redirects unauthenticated users to login', async ({ page }) => {
  await page.goto(`${baseURL}/`);

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('region', { name: 'Xero operator login' })).toBeVisible();
});

test('valid operator login redirects to home when C2 is disconnected', async ({ page }) => {
  await page.goto(`${baseURL}/login`);

  await page.getByLabel('Username').fill('operator');
  await page.getByLabel('Password').fill('operator_password');
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Home' })).toBeVisible();
  await expect(page.getByLabel('Architecture status')).toBeVisible();

  const homeSubNav = page.getByRole('navigation', { name: 'Home sections' });
  await expect(homeSubNav.getByText('Overview', { exact: true })).toBeVisible();
  await expect(homeSubNav.getByText('C2 Backend', { exact: true })).toHaveCount(0);
  await expect(homeSubNav.getByText('BFF', { exact: true })).toHaveCount(0);

  const primaryNav = page.locator('.side-nav');
  await expect(primaryNav.getByText('Home', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Projects', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Recon', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Beacons', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Exploits', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Payloads', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Assets', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Reports', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Loot', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Settings', { exact: true })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'System' }).getByText('Health', { exact: true })).toBeVisible();
  await expect(primaryNav.getByText('Findings', { exact: true })).toHaveCount(0);
  await expect(primaryNav.getByText('Inventory', { exact: true })).toHaveCount(0);
});

test('logout returns the operator to login', async ({ page }) => {
  await page.goto(`${baseURL}/login`);

  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page).toHaveURL(/\/home$/);

  await page.getByRole('button', { name: 'Log out' }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('region', { name: 'Xero operator login' })).toBeVisible();
});

test('authenticated 401 clears the shell session and redirects to login', async ({ page }) => {
  await page.route('**/api/v1/ready', async (route) => {
    await route.fulfill({
      body: JSON.stringify({ detail: 'Token expired' }),
      contentType: 'application/json',
      status: 401,
    });
  });

  await page.goto(`${baseURL}/login`);

  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('region', { name: 'Xero operator login' })).toBeVisible();
});

test('default local admin login redirects to home when C2 is disconnected', async ({ page }) => {
  await page.goto(`${baseURL}/login`);

  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Home' })).toBeVisible();
  await expect(page.getByLabel('C2 Disconnected')).toBeVisible();
});

test('invalid operator login shows an error message', async ({ page }) => {
  await page.goto(`${baseURL}/login`);

  await page.getByLabel('Username').fill('operator');
  await page.getByLabel('Password').fill('wrong');
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page.getByRole('alert')).toHaveText('Invalid username or password.');
  await expect(page).toHaveURL(/\/login$/);
});

test('unauthenticated project access redirects to login', async ({ page }) => {
  await page.goto(`${baseURL}/projects`);

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('region', { name: 'Xero operator login' })).toBeVisible();
});

test('unauthenticated health access redirects to login', async ({ page }) => {
  await page.goto(`${baseURL}/health`);

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('region', { name: 'Xero operator login' })).toBeVisible();
});

test('authenticated health page shows green dependency status', async ({ page }) => {
  await page.goto(`${baseURL}/login`);

  await page.getByLabel('Username').fill('admin');
  await page.getByLabel('Password').fill('admin');
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page).toHaveURL(/\/home$/);

  await page.goto(`${baseURL}/health`);

  await expect(page.getByRole('heading', { name: 'System health' })).toBeVisible();
  await expect(page.getByTestId('backend-status')).toHaveAttribute('data-status', 'healthy');
  await expect(page.getByTestId('postgres-status')).toHaveAttribute('data-status', 'healthy');
  await expect(page.getByTestId('redis-status')).toHaveAttribute('data-status', 'healthy');
});
