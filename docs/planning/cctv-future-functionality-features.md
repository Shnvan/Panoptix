# Panoptix — Future Functionality Idea Catalog

This document is an **idea catalog**, not an approved roadmap. Items listed here are possible future features that could be added to Panoptix beyond the current MVP described in `docs/planning/cctv-core-functionality-features.md`.

**No item in this document is approved for development** unless it is explicitly marked as **Pilot** (planned for the second phase) or has an accepted ADR authorizing implementation.

Before working on any idea from this catalog, check:

1. The guardrails in `docs/frontend/frontend-guardrails.md` and `docs/database/database-guardrails.md`.
2. The API contract in `docs/implementation/api-reference.md`.
3. The non-negotiable rules below.

---

## Non-Negotiable Rules for All Future Features

Every feature added to Panoptix must respect these constraints. No exceptions without a new ADR.

| Rule | Detail |
|---|---|
| No browser/phone/webcam publishing | Panoptix is a CCTV-only system. Browsers are viewers only. This is permanent. |
| No browser camera/microphone access | The app will never request `getUserMedia`, `MediaRecorder`, or `navigator.mediaDevices`. |
| No camera credentials in browser or API | RTSP URLs, camera passwords, and NVR credentials exist only on the gateway. |
| `cctv-api` remains security authority | All authorization, token minting, session management, and audit writes go through FastAPI. The frontend does not make security decisions. |
| Gateway remains outbound-only | Zero inbound WAN ports. The gateway initiates all connections to the control plane and LiveKit. |
| Recording/snapshots/playback require ADR | These features change the privacy and data-retention scope. They cannot be built without an explicit, accepted Architecture Decision Record. |
| No self-registration | All user accounts are created by admins through the identity provider. |
| No self-service MFA reset | MFA resets are admin-mediated only. |

---

## 1. Already-Mentioned Future Features

These items already appear in `docs/planning/cctv-core-functionality-features.md` or `docs/planning/secure-cctv-monitoring-system-v4.md`. They are listed here for completeness.

| Feature | Status | Notes |
|---|---|---|
| Viewer identity watermark on video | Pilot | CSS overlay for MVP deterrence; video-embedded watermark in pilot. |
| Alerting and notifications | Pilot | Backend alert records and SMTP email notification are implemented. Production sends high/critical alerts through Resend to active admin users. No Telegram, webhook, SMS, PagerDuty, Slack, or Teams integration in v1. |
| mTLS gateway certificates with rotation alerts | Pilot | Replaces service-token identity for stronger gateway auth. |
| NVR integration (`nvr_rtsp` source type) | Pilot | Extends camera source types beyond direct IP camera RTSP. |
| Suspicious login detection | Pilot | CF Access signals + app heuristics. |
| Audit tamper-check 5-minute cadence | Pilot | Periodic HMAC chain verification job. |
| Device posture enforcement (WARP) | Pilot | Admin device trust checks via Cloudflare. |
| Recording and playback | Future, ADR-gated | Requires explicit ADR, privacy impact assessment, and retention policy. |
| Snapshots | Future, ADR-gated | Same approval gate as recording. |
| Motion detection | Future | Requires backend processing or gateway-side detection. |
| Privacy masking | Future | Regions of video obscured for privacy compliance. |
| Multi-site management | Future | Dashboard and admin model for multiple physical locations. |
| Firmware inventory | Future | Track camera/NVR firmware versions for patching. |
| LiveKit fallback automatic failover | Future | Currently manual SuperAdmin switch; auto requires hysteresis logic. |

---

## 2. Viewer and Dashboard Ideas

Ideas to improve the daily experience for viewers watching cameras.

| Idea | Complexity | Who can prepare | Notes |
|---|---|---|---|
| Camera favorites | Low | Frontend + Database | User marks cameras as favorites; saved in DB; frontend shows favorites first. |
| Saved dashboard layouts | Low | Frontend + Database | User saves preferred grid arrangement; DB stores layout per user. |
| Camera search and filter | Low | Frontend | Filter camera list by name, status, site, or tag. |
| Camera grouping / tagging | Low | Frontend + Database | Admin assigns tags/groups to cameras; viewers filter by group. |
| Better fullscreen controls | Low | Frontend | Improved fullscreen toolbar with camera name overlay and quick-switch. |
| Picture-in-picture mode | Low | Frontend | Browser PiP API for watching a camera while navigating other tabs. |
| Stream quality selector | Medium | Frontend + Backend | Choose between main stream and sub-stream if camera supports multiple profiles. |
| Viewer activity indicator | Low | Frontend | Show how many viewers are watching a camera (count only, no identity). |
| Dark / light theme toggle | Low | Frontend | User preference for dashboard color scheme. |
| Camera timeline | High, ADR-gated | All | Requires recording feature first. Not available until recording ADR is accepted. |
| Keyboard shortcuts | Low | Frontend | Arrow keys to navigate grid, Escape to exit fullscreen, number keys for layout presets. |
| Auto-reconnect with status feedback | Low | Frontend | Better UX when a stream drops and reconnects automatically. |

