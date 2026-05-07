# ADR 0004 â€” LiveKit Fallback Strategy

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: Software Architect, System Owner
- **Supersedes**: None
- **Amended by**: ADR 0014 â€” Railway + Python Control Plane
- **Plan references**: Invariant 4, 13; Â§10.1â€“10.4; Â§12 stack table; Â§12.2; Â§13.4; Â§13.5 rules 6, 8, 9, 14; Â§18.2 T-37, T-45; Â§20.10; Â§23 Risk R-02

## Context

The media plane uses **LiveKit Cloud (APAC)** as its primary SFU for WebRTC media. LiveKit Cloud is a managed service â€” the system does not control its infrastructure. This creates a single-vendor dependency for the media plane:

- **Quota exhaustion**: LiveKit Cloud may impose bandwidth, participant, or room limits.
- **Regional outage**: the APAC region could become unavailable.
- **Pricing changes**: LiveKit Cloud could change pricing in ways that make continued use uneconomic.
- **Service discontinuation**: unlikely but possible for any SaaS vendor.

The system's architecture (ADR 0001) separates the media plane from the control plane. This separation makes a media-plane failover feasible without touching authentication, authorization, audit, or the database.

The key constraint is **â‰¤60 s reconnection RTO**: since viewer and gateway tokens are already â‰¤60 s TTL, a failover that completes within one token-refresh cycle is invisible to end users (they simply reconnect with a new token pointing at the fallback endpoint).

## Decision

**A self-hosted LiveKit fallback remains required as the media-plane provider-exit strategy. After ADR 0014, Railway is used for the control plane and is not selected for LiveKit fallback. DigitalOcean Singapore is the first procurement candidate for fallback hosting, with an equivalent UDP-capable APAC VPS/provider as fallback. The selected provider must be verified to support LiveKit SFU networking requirements, especially UDP/media ports and TCP/TLS:443 fallback.**

### Fallback architecture

```
  LiveKit Cloud (APAC)        â† PRIMARY (normal operation)
         |
    [feature flag flip]
         |
  self-hosted LiveKit fallback     â† FALLBACK (DigitalOcean SG candidate)
    - Separate media-plane service
    - UDP/media-port support verified
    - Only LiveKit media ports exposed
    - TCP/TLS:443 fallback for restrictive networks
    - Separate secret store
    - No HTTP app/admin endpoints
    - No DB connection
    - No Cloudflare Tunnel
```

### Pre-provisioning (warm standby)

The fallback instance is deployed and configured **before it is needed**:

1. **Fallback host selected** with DigitalOcean Singapore as first candidate, or equivalent APAC UDP-capable VPS/provider, only after verifying UDP/media-port and TCP/TLS:443 support.
2. **Dedicated public media endpoint** allocated if required by the selected provider.
3. **LiveKit server binary** deployed in a container or provider-supported runtime with:
   - Media ports (UDP range) open.
   - TCP/TLS:443 fallback enabled (TURN over TLS).
   - No HTTP application surface (no `/dashboard`, no `/admin`, no `/api/*`).
4. **Media-plane secrets** provisioned: LiveKit API key/secret pair (same pair used by `cctv-api` for token minting, or a dedicated fallback pair â€” recorded at provisioning time).
5. **Webhook endpoint** configured: fallback LiveKit sends webhooks to `cctv-api` at `POST /api/v1/webhooks/livekit` (same endpoint, same HMAC verification).
6. **Observability**: tagged `plane=media`, `instance=fallback`; separate dashboards.

The fallback instance should consume minimal resources when idle (no rooms, no participants, no media traffic). Cost depends on the chosen UDP-capable provider and is verified at procurement.

### Activation (failover)

**Trigger**: LiveKit Cloud quota exhaustion, regional outage, or manual decision.

**Procedure** (per Â§20.10 runbook):

1. SuperAdmin authenticates via CF Access App B (re-auth required).
2. `POST /api/v1/admin/livekit/fallback` â†’ sets `system_config.media_plane_mode = 'fallback'`.
3. **Token minting switches**: `cctv-api` starts issuing viewer-subscribe and gateway-publish tokens with the fallback LiveKit URL instead of the Cloud URL.
4. **CSP update**: the response middleware reads `system_config.media_plane_mode` per request and adds the fallback domain to `connect-src` (both Cloud and fallback domains are pre-approved values in code; M-08 dynamic CSP mechanism). No redeploy needed.
5. **Reconnection**: existing tokens expire within â‰¤60 s. Clients (viewers + gateways) request new tokens, which now point to the fallback. Reconnection completes within one refresh cycle.

**No redeploy, no DNS change, no config file edit.** The switch is a DB flag flip.

### Rollback

1. SuperAdmin calls `POST /api/v1/admin/livekit/rollback` (or flips the flag back).
2. Token minting switches back to LiveKit Cloud URL.
3. CSP reverts.
4. Clients reconnect within â‰¤60 s.
5. Both transitions are audit-logged: `system.media_plane.switched_to_fallback`, `system.media_plane.switched_to_primary`.

### Isolation guarantees

