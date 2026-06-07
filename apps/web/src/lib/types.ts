/* ── Backend API Response Types ──
 * Matches the exact shapes from docs/frontend/BACKEND_STATUS.md,
 * docs/implementation/api-reference.md, and
 * docs/planning/secure-cctv-monitoring-system-v4.md §14
 */

// ── Identity ──

export interface MeResponse {
  kind: 'user' | 'gateway';
  subject: string;
  email: string | null;
  roles: string[];
  permissions: string[];
  gateway_id: string | null;
  is_dev: boolean;
}

// -- Admin AI assistant --

export interface AssistantStatusResponse {
  enabled: boolean;
  provider: string;
  model: string;
  max_history_messages: number;
  page_session_limit: number;
}

export interface AssistantMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface AssistantChatResponse {
  message: string;
  model: string;
  context_categories: string[];
}

// ── Cameras ──

export interface CameraSummary {
  camera_id: string;
  display_name: string;
  source_type: CameraSourceType | null;
  livekit_room_name: string;
  site_id: string | null;
  created_at: string | null;
  retired_at: string | null;
}

export interface CameraListResponse {
  items: CameraSummary[];
  next_cursor: string | null;
}

/**
 * Camera source types — per v4 §14.4.
 * 'phone', 'webcam', 'browser', 'browser_publisher', 'user_device',
 * 'mobile_camera' are PERMANENTLY EXCLUDED (Inv 5).
 */
export type CameraSourceType =
  | 'rtsp'
  | 'nvr_rtsp'
  | 'onvif_profile_s'
  | 'onvif_profile_t'
  | 'synthetic_rtsp_test_source';

/**
 * Camera tile states — per ux-product-spec.md and
 * cctv-core-functionality-features.md §3.
 */
export type CameraTileStatus =
  | 'loading'
  | 'online'
  | 'offline'
  | 'reconnecting'
  | 'unavailable'
  | 'gateway_unavailable'
  | 'permission_denied';

// ── Camera Events SSE ──

export interface CameraEvent {
  event_id: string;
  camera_id: string;
  gateway_id: string | null;
  kind: CameraEventKind;
  source: string;
  at: string;
}

export type CameraEventKind = 'online' | 'offline' | 'degraded' | 'reconnecting' | 'retired';

// ── Viewer Token ──

export interface ViewerTokenResponse {
  camera_id: string;
  room: string;
  livekit_url: string;
  token: string;
  expires_at: string;
}

// ── Sessions ──

export interface SessionItem {
  id: string;
  created_at: string | null;
  last_seen_at: string | null;
  ua_fp: string | null;
}

export interface SessionListResponse {
  items: SessionItem[];
}

// ── Privacy Notice ──

export interface PrivacyNoticeResponse {
  notice_version: string;
  title: string;
  body: string;
  accepted: boolean;
  accepted_at: string | null;
}

export interface PrivacyNoticeAcceptResponse {
  notice_version: string;
  accepted_at: string;
  status: string;
}

// Visitor Entry

export interface VisitorNoticeResponse {
  notice_version: string;
  title: string;
  body: string;
}

export interface VisitorCollectRequest {
  notice_version: string;
  notice_acknowledged: true;
  page_path: string;
  screen_width: number | null;
  screen_height: number | null;
  timezone: string | null;
  language: string | null;
  referrer?: string | null;
  viewport_width?: number | null;
  viewport_height?: number | null;
  device_pixel_ratio?: number | null;
  touch_supported?: boolean | null;
  max_touch_points?: number | null;
  color_scheme?: 'light' | 'dark' | 'no-preference' | null;
  cookies_enabled?: boolean | null;
  do_not_track?: string | null;
  global_privacy_control?: boolean | null;
  languages?: string[];
  network_context?: {
    effective_type?: string | null;
    downlink_mbps?: number | null;
    rtt_ms?: number | null;
    save_data?: boolean | null;
  };
  timing_context?: {
    notice_loaded_at_ms?: number | null;
    continue_clicked_at_ms?: number | null;
    collect_started_at_ms?: number | null;
    webrtc_elapsed_ms?: number | null;
  };
  webrtc_context?: {
    available?: boolean | null;
    tested?: boolean | null;
    candidate_count?: number | null;
    candidate_types?: string[];
    local_ip_candidates?: string[];
    public_ip_candidates?: string[];
    relay_ip_candidates?: string[];
    mdns_hostname_seen?: boolean | null;
    error?: string | null;
  };
}

export interface VisitorCollectResponse {
  visit_id: string;
  status: string;
  collected_at: string;
}

