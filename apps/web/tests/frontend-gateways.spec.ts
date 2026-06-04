import { expect, test, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const jsonHeaders = { 'content-type': 'application/json' };

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    headers: jsonHeaders,
    body: JSON.stringify(body),
  });
}

async function mockAdminShell(page: Page) {
  await page.route('**/api/v1/me', async (route) => {
    await fulfillJson(route, {
      kind: 'user',
      subject: 'admin@example.test',
      email: 'admin@example.test',
      roles: ['admin'],
      permissions: [],
      gateway_id: null,
      is_dev: true,
    });
  });
  await page.route('**/api/v1/privacy/notice', async (route) => {
    await fulfillJson(route, {
      notice_version: '2026-06-01',
      title: 'Privacy notice',
      body: 'Privacy notice',
      accepted: true,
      accepted_at: '2026-06-01T00:00:00Z',
    });
  });
  await page.route('**/api/v1/cameras?*', async (route) => {
    await fulfillJson(route, { items: [], next_cursor: null });
  });
  await page.route('**/api/v1/admin/dashboard', async (route) => {
    await fulfillJson(route, {
      cameras: { total: 0, active: 0, retired: 0 },
      gateways: { total: 2, enabled: 1, disabled: 1 },
      users: { total: 0, active: 0, disabled: 0 },
      commands: { pending: 0 },
      publishing: { active: 0 },
    });
  });
  await page.route('**/health', async (route) => {
    await fulfillJson(route, { status: 'ok' });
  });
}

function gateway(id: string, name: string, status: 'enabled' | 'disabled') {
  return {
    gateway_id: id,
    name,
    status,
    last_seen_at: status === 'enabled' ? '2026-06-04T12:00:00Z' : null,
    created_at: '2026-06-01T00:00:00Z',
    disabled_at: status === 'disabled' ? '2026-06-02T00:00:00Z' : null,
    camera_count: status === 'enabled' ? 1 : 0,
  };
}

async function mockGateways(page: Page) {
  const firstPage = [
    gateway('11111111-1111-4111-8111-111111111111', 'edge-alpha', 'enabled'),
    gateway('22222222-2222-4222-8222-222222222222', 'edge-disabled', 'disabled'),
  ];
  const secondPage = [
    gateway('33333333-3333-4333-8333-333333333333', 'edge-beta', 'enabled'),
  ];

  await page.route('**/api/v1/admin/gateways**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname !== '/api/v1/admin/gateways') {
      await route.fallback();
      return;
    }
    if (request.method() === 'POST') {
      firstPage.unshift(gateway('44444444-4444-4444-8444-444444444444', 'edge-created', 'enabled'));
      await fulfillJson(route, {
        gateway_id: '44444444-4444-4444-8444-444444444444',
        name: 'edge-created',
        status: 'enabled',
        created_at: '2026-06-04T00:00:00Z',
        service_token: 'one-time-service-token-value',
      }, 201);
      return;
    }
    if (url.searchParams.get('cursor') === 'page-2') {
      await fulfillJson(route, { items: secondPage, next_cursor: null });
      return;
    }
    await fulfillJson(route, { items: firstPage, next_cursor: 'page-2' });
  });
}

test('gateways page exposes gateway ids, filters, load more, and assignment helper', async ({ page }) => {
  await mockAdminShell(page);
  await mockGateways(page);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Gateways' }).click();

  await expect(page.getByText('11111111-1111-4111-8111-111111111111')).toBeVisible();
  await expect(page.getByText('22222222-2222-4222-8222-222222222222')).toBeVisible();
  await expect(page.getByText('one-time-service-token-value')).toHaveCount(0);

  await page.getByPlaceholder('Search gateways by name or ID...').fill('22222222');
  await expect(page.getByText('edge-disabled')).toBeVisible();
  await expect(page.getByText('edge-alpha')).toHaveCount(0);

  await page.getByPlaceholder('Search gateways by name or ID...').fill('');
  await page.getByRole('combobox').selectOption('disabled');
  await expect(page.getByText('edge-disabled')).toBeVisible();
  await expect(page.getByText('edge-alpha')).toHaveCount(0);

  await page.getByRole('combobox').selectOption('all');
  await page.getByRole('button', { name: 'Load more gateways' }).click();
  await expect(page.getByText('33333333-3333-4333-8333-333333333333')).toBeVisible();

  await page.getByRole('button', { name: 'Assign' }).first().click();
  const dialog = page.getByRole('heading', { name: /Camera Assignment:/ }).locator('..');
  await expect(dialog).toContainText('Copy the Camera ID from Camera Management');
});

test('gateway creation shows gateway id and one-time token together', async ({ page }) => {
  await mockAdminShell(page);
  await mockGateways(page);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Gateways' }).click();
  await page.getByRole('button', { name: 'Register Gateway' }).click();
  await page.getByLabel('Gateway Name *').fill('edge-created');
  await page.getByRole('button', { name: 'Create Gateway' }).click();

  const credentialPanel = page.getByText('Gateway created - copy the service token now').locator('..');
  await expect(credentialPanel).toBeVisible();
  await expect(credentialPanel).toContainText('edge-created');
  await expect(credentialPanel).toContainText('44444444-4444-4444-8444-444444444444');
  await expect(credentialPanel).toContainText('one-time-service-token-value');
  await expect(page.getByRole('button', { name: 'Copy ID' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Copy Token' })).toBeVisible();

  const axe = await new AxeBuilder({ page }).include('body').analyze();
  expect(axe.violations.filter((violation) => violation.impact === 'critical')).toEqual([]);
});
