# ADR 0008 - Gateway Identity and mTLS CA Design

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: System Owner, Software Architect, Operations Owner
- **Decision**: Service-token MVP + mTLS required before pilot
- **Supersedes**: None
- **Plan references**: Section 11.5; Section 13.8; Section 13.9; Section 14.1; Section 15.3; Section 16.16; Section 20.14; Section 20.15; ADR 0001; ADR 0012; ADR 0013

## Context

The edge gateway is the only production publisher in the system. It pulls RTSP from cameras/NVRs on the camera VLAN and publishes to LiveKit using short-lived gateway-publish tokens minted by `cctv-api`.

The control plane must therefore authenticate each gateway before it issues a gateway-publish token. Gateway identity answers four questions:

1. Which gateway is making this request?
2. Is that gateway enabled?
3. Which cameras is that gateway allowed to publish?
4. Has this gateway credential been rotated, revoked, or compromised?

Without gateway identity, any machine could attempt to impersonate a camera gateway, request publisher tokens, publish fake video, or spam gateway endpoints.

## Decision

**Use a staged gateway identity model: service-token identity for MVP, with mTLS client certificates required before pilot.**

This provides fast MVP implementation while preserving a strong pilot/production security path.

## MVP design - service token per gateway

### Credential issuance

- One high-entropy service token is generated per gateway.
- Token is generated server-side during gateway enrolment.
- Raw token is shown/downloaded once through an authenticated admin enrolment flow.
- Raw token is never stored server-side after issuance.
- Server stores only `edge_gateways.service_token_hash`, using Argon2id.

### Gateway storage

Production on-site gateway:

```text
/etc/cctv-gateway/gateway.env
mode: 0600
owner: cctv-gateway:cctv-gateway
loaded by: systemd EnvironmentFile= in cctv-gateway.service
```

Dev/CI synthetic gateway:

```text
Secret loaded into the selected dev/CI gateway process environment
```

The token must never be embedded in source code, container image layers, logs, or audit payloads.

### Request authentication

Every gateway request to `cctv-api` must include:

```text
Authorization: Bearer <gateway-service-token>
```

The route is also protected by the Cloudflare Access gateway service-token policy for `/api/v1/gateways/*` during MVP.

The app validates:

1. Token hash matches exactly one `edge_gateways` row.
2. Gateway status is `enabled`.
3. Request path is scoped to that gateway ID.
4. Gateway has an active `gateway_camera_assignments` row for the requested camera.
5. Requested camera is not retired.

Only then can the app mint a `gateway_publish` LiveKit token.

### Rotation

Rotation flow:

1. Admin triggers gateway credential rotation.
2. App generates new token.
3. Admin delivers token to gateway out-of-band or through one-shot enrolment download.
4. Gateway updates `/etc/cctv-gateway/gateway.env` and restarts service.
5. App revokes old token hash.
6. Audit `gateway.credential.rotated`.

Rotation occurs quarterly or immediately after suspected compromise.

## Pilot+ design - mTLS client certificates

Before pilot, each production gateway must have a client certificate. Service tokens may remain only as a temporary migration fallback, not as the final pilot posture.

### CA model

Default design:

- Self-managed internal CA.
- Offline root CA.
- Online intermediate CA used to issue gateway leaves.
- Root key escrowed in sealed envelope with dual-control access.
- Intermediate key protected in an operator-controlled secret store.

Alternative:

- Cloudflare mTLS can be used if procurement and operational checks show it is simpler and sufficiently auditable.

The final CA implementation can be confirmed during procurement, but the identity requirement is fixed: **gateway mTLS is required before pilot**.

### Gateway leaf certificate

Each gateway receives a unique 90-day client certificate:

- CN = gateway ID.
- SAN = gateway hostname, e.g. `cctv-gw-<site-slug>`.
- Key generated on the gateway where feasible.
- Leaf certificate deployed to the gateway secret path with restrictive permissions.

### Server-side validation

For every gateway request, the app validates:

1. Client certificate chains to trusted CA root/intermediate.
2. Certificate is within validity period.
3. SHA-256 fingerprint matches `edge_gateways.mtls_fingerprint`.
4. Gateway status is `enabled`.
5. Requested camera is assigned to that gateway.
6. Request path is scoped to that gateway.

The app stores:

```text
edge_gateways.mtls_fingerprint
edge_gateways.cert_expires_at
```

### Expiry and rotation

- Gateway certificates are valid for 90 days.
- Alert fires at `cert_expires_at - 14 days`.
- Rotation runbook issues a new leaf certificate, deploys it to the gateway, updates `mtls_fingerprint`, and audits the change.

Audit events:

