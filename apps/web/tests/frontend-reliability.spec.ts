import { expect, test, type Page, type Route } from '@playwright/test';
import {
  nextPlaybackAttempt,
  playbackStateForRoomEvent,
  playbackStateForTrack,
} from '../src/app/components/cameraPlayback';

const jsonHeaders = { 'content-type': 'application/json' };

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, headers: jsonHeaders, body: JSON.stringify(body) });
}

async function mockShell(page: Page, cameras: Array<Record<string, unknown>> = []) {
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
      notice_version: '2026-06-06',
      title: 'Privacy notice',
      body: 'Privacy notice',
      accepted: true,
      accepted_at: '2026-06-06T00:00:00Z',
    });
  });
  await page.route('**/api/v1/cameras?*', async (route) => {
    await fulfillJson(route, { items: cameras, next_cursor: null });
  });
  await page.route('**/api/v1/admin/dashboard', async (route) => {
    await fulfillJson(route, {
      cameras: { total: cameras.length, active: cameras.length, retired: 0 },
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

test('gateway request failure is not shown as an empty gateway database', async ({ page }) => {
  await mockShell(page);
  let allowRecovery = false;
  await page.route('**/api/v1/admin/gateways?*', async (route) => {
    if (!allowRecovery) {
      await fulfillJson(route, { detail: 'temporary-gateway-load-failure' }, 503);
      return;
    }
    await fulfillJson(route, {
      items: [{
        gateway_id: '11111111-1111-4111-8111-111111111111',
        name: 'recovered-gateway',
        status: 'enabled',
        last_seen_at: null,
        created_at: '2026-06-06T00:00:00Z',
        disabled_at: null,
        camera_count: 0,
      }],
      next_cursor: null,
    });
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Gateways' }).click();

  await expect(page.getByRole('alert')).toContainText('Unable to load gateways');
  await expect(page.getByText('No Gateways Registered')).toHaveCount(0);
  allowRecovery = true;
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('recovered-gateway')).toBeVisible();
});

test('session request failure is not shown as no active sessions', async ({ page }) => {
  await mockShell(page);
  let attempts = 0;
  await page.route('**/api/v1/sessions/active', async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await fulfillJson(route, { detail: 'temporary-session-load-failure' }, 503);
      return;
    }
    await fulfillJson(route, {
      items: [{
        id: '22222222-2222-4222-8222-222222222222',
        created_at: '2026-06-06T00:00:00Z',
        last_seen_at: '2026-06-06T00:01:00Z',
        ua_fp: 'Playwright',
      }],
    });
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Settings' }).click();

  await expect(page.getByRole('alert')).toContainText('Unable to load session activity');
  await expect(page.getByText('No active sessions found')).toHaveCount(0);
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('22222222-222...')).toBeVisible();
});

test('camera modal reports viewer-token failure instead of an active stream', async ({ page }) => {
  await mockShell(page, [{
    camera_id: '33333333-3333-4333-8333-333333333333',
    display_name: 'Front gate viewer',
    livekit_room_name: 'front_gate',
    source_type: 'rtsp',
  }]);
  await page.route('**/api/v1/cameras/*/view-token', async (route) => {
    await fulfillJson(route, { detail: 'viewer-token-unavailable' }, 503);
  });

  await page.goto('/', { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Live Cameras' }).click();
  await page.getByText('Front gate viewer').click();
  await page.getByRole('button', { name: 'Establish Stream' }).click();

  await expect(page.getByText('CONNECTION ERROR').first()).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('viewer-token-unavailable');
  await expect(page.getByText('LIVE', { exact: true })).toHaveCount(0);
});

test('camera playback transitions require a current connection and a subscribed track', () => {
  const firstAttempt = nextPlaybackAttempt(0);
  const retryAttempt = nextPlaybackAttempt(firstAttempt);

  expect(playbackStateForRoomEvent(retryAttempt, firstAttempt, 'connection_error')).toBeNull();
  expect(playbackStateForRoomEvent(retryAttempt, retryAttempt, 'connection_error')).toBe('error');
  expect(playbackStateForRoomEvent(retryAttempt, retryAttempt, 'connected')).toBe('waiting_for_publisher');
  expect(playbackStateForRoomEvent(retryAttempt, retryAttempt, 'publisher_timeout')).toBe('offline');
  expect(playbackStateForTrack('waiting_for_publisher', true)).toBe('playing');
  expect(playbackStateForTrack('playing', false)).toBe('waiting_for_publisher');
});
