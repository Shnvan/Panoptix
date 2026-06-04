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
      cameras: { total: 2, active: 1, retired: 1 },
      gateways: { total: 0, enabled: 0, disabled: 0 },
      users: { total: 0, active: 0, disabled: 0 },
      commands: { pending: 0 },
      publishing: { active: 0 },
    });
  });
  await page.route('**/health', async (route) => {
    await fulfillJson(route, { status: 'ok' });
  });
}

function camera(
  id: string,
  displayName: string,
  room: string,
  sourceType: string,
  retired = false,
) {
  return {
    camera_id: id,
    display_name: displayName,
    source_type: sourceType,
    livekit_room_name: room,
    gateway_id: null,
    site_id: null,
    created_at: '2026-06-01T00:00:00Z',
    retired_at: retired ? '2026-06-02T00:00:00Z' : null,
    acl_count: 0,
  };
}

async function mockAdminCameras(page: Page) {
  const firstPage = [
    camera('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'front gate', 'front_gate_room', 'rtsp'),
    camera('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'retired lobby', 'lobby_room', 'nvr_rtsp', true),
  ];
  const secondPage = [
    camera('cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'garage test', 'garage_room', 'synthetic_rtsp_test_source'),
  ];

  await page.route('**/api/v1/admin/cameras**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname !== '/api/v1/admin/cameras') {
      await route.fallback();
      return;
    }
    if (request.method() === 'POST') {
      firstPage.unshift(camera('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'new camera', 'new_camera_room', 'rtsp'));
      await fulfillJson(route, {
        camera_id: 'dddddddd-dddd-4ddd-8ddd-dddddddddddd',
        display_name: 'new camera',
        source_type: 'rtsp',
        livekit_room_name: 'new_camera_room',
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

test('camera management exposes full camera ids, filters, and load more', async ({ page }) => {
  await mockAdminShell(page);
  await mockAdminCameras(page);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Camera Management' }).click();

  await expect(page.getByText('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa')).toBeVisible();
  await expect(page.getByText('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Copy' }).first()).toBeVisible();

  await page.getByLabel('Search cameras by name, room, or ID').fill('bbbbbbbb');
  await expect(page.getByText('retired lobby')).toBeVisible();
  await expect(page.getByText('front gate')).toHaveCount(0);

  await page.getByLabel('Search cameras by name, room, or ID').fill('');
  await page.getByLabel('Camera status filter').selectOption('active');
  await expect(page.getByText('front gate')).toBeVisible();
  await expect(page.getByText('retired lobby')).toHaveCount(0);

  await page.getByLabel('Camera status filter').selectOption('all');
  await page.getByLabel('Camera source type filter').selectOption('nvr_rtsp');
  await expect(page.getByText('retired lobby')).toBeVisible();
  await expect(page.getByText('front gate')).toHaveCount(0);

  await page.getByLabel('Camera source type filter').selectOption('all');
  await page.getByRole('button', { name: 'Load more cameras' }).click();
  await expect(page.getByText('cccccccc-cccc-4ccc-8ccc-cccccccccccc')).toBeVisible();
});

test('camera registration shows created camera id and room', async ({ page }) => {
  await mockAdminShell(page);
  await mockAdminCameras(page);

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Camera Management' }).click();
  await page.getByRole('button', { name: 'Register Camera' }).click();
  await page.getByLabel('Display Name *').fill('new camera');
  await page.getByLabel('LiveKit Room Name *').fill('new_camera_room');
  await page.getByRole('button', { name: 'Create Camera' }).click();

  const successPanel = page.getByText('Camera registered').locator('..');
  await expect(successPanel).toBeVisible();
  await expect(successPanel).toContainText('new camera');
  await expect(successPanel).toContainText('new_camera_room');
  await expect(successPanel).toContainText('dddddddd-dddd-4ddd-8ddd-dddddddddddd');
  await expect(page.getByRole('button', { name: 'Copy ID' })).toBeVisible();

  const axe = await new AxeBuilder({ page }).include('body').analyze();
  expect(axe.violations.filter((violation) => violation.impact === 'critical')).toEqual([]);
});
