# ADR 0001 â€” Control-Plane / Media-Plane / Camera-Plane Separation

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: Software Architect, System Owner
- **Supersedes**: None
- **Amended by**: ADR 0014 â€” Railway + Python Control Plane
- **Plan references**: Invariants 1, 3, 4; Â§10.1â€“10.4; Â§12 stack table; Â§16.10; Â§20.13

## Context

The system is a live-view CCTV monitoring application that connects IP cameras (via edge gateways) to authenticated browser viewers through a WebRTC SFU. This combines three fundamentally different traffic types:

1. **Control-plane traffic** â€” HTTP: authentication, authorization, token minting, audit, admin operations, DB access.
2. **Media-plane traffic** â€” WebRTC (UDP/TCP): real-time video from cameras to viewers via an SFU (LiveKit).
3. **Camera-plane traffic** â€” RTSP: on-site camera streams ingested by edge gateways on a local or VLAN-isolated network.

Running all three through a single network path, a single process, or a shared secret/credential store creates compounding risk:

- A compromise of the media plane (which has public-facing UDP ports) could pivot to DB credentials, session cookies, or audit keys.
- A compromise of the camera plane (on-site RTSP credentials, gateway secrets) could reach the control plane if they share a process or secrets store.
- Cloudflare Tunnel is HTTP-only and cannot carry WebRTC media efficiently; attempting to route media through it degrades latency and violates the Tunnel's design assumptions.

## Decision

**The system is architected as three isolated planes: control, media, and camera. Each plane has its own compute, its own secret store, and its own trust boundary. No plane can pivot to another without an explicit, authenticated, audited cross-plane API call.**

### Control plane

- **Compute**: `cctv-api` on Railway as a Python/FastAPI service.
- **Network**: supported user entry point is Cloudflare Access in front of the Railway custom domain. Protected routes fail closed without a valid Cloudflare Access JWT. Origin-binding enforced (Inv 14, ADR 0010).
- **Secrets**: Railway/control-plane secrets scoped to `cctv-api` only â€” DB URL, audit HMAC keys, LiveKit API key/secret, cookie signing key.
- **DB access**: only the control plane connects to Postgres. No other plane has a DB connection string.
- **Outbound**: issues viewer-subscribe and gateway-publish tokens to LiveKit; calls LiveKit room API to terminate participants on user/gateway disable.

### Media plane

- **Compute (primary)**: LiveKit Cloud (APAC region). Fully managed SFU.
- **Compute (fallback)**: self-hosted LiveKit fallback on DigitalOcean Singapore or equivalent UDP-capable APAC host. Only LiveKit media ports exposed; no HTTP app/admin endpoints, no DB access.
- **Secrets**: LiveKit API key/secret on the managed instance; separate media-plane secret store on the fallback instance. **No DB URL, no audit HMAC key, no cookie signing key.**
- **Trust boundary**: accepts connections from gateways (publisher tokens) and browsers (subscriber tokens). Tokens are short-lived (â‰¤60 s), kind-distinct, and minted exclusively by the control plane.
- **Cross-plane communication**: LiveKit fires webhooks (HMAC-signed + replay-protected) to the control plane at `POST /api/v1/webhooks/livekit`. This is the only inbound path from media to control.

### Camera plane

- **Compute**: on-site NUC-class mini-PC (production) or selected dev/CI synthetic gateway host. Runs `mediamtx` + gateway-agent.
- **Network**: on a camera VLAN, firewalled from the corporate/school LAN. Only outbound HTTPS (to control plane for heartbeat/token-mint) and outbound UDP/TCP (to LiveKit for publishing).
- **Secrets**: camera RTSP credentials stored only on the gateway, in `/etc/cctv-gateway/gateway.env` (mode 0600). Gateway's own service-token (MVP) or mTLS leaf cert (pilot+) for authenticating to the control plane. **No DB URL, no audit HMAC key, no viewer session cookies.**
- **Trust boundary**: gateway authenticates to the control plane via service-token or mTLS. Control plane validates identity, checks `gateway_camera_assignments`, and mints a gateway-publish token. Gateway publishes to LiveKit with that token. **Camera credentials never leave the gateway.**

### Cross-plane interfaces (exhaustive)

