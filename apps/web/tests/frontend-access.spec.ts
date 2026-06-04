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

async function gotoApp(page: Page, path: string) {
  await page.goto(path, { waitUntil: 'domcontentloaded' });
}

async function mockEntryNotice(page: Page) {
  await page.route('**/api/v1/visitor/notice', async (route) => {
    await fulfillJson(route, {
      notice_version: '2026-06-01',
      title: 'Panoptix Visitor Security Notice',
      body: 'Public entry notice for access security.',
    });
  });
}

async function mockAdminShell(
  page: Page,
  pendingRequests: Array<Record<string, unknown>>,
  options: {
    users?: Array<Record<string, unknown>>;
    moreUsers?: Array<Record<string, unknown>>;
    usersNextCursor?: string | null;
    morePendingRequests?: Array<Record<string, unknown>>;
    accessRequestsNextCursor?: string | null;
  } = {},
) {
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
  await page.route('**/api/v1/admin/users**', async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get('cursor') === options.usersNextCursor) {
      await fulfillJson(route, { items: options.moreUsers || [], next_cursor: null });
      return;
    }
    await fulfillJson(route, { items: options.users || [], next_cursor: options.usersNextCursor || null });
  });
  await page.route('**/api/v1/admin/access-requests**', async (route) => {
    if (route.request().method() !== 'GET') {
      await route.fallback();
      return;
    }
    const url = new URL(route.request().url());
    if (url.searchParams.get('cursor') === options.accessRequestsNextCursor) {
      await fulfillJson(route, { items: options.morePendingRequests || [], next_cursor: null });
      return;
    }
    await fulfillJson(route, { items: pendingRequests, next_cursor: options.accessRequestsNextCursor || null });
  });
}

function pendingRequest(index = 1) {
  return {
    request_id: `11111111-1111-4111-8111-${String(index).padStart(12, '0')}`,
    applicant_name: index === 1 ? 'Mara Santos' : `Applicant ${index}`,
    email: index === 1 ? 'mara@example.test' : `applicant-${index}@example.test`,
    organization: index === 1 ? 'Security Team' : `Team ${index}`,
    reason: 'Needs access for monitoring rotation.',
    requested_role: 'viewer',
    status: 'pending',
    visitor_visit_id: '22222222-2222-4222-8222-222222222222',
    requester_ip: null,
    created_at: '2026-06-01T00:00:00Z',
    decided_at: null,
    decided_by_user_id: null,
    decision_note: null,
    github_invitation_id: null,
    github_org: null,
    github_invite_status: null,
  };
}

function adminUser(index: number) {
  return {
    user_id: `22222222-2222-4222-8222-${String(index).padStart(12, '0')}`,
    email: `operator-${index}@example.test`,
    roles: ['viewer'],
    role_default: 'viewer',
    disabled_at: null,
    created_at: '2026-06-01T00:00:00Z',
  };
}

test('public entry access request validates fields and shows success', async ({ page }) => {
  await mockEntryNotice(page);
  await page.route('**/api/v1/visitor/access-requests', async (route) => {
    const body = route.request().postDataJSON();
    expect(body).toMatchObject({
      applicant_name: 'Mara Santos',
      email: 'mara@example.test',
      organization: 'Security Team',
      reason: 'Need SOC viewer access.',
      requested_role: 'viewer',
    });
    await fulfillJson(route, {
      status: 'received',
      next_step: 'If this request can be reviewed, an administrator will process it.',
    }, 202);
  });

  await gotoApp(page, '/entry');
  await page.getByRole('button', { name: 'Submit access request' }).click();
  await expect(page.getByRole('alert')).toContainText('Check the highlighted fields');

  await page.getByLabel('Full name').fill('Mara Santos');
  await page.getByLabel('Email address').fill('mara@example.test');
  await page.getByLabel('Organization or team').fill('Security Team');
  await page.getByLabel('Reason for access').fill('Need SOC viewer access.');
  await page.getByRole('button', { name: 'Submit access request' }).click();

  await expect(page.getByRole('status')).toContainText('If this request can be reviewed');
});

test('public entry access request shows generic duplicate success and rate-limit error', async ({ page }) => {
  await mockEntryNotice(page);
  let response: 'duplicate' | 'rate-limit' = 'duplicate';
  await page.route('**/api/v1/visitor/access-requests', async (route) => {
    if (response === 'duplicate') {
      await fulfillJson(route, {
        status: 'received',
        next_step: 'If this request can be reviewed, an administrator will process it.',
      }, 202);
      return;
    }
    await fulfillJson(route, {
      type: 'https://panoptix.local/problems/error',
      title: 'Error',
      status: 429,
      detail: 'access-request-rate-limited',
    }, 429);
  });

  await gotoApp(page, '/entry');
  await page.getByLabel('Full name').fill('Mara Santos');
  await page.getByLabel('Email address').fill('mara@example.test');
  await page.getByLabel('Reason for access').fill('Need SOC viewer access.');
  await page.getByRole('button', { name: 'Submit access request' }).click();
  await expect(page.getByRole('status')).toContainText('If this request can be reviewed');

  response = 'rate-limit';
  await page.getByLabel('Full name').fill('Mara Santos');
  await page.getByLabel('Email address').fill('mara@example.test');
  await page.getByLabel('Reason for access').fill('Need SOC viewer access.');
  await page.getByRole('button', { name: 'Submit access request' }).click();
  await expect(page.getByRole('alert')).toContainText('Too many access requests');
});