---

## 3. Admin and Operator Ideas

Ideas to improve camera, user, and gateway management.

| Idea | Complexity | Who can prepare | Notes |
|---|---|---|---|
| Admin activity summary dashboard | Medium | Frontend + Backend | Overview of recent admin actions, user changes, camera additions. |
| Bulk user management | Medium | Frontend + Backend | Assign/revoke roles or camera access for multiple users at once. |
| Bulk camera management | Medium | Frontend + Backend | Enable/disable or reassign multiple cameras at once. |
| Camera maintenance notes | Low | Frontend + Database | Free-text notes per camera for maintenance history. |
| Camera maintenance calendar | Medium | Frontend + Database | Schedule and track maintenance windows per camera or gateway. |
| Gateway fleet overview with health history | Medium | Frontend + Backend + Database | Historical heartbeat/status data for each gateway over time. |
| Role refinements | Medium | Backend + Database | Site-scoped admin, read-only operator, or custom permission sets. |
| Admin approval workflows | Medium | Backend + Database | Require a second admin to approve sensitive changes like role grants or camera deletion. |
| Scheduled camera enable/disable | Medium | Backend + Database | Time-based rules to enable cameras during school hours and disable after. |
| User onboarding wizard | Low | Frontend | Step-by-step guide for new admins setting up their first cameras and users. |
| Audit report builder | Medium | Frontend + Backend | Custom filters, date ranges, and export presets for audit log reports. |
| Camera retirement archive | Low | Database | Soft-archive retired cameras with historical metadata preserved for audit. |
| Gateway decommission checklist | Low | Frontend + Backend | Guided steps for safely retiring a gateway and its assigned cameras. |

---

## 4. Security and Compliance Ideas

Ideas to strengthen security or simplify compliance workflows.

| Idea | Complexity | Who can prepare | Notes |
|---|---|---|---|
| Device posture scoring beyond WARP | Medium | Backend | Additional device trust signals beyond Cloudflare WARP posture. |
| Geo-restriction rules | Medium | Backend | Restrict login or viewing to specific countries or IP ranges. |
| Session anomaly detection | Medium | Backend | Flag sessions with unusual patterns (location change, rapid role switching). |
| Advanced break-glass audit dashboard | Medium | Frontend + Backend | Dedicated view for all break-glass events with timeline and action detail. |
| Automated compliance report generation | Medium | Backend | One-click generation of ROPA, PIA summary, and processor register exports. |
| Cross-site audit aggregation | High | Backend + Database | Unified audit view across multiple sites (requires multi-site first). |
| Certificate expiry alerting dashboard | Low | Frontend + Backend | Visual warnings for gateway mTLS certificates approaching expiry. |
| Login attempt rate visualization | Low | Frontend + Backend | Chart showing login attempt volume over time for anomaly spotting. |
| IP allowlist for admin actions | Medium | Backend | Restrict sensitive admin endpoints to specific trusted IP ranges. |
| Secret rotation dashboard | Medium | Frontend + Backend | Track rotation status of all secrets (gateway tokens, HMAC keys, API keys). |

### Actor Investigation Pilot Enhancements

The backend actor profile and activity APIs are implemented for current audit/session/camera/gateway data. Unsupported actor profile sections intentionally return `null` until pilot data sources, database models, and privacy/security review exist.