| From | To | Mechanism | Auth | Direction |
|---|---|---|---|---|
| Control â†’ Media | Token mint (viewer-subscribe, gateway-publish) | LiveKit Server SDK | LiveKit API key/secret | Outbound from control |
| Control â†’ Media | Room API (terminate participant) | LiveKit Server SDK | LiveKit API key/secret | Outbound from control |
| Media â†’ Control | Webhook (`participant_joined`, `participant_left`, `room_finished`) | HTTPS POST | HMAC-signed + 60-s timestamp | Inbound to control |
| Camera â†’ Control | Heartbeat, token-mint, camera-status | HTTPS (via CF Access service-token route) | Service-token (MVP) / mTLS (pilot+) | Outbound from camera |
| Camera â†’ Media | WebRTC publish | LiveKit SDK | Gateway-publish token (â‰¤60 s) | Outbound from camera |
| Browser â†’ Control | All app HTTP (auth, view-token, admin, audit) | HTTPS (via CF Access â†’ Railway) | CF JWT + session cookie | Inbound to control |
| Browser â†’ Media | WebRTC subscribe | LiveKit SDK | Viewer-subscribe token (â‰¤60 s) | Direct to media |

No other cross-plane paths exist. Any new cross-plane path requires an update to this ADR and a threat-model review.

## Consequences

### Positive

- **Blast-radius containment**: compromising one plane does not yield credentials, DB access, or audit-tampering ability in another.
- **Independent scaling**: media plane can scale viewer capacity (LiveKit Cloud) without touching control-plane compute.
- **Independent provider-exit**: each plane can be migrated to a different provider independently (Â§20.13). CF can be replaced without touching LiveKit; LiveKit can be replaced without touching CF or Postgres.
- **Audit integrity**: the audit HMAC key never leaves the control plane; even a fully compromised media or camera plane cannot forge audit entries.
- **Camera credential isolation**: RTSP credentials are confined to the camera plane; a compromised control plane cannot extract them (it never has them).

### Negative

- **Operational complexity**: separate control, media, and camera-plane services/hosts, separate secret stores, and separate deploy/lifecycle paths.
- **Latency for cross-plane calls**: webhook delivery from LiveKit to the control plane adds a network hop (mitigated by LiveKit's <1 s webhook SLA).
- **Token-refresh overhead**: 60-second token TTL means both viewers and gateways must refresh tokens frequently, adding load to the control plane's token-mint endpoint.

### Risks accepted

- The control plane is a single point of failure for token minting; if it is down, no new viewers or gateways can connect. Existing connections with valid tokens continue until token expiry (â‰¤60 s). Mitigated by Railway health checks, external probes, rollback/redeploy, and alternate-host DR path.

## Alternatives considered

### A. Monolithic single-process app serving both HTTP and media

- **Rejected**: any vulnerability in the media path (WebRTC stack, codec parsing) could pivot to DB credentials, session cookies, and audit HMAC keys. Violates Inv 3, Inv 4.

### B. Media via Cloudflare Tunnel

- **Rejected**: Tunnel is HTTP-only; WebRTC requires UDP. Attempting to tunnel WebRTC over HTTP/WebSocket degrades latency to unusable levels for live-view CCTV. Violates Inv 4.

### C. Camera credentials stored in the control plane (app manages RTSP directly)

- **Rejected**: `cctv-api` would hold RTSP credentials, making a control-plane compromise a camera-credential breach. The edge-gateway design (Inv 6) ensures camera credentials never leave the on-site box. Violates the camera-plane isolation principle.

### D. Shared secret store across planes

- **Rejected**: a single shared secret store holding both DB URL and media-plane keys means one leaked deploy/provider credential exposes everything. Per-plane secret scopes provide isolation.

## Verification

- **T-30**: external-exposure checklist confirms the supported user entry point is Cloudflare-protected and direct origin access does not expose protected routes.
- **T-45**: media-plane isolation confirms media host exposes only media ports; no HTTP app/admin/DB access.
- **T-56**: origin-binding confirms direct Railway-origin requests fail closed without valid CF Access JWT.
- **T-57**: DB least-privilege confirms runtime role restrictions.
- **Observability tags**: all logs/metrics/alerts tagged `plane=control|media|camera` to confirm separation in practice.

## References

- v4 plan Â§10.1â€“10.4 (System Architecture)
- v4 plan Â§12 (Technology Stack â€” per-plane rows)
- v4 plan Â§16.10 (Origin / control-plane exposure controls)
- v4 plan Â§20.13 (Provider-exit playbook â€” per-plane)
- Invariants 1, 3, 4, 6, 14, 15