test('admin access request approval uses accessible dialog and refreshes pending list', async ({ page }) => {
  const requests = [pendingRequest()];
  await mockAdminShell(page, requests);
  await page.route('**/api/v1/admin/access-requests/*/approve', async (route) => {
    requests.length = 0;
    await fulfillJson(route, { ...pendingRequest(), status: 'approved', decided_at: '2026-06-01T00:01:00Z' });
  });

  await gotoApp(page, '/');
  await page.getByRole('button', { name: 'Users & Access' }).click();
  await expect(page.getByText('mara@example.test')).toBeVisible();
  await page.getByRole('button', { name: 'Approve' }).click();

  const dialog = page.getByRole('dialog', { name: 'Approve Access Request' });
  await expect(dialog).toBeVisible();
  const axe = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
  expect(axe.violations.filter((violation) => violation.impact === 'critical')).toEqual([]);

  await page.getByRole('button', { name: 'Approve and Invite' }).click();
  await expect(page.getByRole('status')).toContainText('Approved mara@example.test');
  await expect(page.getByRole('tab', { name: 'Access Requests (0)' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('main')).toContainText('No pending access requests');
});

test('admin access request rejection requires a reason and handles disabled-user approval', async ({ page }) => {
  const requests = [pendingRequest()];
  await mockAdminShell(page, requests);
  await page.route('**/api/v1/admin/access-requests/*/reject', async (route) => {
    requests.length = 0;
    await fulfillJson(route, { ...pendingRequest(), status: 'rejected', decided_at: '2026-06-01T00:01:00Z' });
  });
  await page.route('**/api/v1/admin/access-requests/*/approve', async (route) => {
    await fulfillJson(route, {
      type: 'https://panoptix.local/problems/conflict',
      title: 'Conflict',
      status: 409,
      detail: 'user-disabled',
    }, 409);
  });

  await gotoApp(page, '/');
  await page.getByRole('button', { name: 'Users & Access' }).click();

  await page.getByRole('button', { name: 'Reject' }).click();
  await page.getByLabel('Rejection reason *').fill('');
  await page.getByRole('button', { name: 'Reject Request' }).click();
  await expect(page.getByRole('alert')).toContainText('Enter a rejection reason');
  await page.getByLabel('Rejection reason *').fill('Not approved for this rollout.');
  await page.getByRole('button', { name: 'Reject Request' }).click();
  await expect(page.getByRole('status')).toContainText('Rejected access request');
  await expect(page.getByRole('tab', { name: 'Access Requests (0)' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('main')).toContainText('No pending access requests');

  requests.push(pendingRequest());
  await expect(page.getByRole('button', { name: 'Refresh' })).toBeEnabled();
  await page.getByRole('button', { name: 'Refresh' }).click();
  await page.getByRole('button', { name: 'Approve' }).click();
  await page.getByRole('button', { name: 'Approve and Invite' }).click();
  await expect(page.getByRole('dialog', { name: 'Approve Access Request' }).getByRole('alert')).toContainText('disabled Panoptix account');
});

test('admin users and access tabs prevent request flood and paginate lists', async ({ page }) => {
  const requests = Array.from({ length: 8 }, (_, index) => pendingRequest(index + 1));
  await mockAdminShell(page, requests, {
    users: [adminUser(1)],
    moreUsers: [adminUser(2)],
    usersNextCursor: 'users-page-2',
    morePendingRequests: [pendingRequest(9)],
    accessRequestsNextCursor: 'requests-page-2',
  });

  await gotoApp(page, '/');
  await page.getByRole('button', { name: 'Users & Access' }).click();

  await expect(page.getByRole('tab', { name: /Access Requests \(8\+\)/ })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText('applicant-8@example.test')).toBeVisible();

  await page.getByRole('tab', { name: 'Users' }).click();
  await expect(page.getByText('operator-1@example.test')).toBeVisible();
  await expect(page.getByText('applicant-8@example.test')).toHaveCount(0);
  await page.getByRole('button', { name: 'Load more users' }).click();
  await expect(page.getByText('operator-2@example.test')).toBeVisible();

  await page.getByRole('tab', { name: /Access Requests/ }).click();
  await page.getByRole('button', { name: 'Load more access requests' }).click();
  await expect(page.getByText('applicant-9@example.test')).toBeVisible();
});
