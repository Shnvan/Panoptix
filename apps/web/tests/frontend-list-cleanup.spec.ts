import { expect, test, type Page, type Route } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const jsonHeaders = { 'content-type': 'application/json' };

test.describe.configure({ mode: 'serial' });
test.setTimeout(60000);

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
      gateways: { total: 0, enabled: 0, disabled: 0 },
      users: { total: 0, active: 0, disabled: 0 },
      commands: { pending: 0 },
      publishing: { active: 0 },
    });
  });
  await page.route('**/health', async (route) => {
    await fulfillJson(route, { status: 'ok' });
  });
  await page.route('**/api/v1/admin/dsr-requests**', async (route) => {
    await fulfillJson(route, { items: [], next_cursor: null });
  });
  await page.route('**/api/v1/admin/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/v1/admin/dashboard') {
      await fulfillJson(route, {
        cameras: { total: 0, active: 0, retired: 0 },
        gateways: { total: 0, enabled: 0, disabled: 0 },
        users: { total: 0, active: 0, disabled: 0 },
        commands: { pending: 0 },
        publishing: { active: 0 },
      });
      return;
    }
    if (url.pathname.includes('/audit/export')) {
      await fulfillJson(route, { format: 'jsonl', manifest: {}, items: [] });
      return;
    }
    if (url.pathname.includes('/audit/verify')) {
      await fulfillJson(route, { valid: true, checked: 0, error: null });
      return;
    }
    await fulfillJson(route, { items: [], next_cursor: null });
  });
}

function alert(alert_id: string, title: string, message: string) {
  return {
    alert_id,
    severity: title.includes('Gateway') ? 'critical' : 'high',
    category: 'security',
    title,
    message,
    status: 'open',
    source: 'visitor.entry',
    source_event_id: null,
    resource: null,
    actor_type: null,
    actor_id: null,
    metadata: null,
    created_at: new Date().toISOString(),
    acknowledged_at: null,
    acknowledged_by: null,
    resolved_at: null,
    resolved_by: null,
  };
}

async function mockListPages(page: Page) {
  const now = Date.now();
  await page.route('**/api/v1/admin/alerts**', async (route) => {
    await fulfillJson(route, {
      items: [
        alert('alert-visitor', 'Visitor continued to secure sign-in', 'A visitor continued from the public entry notice toward secure sign-in.'),
        alert('alert-gateway', 'Gateway offline', 'A production gateway has not reported recently.'),
      ],
      next_cursor: null,
    });
  });
  await page.route('**/api/v1/admin/visitor-visits**', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          visit_id: 'visit-linked-111111111111',
          collected_at: new Date(now - 10 * 60 * 1000).toISOString(),
          page_path: '/entry',
          notice_version: '2026-06-01',
          user_agent: 'Playwright linked browser',
          login: {
            logged_in: true,
            user_id: 'user-linked-111111111111',
            session_id: 'session-linked-111111111111',
            logged_in_at: new Date(now - 9 * 60 * 1000).toISOString(),
            ip: '203.0.113.10',
          },
        },
        {
          visit_id: 'visit-anonymous-222222222222',
          collected_at: new Date(now - 8 * 24 * 60 * 60 * 1000).toISOString(),
          page_path: '/entry',
          notice_version: '2026-06-01',
          user_agent: 'Playwright anonymous browser',
          login: {
            logged_in: false,
            user_id: null,
            session_id: null,
            logged_in_at: null,
            ip: '203.0.113.20',
          },
        },
      ],
      next_cursor: null,
    });
  });
  await page.route('**/api/v1/admin/audit**', async (route) => {
    await fulfillJson(route, {
      items: [
        {
          id: 1,
          ts: '2026-06-05T12:00:00Z',
          actor_id: 'actor-11111111-2222-4333-8444-555555555555',
          actor_type: 'user',
          action: 'admin.access_request.approved',
          resource: 'visitor-access-request:resource-aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
          payload: null,
          ip: '203.0.113.55',
          ua: 'Playwright',
        },
      ],
      next_cursor: null,
    });
  });
}

test('alerts compact controls hide repeated visitor sign-in noise by default', async ({ page }) => {
  await mockAdminShell(page);
  await mockListPages(page);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Alerts' }).click();

  await expect(page.getByText('1 shown, 1 hidden')).toBeVisible();
  await expect(page.getByRole('main')).toContainText('Gateway offline');
  await expect(page.getByText('Visitor continued to secure sign-in')).toHaveCount(0);

  await page.getByLabel('Hide visitor sign-in noise').uncheck();
  await expect(page.getByRole('main')).toContainText('Visitor continued to secure sign-in');

  await page.getByRole('button', { name: 'comfortable' }).click();
  const axe = await new AxeBuilder({ page }).include('body').analyze();
  expect(axe.violations.filter((violation) => violation.impact === 'critical')).toEqual([]);
});

test('visitor visits filters loaded rows by search, login status, and time', async ({ page }) => {
  await mockAdminShell(page);
  await mockListPages(page);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Visitor Visits' }).click();

  await expect(page.getByRole('main')).toContainText('visit-li');
  await expect(page.getByRole('main')).toContainText('visit-an');

  await page.getByLabel('Visitor login filter').selectOption('linked');
  await expect(page.getByRole('main')).toContainText('visit-li');
  await expect(page.getByRole('main')).not.toContainText('visit-an');

  await page.getByLabel('Visitor login filter').selectOption('all');
  await page.getByLabel('Visitor time filter').selectOption('7d');
  await expect(page.getByRole('main')).toContainText('visit-li');
  await expect(page.getByRole('main')).not.toContainText('visit-an');

  await page.getByLabel('Visitor time filter').selectOption('all');
  await page.getByLabel('Search visitor visits').fill('203.0.113.20');
  await expect(page.getByRole('main')).toContainText('visit-an');
  await expect(page.getByRole('main')).not.toContainText('visit-li');
});

test('audit table shows full actor and resource identifiers with copy controls', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: async () => undefined,
      },
      configurable: true,
    });
  });
  await mockAdminShell(page);
  await mockListPages(page);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Audit Logs' }).click();

  await expect(page.getByText('actor-11111111-2222-4333-8444-555555555555')).toBeVisible();
  await expect(page.getByText('visitor-access-request:resource-aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee')).toBeVisible();

  await page.getByRole('button', { name: 'Copy actor ID' }).click();
  await expect(page.getByRole('status')).toContainText('actor ID copied to clipboard');
});
