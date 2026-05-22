# Glossary

<!-- PE-FIX: Created domain terminology reference for onboarding and clarity -->

Key terms used throughout the Panoptix CCTV monitoring system documentation.

---

| Term | Definition |
|------|------------|
| **Control plane** | The Railway-hosted application layer: `cctv-web` provides the React + Vite UI, while `cctv-api` provides the Python/FastAPI security-authoritative API for authentication verification, authorization, token minting, audit logging, gateway control, and database access. |
| **Media plane** | The LiveKit-based video delivery layer. LiveKit Cloud (APAC) is the primary SFU; a self-hosted LiveKit instance is the fallback. Carries WebRTC media traffic only. |
| **Camera plane** | The on-site infrastructure: IP cameras, the camera VLAN, and the edge gateway mini-PC. Isolated from the internet and the operator LAN. |
| **SFU** | Selective Forwarding Unit. A server that receives media streams from publishers and forwards them to subscribers without mixing. LiveKit is the SFU used in this system. |
| **Edge gateway** | An on-site NUC-class mini-PC that pulls RTSP video from cameras and publishes it to LiveKit. The only production publisher in the system. |
| **mediamtx** | Open-source media software running on the gateway that handles RTSP camera stream ingest. |
| **Presence-driven publish** | The streaming model where the gateway starts publishing a camera feed to LiveKit only when at least one viewer is watching, and stops after the last viewer leaves (with a 10-second grace timer). Conserves LiveKit minutes. |
| **Viewer-subscribe token** | A short-lived (≤60 s) LiveKit JWT that allows a browser to receive (subscribe to) a camera's video stream. Subscriber-only — cannot publish. |
| **Gateway-publish token** | A short-lived (≤60 s) LiveKit JWT that allows a gateway to publish a camera's video stream to LiveKit. Publisher-only — cannot subscribe. |
| **Break-glass** | Emergency admin access for IdP/user/MFA/admin-lockout scenarios while Cloudflare Access remains healthy. Uses a sealed account with a hardware security key. Limited to a 90-minute request-time-enforced window. |
| **Cloudflare Access** | Cloudflare's identity-aware proxy that gates access to the control plane. Federates to Google Workspace for authentication. |
| **CF JWT** | The `Cf-Access-Jwt-Assertion` header — a signed JWT issued by Cloudflare Access after successful authentication. Verified by the FastAPI app on every protected route. |
| **Origin-binding** | The security control ensuring the FastAPI app rejects requests that do not carry a valid Cloudflare Access JWT, even if they reach the Railway origin directly. |
| **RBAC** | Role-Based Access Control. The system uses roles (Viewer, Admin, Auditor, SuperAdmin) combined with camera-level ACLs to determine what each user can do. |
| **Camera ACL** | A per-user, per-camera access control list. A viewer can only watch cameras they have been explicitly granted access to. |
| **HMAC chain** | The tamper-evidence mechanism for audit logs. Each audit row includes an HMAC-SHA-256 hash computed over the previous row's hash plus the current row's content, creating a verifiable chain. |
| **STRIDE** | A threat modeling framework: **S**poofing, **T**ampering, **R**epudiation, **I**nformation disclosure, **D**enial of service, **E**levation of privilege. |
| **Camera VLAN** | A dedicated, isolated network segment for IP cameras. Cameras cannot reach the operator LAN or the internet. Only the gateway has access to this VLAN. |
| **mTLS** | Mutual TLS — a pilot+ requirement where both the gateway (client) and the control plane (server) authenticate each other using certificates. Replaces service tokens for gateway identity. |
| **Service token** | A high-entropy bearer token used by gateways for MVP authentication. One token per gateway, Argon2id-hashed server-side. Replaced by mTLS before pilot. |
| **PIA** | Privacy Impact Assessment. A structured analysis of how the system processes personal data, required under RA 10173 (Philippine Data Privacy Act). |
| **DPA** | Data Processing Agreement. A contract between the controller (system owner) and each processor (vendor) governing how personal data is handled. |
| **RA 10173** | Republic Act 10173 — the Philippine Data Privacy Act of 2012. The primary privacy regulation governing this system. |
| **NPC** | National Privacy Commission — the Philippine regulatory body for data privacy. |
| **ADR** | Architecture Decision Record. A structured document capturing a significant architectural decision, its context, alternatives considered, and consequences. |
| **Provider-exit boundary** | A design principle ensuring each system component (control plane, media plane, camera plane, database) can be independently migrated to a different provider without rewriting the others. |
| **Invariant** | A non-negotiable constraint that must hold true at all times. The system has 16 invariants covering security, architecture, and product identity. |