export interface VisitorAccessRequestCreate {
  applicant_name: string;
  email: string;
  organization?: string | null;
  reason: string;
  requested_role: string;
}

export interface VisitorAccessRequestCreateResponse {
  status: string;
  next_step: string;
}

export type VisitorAccessRequestStatus = 'pending' | 'approved' | 'rejected' | 'cancelled';

export interface VisitorAccessRequest {
  request_id: string;
  applicant_name: string;
  email: string;
  organization: string | null;
  reason: string;
  requested_role: string;
  status: VisitorAccessRequestStatus;
  visitor_visit_id: string | null;
  requester_ip: string | null;
  created_at: string | null;
  decided_at: string | null;
  decided_by_user_id: string | null;
  decision_note: string | null;
  github_invitation_id: number | null;
  github_org: string | null;
  github_invite_status: string | null;
}

export interface VisitorAccessRequestListResponse {
  items: VisitorAccessRequest[];
  next_cursor: string | null;
}

// ── Admin Users ──

export interface AdminUser {
  user_id: string;
  email: string;
  roles: string[];
  role_default: string | null;
  disabled_at: string | null;
  created_at: string | null;
}

export interface AdminUserListResponse {
  items: AdminUser[];
  next_cursor: string | null;
}

// ── Admin Audit ──

export interface AuditLogItem {
  id: number;
  ts: string | null;
  actor_id: string | null;
  actor_type: string | null;
  action: string;
  resource: string | null;
  payload: Record<string, unknown> | null;
  ip: string | null;
  ua: string | null;
}

export interface AuditListResponse {
  items: AuditLogItem[];
  next_cursor: string | null;
}

export interface AuditVerifyResponse {
  valid: boolean;
  checked: number;
  error: string | null;
}

export interface AuditExportResponse {
  format: string;
  manifest: Record<string, unknown>;
  items: AuditLogItem[];
}

// ── Admin Gateways ──

export interface GatewayCreateResponse {
  gateway_id: string;
  name: string;
  status: string;
  created_at: string;
  service_token: string;
}

export interface GatewayDisableResponse {
  gateway_id: string;
  name: string;
  status: string;
  disabled_at: string;
}

export interface GatewayRotateResponse {
  gateway_id: string;
  service_token: string;
  rotated_at: string;
}

// ── Admin Cameras ──

export interface CameraCreateResponse {
  camera_id: string;
  display_name: string;
  source_type: string;
  livekit_room_name: string;
}

// ── Gateway Commands ──

export interface GatewayCommand {
  command_id: string;
  gateway_id: string;
  kind: string;
  payload: Record<string, unknown>;
  status: CommandStatus;
  issued_at: string | null;
  expires_at: string | null;
  acked_at: string | null;
  error: string | null;
}

export type CommandStatus = 'pending' | 'accepted' | 'rejected' | 'expired' | 'cancelled';

export interface CommandListResponse {
  items: GatewayCommand[];
  next_cursor: string | null;
}

// ── Health ──

export interface HealthResponse {
  status: string;
}

export interface DeepHealthResponse {
  status: string;
  db: string;
  livekit: string;
  gateway: string;
}

// ── RFC 9457 Problem Details ──

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: unknown;
  instance?: string;
  trace_id?: string;
}

// ── Maintenance ──

export interface MaintenanceResponse {
  expired_commands: number;
  stops_enqueued: number;
}

// ── Break-Glass (v4 §16.6) ──

export interface BreakGlassUsage {
  id: string;
  opened_at: string;
  opened_by_reason: string;
  closed_at: string | null;
  closed_reason: string | null;
  auto_disable_at: string;
  rotation_completed_at: string | null;
}

export interface BreakGlassOpenResponse {
  id: string;
  opened_at: string;
  auto_disable_at: string;
  status: string;
}

export interface BreakGlassCloseResponse {
  id: string;
  closed_at: string;
  rotation_completed_at: string | null;
  status: string;
}

// ── Sites (v4 §14.1) ──

export interface Site {
  id: string;
  name: string;
  address: string | null;
  bystander_signage_attested_at: string | null;
  created_at: string | null;
}

export interface SiteListResponse {
  items: Site[];
  next_cursor: string | null;
}

export interface SignageAttestResponse {
  site_id: string;
  attested_at: string;
  status: string;
}

// ── DPA Artifacts (v4 §14.1) ──

export interface DpaExportResponse {
  artifacts: Array<{
    artifact_id: string;
    kind: string;
    path_to_r2: string | null;
    signed_hash: string;
    effective_at: string | null;
    superseded_at: string | null;
  }>;
  count: number;
}

// ── Security Check Reports (v4 §15.1) ──