| Property | Enforced by |
|---|---|
| No DB access from fallback | No DB connection string in fallback secrets; network policy blocks egress to Postgres where supported |
| No app endpoints on fallback | No HTTP app deployed; only LiveKit server binary |
| No shared secret store | Separate media-plane service/provider secret scope |
| No Cloudflare Tunnel on fallback | No `cloudflared` sidecar; media host is not behind CF Access |
| Media-only ports | Provider exposes only LiveKit media ports + TCP/TLS:443 |

### Acceptance criteria

- **T-37 (expanded)**: UDP preferred â†’ verify media flows over UDP. TCP/TLS:443 fallback â†’ verify media flows when UDP is blocked. Viewer + gateway reconnection â‰¤60 s after flag flip.
- **T-45**: media host scanned â†’ only LiveKit media ports reachable. HTTP `/`, `/admin`, `/api/*` â†’ connection refused. DB connection from media host â†’ blocked. Secrets store scoped to media-plane only.

## Consequences

### Positive

- **â‰¤60 s RTO for media plane**: failover is invisible to users within one token-refresh cycle.
- **No redeploy required**: DB flag flip + dynamic CSP = instant switch.
- **Blast-radius containment**: fallback instance cannot access the DB, app endpoints, or control-plane secrets (ADR 0001 plane separation).
- **Provider-exit path**: if LiveKit Cloud becomes untenable long-term, the fallback instance is already running the same software. Migration is a permanent flag flip.
- **Cost-bounded standby**: fallback cost is verified during procurement and kept idle/warm according to budget.

### Negative

- **Operational overhead**: a second LiveKit instance to maintain, update, and monitor.
- **Media-host cost**: UDP-capable hosting may cost more than a simple Railway web service and must be budgeted separately.
- **Webhook routing**: fallback instance must be able to reach `cctv-api`'s webhook endpoint via CF Access (service-token protected). This adds a cross-plane dependency.
- **No automatic failover**: the switch is manual (SuperAdmin action). Automatic failover (health-check-driven) is deferred to pilot+ to avoid false-positive flips.

### Risks accepted

- **Fallback provider requires verification**: DigitalOcean Singapore is the first candidate, but the final fallback host must pass UDP/media-port, TCP/TLS:443, isolation, cost, and DPA/procurement checks before pilot or the fallback requirement must be explicitly deferred with risk acceptance.
- **Manual activation latency**: time to detect the issue + time for SuperAdmin to authenticate + activate. Could be 5â€“15 minutes. Mitigated by alerts on LiveKit Cloud health metrics.

## Alternatives considered

### A. No fallback â€” rely solely on LiveKit Cloud

- **Rejected**: creates a hard dependency on a single SaaS vendor for the media plane. Any outage, quota change, or pricing change halts all live viewing with no recourse. Violates Invariant 13 (provider-exit boundaries).

### B. Automatic health-check-driven failover

- **Deferred to pilot+**: automatic failover risks false positives (a transient LiveKit Cloud hiccup triggers a flip, then the flip-back causes a second disruption). Manual activation for MVP; automated with hysteresis and dead-man's-switch for pilot.

### C. mediamtx WebRTC as fallback (no LiveKit at all)

- **Rejected for MVP**: mediamtx's WebRTC support is less mature than LiveKit's SFU. Using the same SFU software (LiveKit) for both primary and fallback means the same client SDK, the same token format, the same room model. Switching is a URL change, not a protocol change.

### D. Multi-region active-active media plane

- **Rejected for MVP**: active-active requires room routing, participant migration, and significantly more operational complexity. Overkill for â‰¤4 users / â‰¤10 cameras at MVP scale.

### E. Cloudflare Tunnel for media (eliminate separate media plane)

- **Rejected**: Tunnel is HTTP-only. WebRTC requires UDP for acceptable latency. Attempting to tunnel WebRTC over HTTP/WebSocket degrades quality to unusable levels for live CCTV monitoring. This is a hard technical constraint, not a preference.

## Verification

- **T-37 (expanded)**: UDP media flow verified; TCP/TLS:443 fallback verified; reconnection â‰¤60 s verified.
- **T-45**: media host isolation verified (no HTTP app, no DB, no control-plane secrets).
- **Failover drill**: quarterly manual failover exercise (activate â†’ verify media flows â†’ rollback â†’ verify). Documented in runbook Â§20.10.
- **Idle monitoring**: alert if the fallback LiveKit host goes unhealthy while in standby (before it's needed).

## References

- v4 plan Invariant 4 (Control-plane vs media-plane separation)
- v4 plan Invariant 13 (Provider-exit boundaries)
- v4 plan Â§10.1 (System Architecture â€” media plane)
- v4 plan Â§12 (Technology Stack â€” media plane rows)
- v4 plan Â§12.2 (Provider-exit considerations)
- v4 plan Â§13.4 (Self-hosted LiveKit fallback â€” networking model)
- v4 plan Â§13.5 rules 6, 8, 9, 14
- v4 plan Â§18.2 T-37, T-45
- v4 plan Â§20.10 (LiveKit quota-fallback runbook)
- v4 plan Â§23 Risk R-02 (LiveKit Cloud outage)