- `gateway.cert.issued`
- `gateway.cert.deployed`
- `gateway.cert.fingerprint.updated`
- `gateway.cert.revoked`
- `gateway.cert.expiring_soon_alert`
- `gateway.credential.rotated`

### Revocation

On compromise:

1. Admin disables the gateway.
2. Existing publish is terminated within 10 seconds.
3. Certificate fingerprint is marked revoked or replaced.
4. Replacement credential/certificate is issued.
5. Rotation event is audited.

## Database implications

`edge_gateways` keeps both MVP and pilot identity fields:

```text
edge_gateways(
  id,
  name,
  status,
  service_token_hash NULL,
  mtls_fingerprint NULL,
  cert_expires_at NULL,
  last_seen_at,
  created_at,
  disabled_at
)
```

MVP permits service-token-only rows.

Pilot requires `mtls_fingerprint IS NOT NULL` for production gateways.

`gateway_camera_assignments` remains the sole authority for what a gateway may publish. Identity proves who the gateway is; assignments define what it can do.

## Consequences

### Positive

- **Fast MVP**: service-token authentication is simple and low-cost to build.
- **Scoped blast radius**: one credential per gateway means one compromised token disables only one gateway.
- **Pilot-grade path**: mTLS adds certificate-based device identity before real pilot use.
- **Auditable lifecycle**: issuance, rotation, expiry, and revocation are all represented in audit events.
- **Future-ready schema**: mTLS fields exist from the start, avoiding disruptive later migrations.

### Negative

- **Migration required**: MVP token-only gateways must be upgraded to mTLS before pilot.
- **CA operational burden**: mTLS requires certificate issuance, storage, expiry monitoring, and revocation procedures.
- **More failure modes**: expired certs, wrong fingerprints, clock skew, or CA misconfiguration can break gateway connectivity.

### Risks accepted

- During MVP, a stolen gateway service token can impersonate that gateway until it is disabled or rotated. This is accepted only for MVP because each token is gateway-scoped, stored with restrictive permissions, and must be replaced by mTLS before pilot.

## Alternatives considered

### A. Service-token only forever

- **Rejected**: too weak for pilot/production. Bearer tokens prove possession of a secret, not device identity. A stolen token remains usable until rotation.

### B. mTLS from day one

- **Rejected for MVP**: strongest option, but slows early implementation and introduces CA management before the basic gateway path is proven.

### C. Shared service token for all gateways

- **Rejected**: one leak compromises every site. Per-gateway credentials are mandatory.

### D. IP allow-listing as gateway identity

- **Rejected**: sites may not have static IPs, NATs change, and IPs do not prove device identity.

### E. Cloudflare Access service token only, with no app-side gateway identity

- **Rejected**: CF service token proves access to a route, not which gateway/cameras are authorized. The app must still bind identity to `edge_gateways` and `gateway_camera_assignments`.

## Verification

### MVP

- Gateway with valid service token can call heartbeat and ingest-token endpoints.
- Gateway with invalid service token is rejected.
- Disabled gateway is rejected.
- Gateway requesting an unassigned camera is rejected.
- Browser session calling gateway ingest endpoint is rejected.
- Token rotation invalidates the old token.
- Gateway credential never appears in logs, audit payloads, API responses, or browser bundle.

### Pilot

- Gateway with valid mTLS cert and matching fingerprint is accepted.
- Gateway with expired cert is rejected.
- Gateway with valid CA chain but mismatched fingerprint is rejected.
- Gateway with revoked/disabled status is rejected.
- Cert-expiry alert fires 14 days before expiry.
- Rotation updates fingerprint and audits issuance/deployment/update.

## Operational follow-up

- Implement service-token MVP enrolment flow.
- Ensure raw gateway token is one-shot displayed/downloaded only.
- Store only Argon2id token hash server-side.
- Add gateway credential rotation runbook checks.
- Before pilot, use an internal project CA for gateway mTLS unless implementation-time Cloudflare mTLS support proves simpler and equivalent.
- Before pilot, issue 90-day mTLS certificates for production gateways.
- Before pilot, enforce `mtls_fingerprint IS NOT NULL` for production gateways.

## References

- v4 plan Section 11.5 (Gateway identity)
- v4 plan Section 13.8 (Camera Site Hardware)
- v4 plan Section 13.9 (Camera Network Design)
- v4 plan Section 14.1 (Data model)
- v4 plan Section 15.3 (Token-mint authorization summary)
- v4 plan Section 16.16 (Gateway identity & mTLS summary)
- v4 plan Section 20.14 (Gateway lifecycle runbook)
- v4 plan Section 20.15 (Gateway certificate rotation runbook)
- ADR 0001 (Plane separation)
- ADR 0012 (Camera network design)
- ADR 0013 (Gateway hardware standard)