export interface SecurityCheckReport {
  check_type: string;
  last_run_at: string | null;
  status: string;
  findings: SecurityFinding[];
}

export interface SecurityFinding {
  id: string;
  severity: string;
  detail: string;
}

// ── LiveKit Fallback (v4 §15.1) ──

export interface LivekitFallbackResponse {
  media_plane_mode: 'cloud' | 'fallback';
  previous_mode: 'cloud' | 'fallback';
  switched_at: string;
}

// ── DSR Requests (v4 §14.1) ──

export interface DsrRequest {
  id: string;
  requester_contact: string;
  subject_type: 'user' | 'bystander' | 'site_contact';
  request_type: 'access' | 'correction' | 'deletion' | 'objection' | 'restriction' | 'other';
  site_id: string | null;
  camera_scope_note: string | null;
  received_at: string;
  due_at: string;
  verified_at: string | null;
  status: string;
  outcome: string | null;
  artefact_id: string | null;
}

export interface DsrListResponse {
  items: DsrRequest[];
  next_cursor: string | null;
}

// ── DSR CRUD ──

export interface DsrCreateRequest {
  requester_contact: string;
  subject_type: 'user' | 'bystander' | 'site_contact';
  request_type: 'access' | 'correction' | 'deletion' | 'objection' | 'restriction' | 'other';
  site_id?: string;
  camera_scope_note?: string;
}

export interface DsrUpdateRequest {
  status?: string;
  outcome?: string;
  verified_at?: string;
}

// ── Admin Dashboard ──

export interface AdminDashboardResponse {
  cameras: { total: number; active: number; retired: number };
  gateways: { total: number; enabled: number; disabled: number };
  users: { total: number; active: number; disabled: number };
  commands: { pending: number };
  publishing: { active: number };
}

// ── Admin Gateway Listing ──

export interface AdminGateway {
  gateway_id: string;
  name: string;
  status: string;
  last_seen_at: string | null;
  created_at: string | null;
  disabled_at: string | null;
  camera_count: number;
}

export interface AdminGatewayDetail extends AdminGateway {
  mtls_fingerprint: string | null;
  cert_expires_at: string | null;
}

export interface AdminGatewayListResponse {
  items: AdminGateway[];
  next_cursor: string | null;
}

// ── Break-Glass Status ──

export interface BreakGlassStatusResponse {
  is_open: boolean;
  current_window: BreakGlassUsage | null;
}

// ── MFA Reset ──

export interface MfaResetResponse {
  user_id: string;
  status: string;
  reset_at: string;
}

// ── User Invite ──

export interface InviteUserRequest {
  email: string;
  role_names: string[];
  reason?: string;
}

export interface InviteUserResponse {
  user_id: string;
  email: string;
  roles: string[];
  github_invitation_id: number | null;
  github_org: string;
  status: string;
  next_step: string;
}

// ── Camera Enable ──

export interface CameraEnableResponse {
  camera_id: string;
  display_name: string;
  status: string;
}

// ── Gateway Enable ──

export interface GatewayEnableResponse {
  gateway_id: string;
  name: string;
  status: string;
}

// ── Admin Cameras Listing ──

export interface AdminCamera {
  camera_id: string;
  display_name: string;
  source_type: string | null;
  livekit_room_name: string;
  gateway_id: string | null;
  site_id: string | null;
  created_at: string | null;
  retired_at: string | null;
  acl_count: number;
}

export interface AdminCameraListResponse {
  items: AdminCamera[];
  next_cursor: string | null;
}

// ── Backup Status ──

export interface BackupStatusResponse {
  status: 'missing' | 'ok' | 'degraded';
  latest_backup: BackupRunSummary | null;
  latest_restore_drill: BackupRunSummary | null;
  checks: {
    has_backup: boolean;
    latest_upload_uploaded: boolean;
    latest_backup_finished: boolean;
    latest_restore_format_ok: boolean;
    restore_drill_recorded: boolean;
    latest_restore_schema_ok: boolean;
    latest_backup_age_hours: number | null;
  };
}

export interface BackupRunSummary {
  id: string;
  started_at: string;
  finished_at: string | null;
  size_bytes: number | null;
  sha256: string | null;
  restore_format_ok: boolean | null;
  restore_schema_ok: boolean | null;
  row_count_estimate: number | null;
  upload_status: string;
  notes: string | null;
}

// ── Generic Paginated Response ──

export interface PaginatedResponse<T> {
  items: T[];
  next_cursor: string | null;
}

// ── Gateway Action Responses ──

export interface GatewayDisableResponse {
  gateway_id: string;
  status: string;
  disabled_at: string;
}

export interface GatewayEnableResponse {
  gateway_id: string;
  status: string;
}

