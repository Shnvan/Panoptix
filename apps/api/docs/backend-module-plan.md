# Backend module plan (core MVP)

This is the proposed `cctv-api` module structure and implementation order derived from:

- `docs/implementation/api-reference.md`
- ADRs `0001`, `0003`, `0008`, `0009`, `0010`, `0014`
- `docs/architecture/sequence-*.mmd`
- Database ERD + guardrails

## Proposed package layout

```text
cctv_api/
  app.py
  main.py
  settings.py
  db.py
  models/
    base.py
    enums.py
    tables.py
  api/
    v1/
      router.py
      me.py
      cameras.py
      sessions.py
      privacy.py
      admin/
        router.py
        users.py
        cameras.py
        gateways.py
        audit.py
        health.py
      gateways.py
      gateway_control.py
      webhooks.py
  auth/
    cf_access_jwt.py
    sessions.py
    csrf.py
    rbac.py
    camera_acl.py
  policy/
    authorization.py
  livekit/
    tokens.py
    webhook_verify.py
  audit/
    writer.py
    chain.py
  gateway/
    identity.py
    commands.py
  errors/
    problem_details.py
```

## Implementation order (foundation-first)

1. **HTTP basics**
   - `/health` exact shape
   - RFC 9457 Problem Details error helper
2. **Cloudflare Access JWT verification + origin-binding**
   - fail-closed middleware for protected routes
   - dev-auth mode per `docs/implementation/development-setup.md`
3. **DB session + models integration**
   - integrate SQLAlchemy session dependency into FastAPI
4. **AuthZ primitives**
   - RBAC roles/permissions resolution
   - per-camera ACL checks
5. **Core browser endpoints**
   - `GET /api/v1/me`
   - `GET /api/v1/cameras`
   - `GET /api/v1/cameras/:id/view-token`
6. **Gateway identity + heartbeat**
   - service-token MVP auth
   - `POST /api/v1/gateways/:id/heartbeat`
7. **Token minting**
   - viewer-subscribe vs gateway-publish strict separation
8. **Audit writer (append-only)**
   - start with minimal event set for actions above
9. **Admin endpoints (core)**
   - minimal CRUD for users/cameras/gateways + audit viewing
10. **Gateway control channel**
   - outbound WS + heartbeat fallback command delivery
11. **Webhooks**
   - LiveKit webhook verification + replay-cache

