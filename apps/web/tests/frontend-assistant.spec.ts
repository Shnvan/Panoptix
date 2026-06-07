import { expect, test, type Page, type Route } from '@playwright/test';

const jsonHeaders = { 'content-type': 'application/json' };

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, headers: jsonHeaders, body: JSON.stringify(body) });
}

async function mockShell(page: Page, roles = ['admin']) {
  await page.route('**/api/v1/me', (route) => fulfillJson(route, {
    kind: 'user',
    subject: 'assistant-user',
    email: 'assistant@example.test',
    roles,
    permissions: [],
    gateway_id: null,
    is_dev: true,
  }));
  await page.route('**/api/v1/privacy/notice', (route) => fulfillJson(route, {
    notice_version: '2026-06-07',
    title: 'Privacy notice',
    body: 'Privacy notice',
    accepted: true,
    accepted_at: '2026-06-07T00:00:00Z',
  }));
  await page.route('**/api/v1/cameras?*', (route) => fulfillJson(route, {
    items: [],
    next_cursor: null,
  }));
  await page.route('**/api/v1/admin/dashboard', (route) => fulfillJson(route, {
    cameras: { total: 0, active: 0, retired: 0 },
    gateways: { total: 0, enabled: 0, disabled: 0 },
    users: { total: 0, active: 0, disabled: 0 },
    commands: { pending: 0 },
    publishing: { active: 0 },
  }));
  await page.route('**/health', (route) => fulfillJson(route, { status: 'ok' }));
}

test('admin assistant requires disclosure and sends bounded chat', async ({ page }) => {
  await mockShell(page);
  await page.route('**/api/v1/admin/assistant/status', (route) => fulfillJson(route, {
    enabled: true,
    provider: 'openai-compatible',
    model: 'llama-3.3-70b-versatile',
    max_history_messages: 20,
    page_session_limit: 50,
  }));
  let captured: Record<string, unknown> | null = null;
  await page.route('**/api/v1/admin/assistant/chat', async (route) => {
    captured = JSON.parse(route.request().postData() || '{}');
    await fulfillJson(route, {
      message: '**Gateway status:** connected\n- No stale heartbeats detected.',
      model: 'llama-3.3-70b-versatile',
      context_categories: ['health', 'gateways', 'cameras', 'alerts', 'backups'],
    });
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Open Panoptix operations assistant' }).click();
  await expect(page.getByText('Before you continue')).toBeVisible();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('button', { name: 'Are any gateway heartbeats stale?' }).click();

  await expect(page.getByText('Gateway status:')).toBeVisible();
  await expect(page.getByText('No stale heartbeats detected.')).toBeVisible();
  expect(captured).toEqual({
    messages: [{ role: 'user', content: 'Are any gateway heartbeats stale?' }],
  });
  await expect(page.getByText('49/50 page-session requests')).toBeVisible();
});

test('assistant is absent for viewers', async ({ page }) => {
  await mockShell(page, ['viewer']);
  let statusCalls = 0;
  await page.route('**/api/v1/admin/assistant/status', async (route) => {
    statusCalls += 1;
    await fulfillJson(route, { enabled: true });
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('button', { name: 'Open Panoptix operations assistant' })).toHaveCount(0);
  expect(statusCalls).toBe(0);
});

test('assistant shows sanitized retryable provider failure on mobile', async ({ page }) => {
  await mockShell(page);
  await page.route('**/api/v1/admin/assistant/status', (route) => fulfillJson(route, {
    enabled: true,
    provider: 'openai-compatible',
    model: 'llama-3.3-70b-versatile',
    max_history_messages: 20,
    page_session_limit: 50,
  }));
  await page.route('**/api/v1/admin/assistant/chat', (route) => fulfillJson(route, {
    type: 'https://panoptix.local/problems/bad-gateway',
    title: 'Bad Gateway',
    status: 502,
    detail: 'assistant-provider-unavailable',
  }, 502));

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Open Panoptix operations assistant' }).click();
  await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByLabel('Message Panoptix operations assistant').fill('System status');
  await page.getByRole('button', { name: 'Send assistant message' }).click();

  await expect(page.getByRole('alert')).toContainText('provider is currently unavailable');
  await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Panoptix operations assistant' })).toBeVisible();
});