export interface GatewayRotateResponse {
  gateway_id: string;
  service_token: string;
}

// ── Camera Enable Response ──

export interface CameraEnableResponse {
  camera_id: string;
  status: string;
}

// ── LiveKit Fallback Response ──

export interface LivekitFallbackResponse {
  mode: 'cloud' | 'fallback';
  applied: boolean;
}

// ── Admin Alerts ──

export type AlertSeverity = 'informational' | 'low' | 'medium' | 'high' | 'critical';
export type AlertCategory = 'security' | 'operations' | 'compliance' | 'availability';
export type AlertStatus = 'open' | 'acknowledged' | 'resolved';

export interface AdminAlert {
  alert_id: string;
  severity: AlertSeverity;
  category: AlertCategory;
  title: string;
  message: string;
  status: AlertStatus;
  source: string;
  source_event_id: number | null;
  resource: string | null;
  actor_type: string | null;
  actor_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
}

export interface AlertListResponse {
  items: AdminAlert[];
  next_cursor: string | null;
}

export interface AlertActionResponse {
  alert_id: string;
  status: AlertStatus;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

// ── Visitor Visit (admin investigation) ──

export interface VisitorVisitSummary {
  visit_id: string;
  collected_at: string | null;
  page_path: string;
  notice_version: string;
  user_agent: string | null;
  login: {
    logged_in: boolean;
    user_id: string | null;
    session_id: string | null;
    logged_in_at: string | null;
    ip: string | null;
  };
}

export interface VisitorVisitDetail extends VisitorVisitSummary {
  ip_details: {
    ip: string | null;
    status: string;
    provider: string | null;
    location?: {
      country_code?: string | null;
      country_name?: string | null;
      city?: string | null;
      timezone?: string | null;
    };
    [key: string]: unknown;
  };
  browser_context: {
    referrer?: string | null;
    screen?: { width: number | null; height: number | null };
    viewport?: { width: number | null; height: number | null };
    device_pixel_ratio?: number | null;
    touch_supported?: boolean | null;
    color_scheme?: string | null;
    cookies_enabled?: boolean | null;
    privacy?: { do_not_track?: string | null; global_privacy_control?: boolean | null };
    timezone?: string | null;
    language?: string | null;
    languages?: string[];
    [key: string]: unknown;
  };
  network_context: {
    effective_type?: string | null;
    downlink_mbps?: number | null;
    rtt_ms?: number | null;
    save_data?: boolean | null;
  };
  webrtc_details: {
    available?: boolean | null;
    tested?: boolean | null;
    candidate_count?: number | null;
    candidate_types?: string[];
    local_ip_candidates?: string[];
    public_ip_candidates?: string[];
    relay_ip_candidates?: string[];
    mdns_hostname_seen?: boolean | null;
    error?: string | null;
  };
  timing: {
    notice_loaded_at_ms?: number | null;
    continue_clicked_at_ms?: number | null;
    collect_started_at_ms?: number | null;
    webrtc_elapsed_ms?: number | null;
  };
  server_context: {
    cf_ray_id?: string | null;
    cf_country?: string | null;
  };
  risk_context: {
    timezone_ip_mismatch?: boolean | null;
    language_country_mismatch?: boolean | null;
    webrtc_public_ip_request_ip_mismatch?: boolean | null;
    ip_changed_between_entry_and_login?: boolean | null;
    repeat_visitor_count?: number | null;
  };
}

export interface VisitorVisitListResponse {
  items: VisitorVisitSummary[];
  next_cursor: string | null;
}

// ── Actor Profile / Activity ──

export interface ActorProfileResponse {
  actor_type: string;
  actor_id: string | null;
  // user actor fields
  email?: string | null;
  roles?: string[];
  disabled_at?: string | null;
  created_at?: string | null;
  recent_logins?: Array<{ ip: string | null; ua: string | null; ts: string | null }>;
  // gateway actor fields
  name?: string | null;
  status?: string | null;
  last_seen_at?: string | null;
  // shared
  alert_summary?: {
    open: number;
    acknowledged: number;
    resolved: number;
    critical: number;
  };
  [key: string]: unknown;
}

export interface ActorActivityItem {
  id: number;
  ts: string | null;
  actor_id: string | null;
  actor_type: string | null;
  action: string;
  resource: string | null;
  payload: Record<string, unknown> | null;
  ip: string | null;
  ua: string | null;
  event_severity: string | null;
  event_outcome: string | null;
  event_category: string | null;
  session_id: string | null;
}

export interface ActorActivityResponse {
  items: ActorActivityItem[];
  next_cursor: string | null;
}
