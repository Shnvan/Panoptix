/* ── Panoptix API Client ──
 * All browser API calls are same-origin /api/v1/*.
 * Auth is session-cookie based — no tokens in localStorage.
 * CSRF token from panoptix_csrf cookie sent on mutations.
 * Dev-auth headers sent only when VITE_DEV_AUTH=true.
 */

import type { ProblemDetail } from './types';

function getCsrfToken(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)panoptix_csrf=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function getDevAuthHeaders(): Record<string, string> {
  if (import.meta.env.VITE_DEV_AUTH !== 'true') return {};
  const email = import.meta.env.VITE_DEV_EMAIL || 'admin@example.test';
  const roles = import.meta.env.VITE_DEV_ROLES || 'admin';
  return {
    'x-panoptix-dev-auth': '1',
    'x-panoptix-dev-email': email,
    'x-panoptix-dev-subject': email,
    'x-panoptix-dev-roles': roles,
  };
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public problem?: ProblemDetail,
  ) {
    super(`API Error ${status}: ${detail}`);
    this.name = 'ApiError';
  }
}

function normalizeProblemDetail(problem: ProblemDetail | undefined, fallback: string): string {
  const detail = problem?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return 'Request validation failed';
  if (detail && typeof detail === 'object') return 'Request validation failed';
  return fallback;
}

const CSRF_PATHS = [
  '/api/v1/admin/',
  '/api/v1/privacy/notice/accept',
  '/api/v1/sessions/revoke',
];

function needsCsrf(method: string, path: string): boolean {
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(method.toUpperCase())) return false;
  return CSRF_PATHS.some((p) => path.startsWith(p) || path === p);
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || 'GET').toUpperCase();
  const headers: Record<string, string> = {
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...getDevAuthHeaders(),
  };

  if (needsCsrf(method, path)) {
    const csrf = getCsrfToken();
    if (csrf) headers['x-panoptix-csrf-token'] = csrf;
  }

  const response = await fetch(path, {
    ...options, method,
    headers: { ...headers, ...(options.headers as Record<string, string>) },
    credentials: 'same-origin',
  });

  if (!response.ok) {
    let problem: ProblemDetail | undefined;
    try { problem = await response.json(); } catch { /* non-JSON */ }
    throw new ApiError(response.status, normalizeProblemDetail(problem, response.statusText), problem);
  }

  const ct = response.headers.get('content-type') || '';
  if (ct.includes('application/json')) return response.json() as Promise<T>;
  return response.text() as unknown as T;
}

// ── Public API ──