| Enhancement | Status | Notes |
|---|---|---|
| IP enrichment | Pilot | Add geolocation, IP reputation, VPN/Tor flags, and source-risk context for actor profiles. |
| Device details | Pilot | Add stronger browser/device fingerprinting or Cloudflare device signals beyond raw user-agent strings. |
| MFA details | Pilot | Ingest Cloudflare Access logs for MFA method, bypass, recovery, and denied MFA visibility. |
| Threat intelligence | Pilot | Enrich actor activity with approved threat feeds such as abuse.ch or an equivalent source. |
| Alerts and detections | Pilot | Initial backend rules create alert records for break-glass opened, invalid audit verification, admin role grants, gateway disable, rejected gateway commands, and degraded/missing backup status. Broader suspicious actor behavior still needs new data sources, models, and privacy/security review. |
| Incident tracking | Pilot | Add an incident model linked to actor profiles, audit rows, and containment actions. |
| Analyst notes | Pilot | Allow authorized admins/security analysts to attach notes to actor profiles and investigation timelines. |
| Behavior baseline | Pilot | Compute normal-vs-unusual actor behavior from historical audit/session/stream activity. |
| Persistence and defense-evasion indicators | Pilot | Derive indicators from audit events, service tokens, gateway credentials, break-glass usage, role changes, and policy changes. |

Not applicable for the CCTV pilot unless a future ADR changes scope: email collaboration activity, endpoint/EDR telemetry, broad network monitoring, cloud IAM activity, and business transaction activity.

---

## 5. Gateway and Camera Ideas

Ideas for improving gateway operations and camera management.

| Idea | Complexity | Who can prepare | Notes |
|---|---|---|---|
| Gateway auto-update mechanism | High | Backend + Gateway | Push or pull-based updates for gateway Docker image or config. |
| Gateway resource monitoring | Medium | Backend + Gateway | Report CPU, RAM, disk, and network usage from gateway to control plane. |
| Camera health scoring | Medium | Backend + Database | Composite score based on uptime, stream stability, and reconnect frequency. |
| ONVIF device discovery | Medium | Gateway | Automatically discover cameras on the camera VLAN using ONVIF. Requires hardware spike. |
| Gateway local network discovery | Medium/High | Gateway + Backend | Moved to the core functionality document as planned pilot scope. This broader device inventory is separate from ONVIF-only camera discovery and is not implemented yet. |
| Camera PTZ control | High | Frontend + Backend + Gateway | Pan/tilt/zoom control for supported cameras. Requires camera hardware support and new API endpoints. |
| Multi-stream quality profiles | Medium | Backend + Gateway | Gateway publishes main and sub-stream; viewer or backend selects quality. |
| Gateway-to-gateway failover | High | Backend + Database | Backup gateway takes over cameras if primary gateway goes offline. |
| Bandwidth usage tracking | Medium | Backend + Gateway + Database | Track and display bandwidth consumption per camera and per gateway. |
| Camera screenshot on demand | Medium, ADR-gated | All | Single frame capture from live stream. Same approval gate as snapshots. |
| Gateway diagnostic mode | Medium | Backend + Gateway | On-demand diagnostic report from gateway (connectivity, RTSP pull status, resource usage). |

Gateway local network discovery is tracked in the core functionality document as a planned gateway-only pilot. ONVIF device discovery remains the narrower camera-specific discovery item in this future catalog.

---

## 6. Incident and Operations Ideas

Ideas for operational workflows and incident response.

| Idea | Complexity | Who can prepare | Notes |
|---|---|---|---|
| Incident dashboard with timeline | Medium | Frontend + Backend + Database | Log and track incidents with timestamped events and resolution notes. |
| Escalation workflows | Medium | Backend | Define escalation chains for unacknowledged alerts using email-only v1; other channels require separate approval. |
| SLA tracking dashboard | Medium | Frontend + Backend | Track system uptime against defined service level targets. |
| Downtime calendar | Low | Frontend + Database | Visual calendar showing past and scheduled downtime windows. |
| Post-incident review templates | Low | Frontend + Database | Structured template for documenting incident root cause and remediation. |
| Alert routing rules | Medium | Backend | Route alerts based on time of day, camera group, severity, or on-call schedule. |
| On-call schedule management | Medium | Frontend + Backend + Database | Define and display who is on-call for incident response. |
| System health summary email | Low | Backend | Daily or weekly automated email summarizing system health, alerts, and actions. |

---

## 7. Analytics and Intelligence Ideas

All items in this section require **explicit approval** before any work begins. Many change the privacy scope.

