import { expect, test, type Page, type Route } from '@playwright/test';

function json(route: Route, payload: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}

async function mockApi(page: Page) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === '/api/auth/token/' && method === 'POST') {
      return json(route, { access: 'e2e-access', refresh: 'e2e-refresh' });
    }
    if (path === '/api/auth/refresh/' && method === 'POST') {
      return json(route, { access: 'e2e-access' });
    }
    if (path === '/api/auth/settings/' && method === 'GET') {
      return json(route, { base_currency: 'EUR' });
    }
    if (path === '/api/auth/settings/' && method === 'PUT') {
      return json(route, { base_currency: 'EUR' });
    }
    if (path === '/api/family-members/' && method === 'GET') {
      return json(route, []);
    }
    if (path === '/api/net-worth/summary/' && method === 'GET') {
      return json(route, {
        base_currency: 'EUR',
        total_assets: '1000.00',
        total_liabilities: '250.00',
        net_worth: '750.00',
        assets_by_category: {},
        assets_by_subcategory: {},
        liabilities_by_category: {},
        inflation_region: null,
        inflation_base_period: null,
        total_assets_real: null,
        total_liabilities_real: null,
        net_worth_real: null,
        assets_by_category_real: null,
        liabilities_by_category_real: null,
      });
    }
    if (path === '/api/net-worth/assets/' && method === 'GET') {
      return json(route, []);
    }
    if (path === '/api/net-worth/liabilities/' && method === 'GET') {
      return json(route, []);
    }
    if (path === '/api/net-worth/snapshots/' && method === 'GET') {
      return json(route, []);
    }
    if (path === '/api/net-worth/snapshots/from-current/' && method === 'POST') {
      return json(route, {
        id: 1,
        snapshot_date: '2026-02-16',
        base_currency: 'EUR',
        total_assets: '1000.00',
        total_liabilities: '250.00',
        net_worth: '750.00',
        created_at: '2026-02-16T00:00:00Z',
      });
    }
    if (path.startsWith('/api/core/fx-rates/') && method === 'GET') {
      return json(route, []);
    }
    if (path.startsWith('/api/core/inflation/') && method === 'GET') {
      return json(route, []);
    }
    return json(route, {});
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test('login redirects to net worth page', async ({ page }) => {
  await page.goto('/login');
  await page.locator('input[autocomplete="username"]').fill('demo');
  await page.locator('input[autocomplete="current-password"]').fill('demo');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('heading', { name: 'Patrimonio' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Datos auxiliares' })).toBeVisible();
});

test('net worth can navigate to auxiliary data page', async ({ page }) => {
  await page.goto('/login');
  await page.locator('input[autocomplete="username"]').fill('demo');
  await page.locator('input[autocomplete="current-password"]').fill('demo');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await page.getByRole('button', { name: 'Datos auxiliares' }).click();
  await expect(page).toHaveURL(/\/data$/);
  await expect(page.getByRole('heading', { name: 'Datos auxiliares' })).toBeVisible();
});