export const api = {
  // Identity
  getMe: () => apiFetch<import('./types').MeResponse>('/api/v1/me'),

  // Cameras
  listCameras: (cursor?: string, limit = 50) => {
    const p = new URLSearchParams();
    if (cursor) p.set('cursor', cursor);
    p.set('limit', String(limit));
    return apiFetch<import('./types').CameraListResponse>(`/api/v1/cameras?${p}`);
  },

  getCameraViewToken: (cameraId: string) =>
    apiFetch<import('./types').ViewerTokenResponse>(`/api/v1/cameras/${cameraId}/view-token`),

  subscribeCameraEvents: (since?: string): EventSource | null => {
    if (import.meta.env.VITE_DEV_AUTH === 'true') return null;
    const p = new URLSearchParams();
    if (since) p.set('since', since);
    return new EventSource(`/api/v1/cameras/events${p.toString() ? '?' + p : ''}`);
  },

  // Sessions
  getActiveSessions: () =>
    apiFetch<import('./types').SessionListResponse>('/api/v1/sessions/active'),

  revokeSession: (sessionId: string) =>
    apiFetch<{ revoked: boolean; session_id: string }>('/api/v1/sessions/revoke', {
      method: 'POST', body: JSON.stringify({ session_id: sessionId }),
    }),

  // Privacy
  getPrivacyNotice: () =>
    apiFetch<import('./types').PrivacyNoticeResponse>('/api/v1/privacy/notice'),

  acceptPrivacyNotice: (version: string) =>
    apiFetch<import('./types').PrivacyNoticeAcceptResponse>('/api/v1/privacy/notice/accept', {
      method: 'POST', body: JSON.stringify({ notice_version: version }),
    }),

  // ── Admin: Users ──
  listAdminUsers: (cursor?: string, limit = 50, email?: string) => {
    const p = new URLSearchParams();
    if (cursor) p.set('cursor', cursor);
    p.set('limit', String(limit));
    if (email) p.set('email', email);
    return apiFetch<import('./types').AdminUserListResponse>(`/api/v1/admin/users?${p}`);
  },

  updateUserRole: (userId: string, action: 'grant' | 'revoke', roleName: string) =>
    apiFetch<{ user_id: string; role_name: string; action: string; status: string }>(
      `/api/v1/admin/users/${userId}/role`,
      { method: 'POST', body: JSON.stringify({ action, role_name: roleName }) },
    ),

  disableUser: (userId: string, reason: string) =>
    apiFetch<{ user_id: string; disabled_at: string; sessions_revoked: number }>(
      `/api/v1/admin/users/${userId}/disable`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),

  // ── Admin: Cameras ──
  createCamera: (displayName: string, sourceType: string, livekitRoomName: string, siteId?: string) =>
    apiFetch<import('./types').CameraCreateResponse>('/api/v1/admin/cameras', {
      method: 'POST',
      body: JSON.stringify({ display_name: displayName, source_type: sourceType, livekit_room_name: livekitRoomName, site_id: siteId }),
    }),

  manageCameraAcl: (cameraId: string, action: 'grant' | 'revoke', userEmail: string) =>
    apiFetch<{ camera_id: string; user_email: string; action: string; status: string }>(
      `/api/v1/admin/cameras/${cameraId}/acl`,
      { method: 'POST', body: JSON.stringify({ action, user_email: userEmail }) },
    ),

  disableCamera: (cameraId: string, reason: string) =>
    apiFetch<{ camera_id: string; display_name: string; retired_at: string }>(
      `/api/v1/admin/cameras/${cameraId}/disable`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),

  // ── Admin: Gateways ──
  createGateway: (name: string, mtlsFingerprint?: string) =>
    apiFetch<import('./types').GatewayCreateResponse>('/api/v1/admin/gateways', {
      method: 'POST', body: JSON.stringify({ name, mtls_fingerprint: mtlsFingerprint }),
    }),

  disableGateway: (gatewayId: string, reason: string) =>
    apiFetch<import('./types').GatewayDisableResponse>(
      `/api/v1/admin/gateways/${gatewayId}/disable`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),

  rotateGatewayCredential: (gatewayId: string, reason: string) =>
    apiFetch<import('./types').GatewayRotateResponse>(
      `/api/v1/admin/gateways/${gatewayId}/rotate-credential`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),

  manageGatewayCameraAssignment: (gatewayId: string, action: 'grant' | 'revoke', cameraId: string) =>
    apiFetch<{ gateway_id: string; camera_id: string; action: string; status: string }>(
      `/api/v1/admin/gateways/${gatewayId}/cameras`,
      { method: 'POST', body: JSON.stringify({ action, camera_id: cameraId }) },
    ),

  // ── Admin: Gateway Commands ──
  listGatewayCommands: (gatewayId: string, cursor?: string, limit = 50, status?: string) => {
    const p = new URLSearchParams();
    if (cursor) p.set('cursor', cursor);
    p.set('limit', String(limit));
    if (status) p.set('status', status);
    return apiFetch<import('./types').CommandListResponse>(`/api/v1/admin/gateways/${gatewayId}/commands?${p}`);
  },

  enqueueGatewayCommand: (gatewayId: string, kind: string, payload?: Record<string, unknown>) =>
    apiFetch<{ command_id: string; gateway_id: string; kind: string; status: string; expires_at: string }>(
      `/api/v1/admin/gateways/${gatewayId}/commands`,
      { method: 'POST', body: JSON.stringify({ kind, payload }) },
    ),

  cancelGatewayCommand: (gatewayId: string, commandId: string) =>
    apiFetch<{ command_id: string; status: string; cancelled_at: string }>(
      `/api/v1/admin/gateways/${gatewayId}/commands/${commandId}/cancel`,
      { method: 'POST' },
    ),

  cleanupCommands: () =>
    apiFetch<{ expired_count: number }>('/api/v1/admin/commands/cleanup', { method: 'POST' }),

  runMaintenance: () =>
    apiFetch<import('./types').MaintenanceResponse>('/api/v1/admin/jobs/run-maintenance', { method: 'POST' }),

  // ── Admin: Audit ──
  listAudit: (cursor?: number, limit = 50, action?: string) => {
    const p = new URLSearchParams();
    if (cursor != null) p.set('cursor', String(cursor));
    p.set('limit', String(limit));
    if (action) p.set('action', action);
    return apiFetch<import('./types').AuditListResponse>(`/api/v1/admin/audit?${p}`);
  },

  verifyAuditChain: (startId?: number, endId?: number) => {
    const p = new URLSearchParams();
    if (startId != null) p.set('start_id', String(startId));
    if (endId != null) p.set('end_id', String(endId));
    return apiFetch<import('./types').AuditVerifyResponse>(`/api/v1/admin/audit/verify?${p}`);
  },

  exportAudit: (startId?: number, endId?: number) => {
    const p = new URLSearchParams();
    if (startId != null) p.set('start_id', String(startId));
    if (endId != null) p.set('end_id', String(endId));
    return apiFetch<import('./types').AuditExportResponse>(`/api/v1/admin/audit/export?${p}`);
  },

  // ── Admin: Break-Glass (v4 §16.6) ──
  openBreakGlass: (reason: string) =>
    apiFetch<import('./types').BreakGlassOpenResponse>('/api/v1/admin/break-glass/open', {
      method: 'POST', body: JSON.stringify({ reason }),
    }),

  closeBreakGlass: (reason: string) =>
    apiFetch<import('./types').BreakGlassCloseResponse>('/api/v1/admin/break-glass/close', {
      method: 'POST', body: JSON.stringify({ reason }),
    }),

  // ── Admin: Sites (v4 §14.1) ──
  listSites: () =>
    apiFetch<import('./types').SiteListResponse>('/api/v1/admin/sites'),

  attestSignage: (siteId: string) =>
    apiFetch<import('./types').SignageAttestResponse>(
      `/api/v1/admin/sites/${siteId}/signage-attest`,
      { method: 'POST' },
    ),

  // ── Admin: DPA Export (v4 §15.1) ──
  exportDpa: () =>
    apiFetch<import('./types').DpaExportResponse>('/api/v1/admin/dpa/export', {
      method: 'POST', body: JSON.stringify({}),
    }),

  // ── Admin: LiveKit Fallback (v4 §15.1) ──
  toggleLivekitFallback: (mode: 'cloud' | 'fallback') =>
    apiFetch<import('./types').LivekitFallbackResponse>('/api/v1/admin/livekit/fallback', {
      method: 'POST',
      body: JSON.stringify({ mode, reason: `Admin switched media plane to ${mode} from frontend` }),
    }),

  // ── Admin: Security Checks (v4 §15.1) ──
  getExposureCheck: () =>
    apiFetch<import('./types').SecurityCheckReport>('/api/v1/admin/exposure-check'),

  getMediaIsolationCheck: () =>
    apiFetch<import('./types').SecurityCheckReport>('/api/v1/admin/media-isolation-check'),

  getOriginBindingCheck: () =>
    apiFetch<import('./types').SecurityCheckReport>('/api/v1/admin/origin-binding-check'),

  // ── Admin: DSR Requests (v4 §14.1) ──
  listDsrRequests: () =>
    apiFetch<import('./types').DsrListResponse>('/api/v1/admin/dsr-requests'),

  // ── Health ──
  getHealth: () => apiFetch<import('./types').HealthResponse>('/health'),

  getDeepHealth: () =>
    apiFetch<import('./types').DeepHealthResponse>('/api/v1/admin/health/deep'),
};