| Idea | Complexity | Approval required | Notes |
|---|---|---|---|
| Viewing pattern heatmap | Medium | Yes | Show which cameras are watched most and when. No personal viewer data exposed. |
| Camera uptime analytics | Medium | No (metadata only) | Historical uptime/downtime charts per camera. |
| AI anomaly detection on feeds | Very high | Yes, ADR-gated | ML-based detection of unusual activity in video. Major privacy and compute implications. |
| Face blurring / privacy masking automation | Very high | Yes, ADR-gated | Automatic blurring of faces or regions. Requires edge or cloud processing. |
| People counting (non-identifying) | High | Yes, ADR-gated | Count people in frame without identifying individuals. Still has privacy implications. |
| Zone-based motion alerts | High | Yes | Define regions of interest in camera view; alert on motion in those zones. |
| Bandwidth forecasting | Medium | No (metadata only) | Predict bandwidth needs based on historical usage patterns. |
| Viewer engagement metrics | Low | Yes | Track how long viewers watch specific cameras. Privacy-sensitive. |

---

## 8. Mobile and UX Ideas

Ideas for improving the user experience on different devices.

| Idea | Complexity | Who can prepare | Notes |
|---|---|---|---|
| Progressive Web App (PWA) | Medium | Frontend | Offline dashboard shell, installable on mobile home screen. No native app. |
| Push notifications for alerts | Medium | Frontend + Backend | Browser push notifications for camera/gateway status changes or alerts. |
| Responsive improvements for tablets | Low | Frontend | Better grid layouts and touch targets for tablet-sized screens. |
| Floorplan / map view | Medium | Frontend + Database | Place cameras on a building floorplan or site map for spatial navigation. |
| Drag-and-drop dashboard layout editor | Medium | Frontend + Database | Rearrange camera tiles by dragging. Save layouts per user. |
| Accessibility improvements | Low | Frontend | Screen reader support, keyboard navigation, ARIA labels, high contrast mode. |
| Guided first-use tour | Low | Frontend | Interactive walkthrough for new users on first login after privacy notice. |
| Quick-action toolbar | Low | Frontend | Persistent toolbar with shortcuts to fullscreen, layout presets, and favorites. |
| Camera status toast notifications | Low | Frontend | In-app toast when a camera goes offline or comes back online while viewing. |

---

## 9. Permanently Not Supported

These features will **never** be part of Panoptix. This list is repeated from `docs/planning/cctv-core-functionality-features.md` for clarity.

| Feature | Reason |
|---|---|
| Webcam viewing or publishing | CCTV-only system. Only registered IP cameras are allowed. |
| Phone camera publishing | Same — no user device cameras. |
| Browser camera/microphone access | The app will never request these permissions. |
| Self-registration | All accounts are admin-created through the identity provider. |
| Self-service MFA reset | MFA resets must go through an admin to prevent social engineering. |
| Public camera URLs | All camera access requires authentication and authorization. |
| Direct database access from frontend | All data access goes through `cctv-api`. |
| Direct gateway control from browser | All gateway commands go through `cctv-api` over the outbound WebSocket channel. |

---

## 10. How to Propose a New Feature

Before building any feature from this catalog or proposing a new one:

1. **Check guardrails**: Read `docs/frontend/frontend-guardrails.md` and `docs/database/database-guardrails.md`. Does the feature violate any rule?
2. **Check API impact**: Does this feature need new API endpoints? Document them in `docs/implementation/api-reference.md` format first.
3. **Check database impact**: Does this need new tables, columns, or migrations? Coordinate with the database owner and system owner.
4. **Check security impact**: Does this feature touch auth, tokens, audit, gateway identity, or camera credentials? System owner must review.
5. **Check privacy impact**: Does this feature collect, store, process, or display personal data or video data in a new way? If yes, it may need a privacy review.
6. **ADR required?**: If the feature changes the product scope (e.g., adds recording, analytics, new camera types, new publishing paths), write an ADR in `docs/adrs/` before implementation.
7. **Team coordination**: Notify all three team members before starting. Use the RACI model in `docs/implementation/team-raci-checklist.md`.

---

## References

- [Core Functionality and Features](cctv-core-functionality-features.md) — current MVP features
- [Frontend Guardrails](../frontend/frontend-guardrails.md) — what frontend must not do
- [Database Guardrails](../database/database-guardrails.md) — what database must not do
- [API Reference](../implementation/api-reference.md) — current API contract
- [Team RACI](../implementation/team-raci-checklist.md) — team ownership model
- [Main System Plan](secure-cctv-monitoring-system-v4.md) — full technical plan
