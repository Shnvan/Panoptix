# Tech Stack — Simple Current Guide

This is the current easy-to-understand technology stack after the decision to use **Railway + Python**.

## Big Picture

```text
User opens CCTV website
→ Cloudflare checks if the user is allowed
→ Google Workspace confirms the user's identity
→ Railway runs our Python web app
→ The user sees the CCTV dashboard
→ LiveKit sends live video to the browser
→ The on-site gateway sends camera video to LiveKit
→ Cameras stay private on the local network
```

The system has three parts:

| Part | Meaning |
|---|---|
| Control plane | Login, dashboard, API, permissions, audit, database |
| Media plane | Live video delivery through LiveKit |
| Camera plane | Physical cameras, local gateway, isolated camera network |

---

## 1. Google Workspace

**What it is:** The school's existing Google account system.

**Purpose:** Users log in with their school Google account.

**Why we use it:** The school already has it, so it is low-cost. It supports strong login security like passkeys and hardware keys.

**Why not others:**

| Alternative | Why not |
|---|---|
| Build our own login | Too risky; we would need passwords, reset, MFA, account recovery |
| GitHub | Better for developers, not school users |
| Microsoft Entra | Good, but unnecessary if the school already uses Google |
| Okta | Strong but paid and overkill for MVP |
| Cloudflare email OTP | Email codes are weaker and can be phished |

---

## 2. Cloudflare Access

**What it is:** A security gate before the app.

**Purpose:** It blocks users who are not logged in or not allowed.

**Why we use it:** It protects the app before traffic reaches Railway. Our app does not need a custom username/password login page.

**Why not only app login:** If we only check login inside the app, attackers can still hit the app directly. Cloudflare Access stops them earlier.

---

## 3. Cloudflare DNS, WAF, and Rate Limits

**What it is:** Cloudflare manages the domain and protects public traffic.

**Purpose:** Users access the app through a Cloudflare-protected domain like `cctv.<domain>`.

**Why we use it:** It gives DNS, attack filtering, rate limits, and integration with Cloudflare Access.

**Why not registrar DNS only:** Registrar DNS usually does not provide the same security features.

---

## 4. Railway

**What it is:** The hosting platform for our main web app.

**Purpose:** Railway runs the Python/FastAPI control-plane app.

Railway hosts:

- Next.js dashboard pages
- Next.js admin pages
- API endpoints
- Next.js privacy pages
- token minting
- gateway heartbeats
- LiveKit webhook receiver
- audit logging

**Why we use it:** The project now requires Railway. It can host the control plane as separate frontend and backend services while keeping the public app behind Cloudflare Access.

**Why not Fly.io now:** Fly.io was the old plan. Railway is now the chosen app host. Fly or another provider may still be considered only for special media networking later.

---

## 5. Python

**What it is:** The programming language for the backend.

**Purpose:** Python handles the app's server-side logic.

Used for:

- checking Cloudflare login tokens
- checking user permissions
- creating LiveKit viewer tokens
- creating gateway publish tokens
- writing audit logs
- receiving gateway heartbeats
- handling admin actions

**Why we use it:** The project now requires Python. It is readable, mature, and has good backend/security libraries.

**Why not Node.js/TypeScript for backend now:** Node/TypeScript is used only for the selected Next.js frontend. Python remains the chosen backend/security-authoritative language.

---

## 6. FastAPI

**What it is:** A Python web framework.

**Purpose:** FastAPI runs the web API and backend routes.

**Why we use it:** It is fast, clean, and good for security-sensitive APIs. It has good request validation and automatic API documentation.

**Why not Django:** Django is powerful but heavier than needed for this API/token-heavy MVP.

**Why not Flask:** Flask is simple, but FastAPI has better validation and type-hint support for this project.

---

## 7. Next.js, React, and Tailwind

**What they are:** Tools for building the web dashboard.

| Tool | Purpose |
|---|---|
| Next.js | Provides the frontend app, routing, and page structure |
| React | Builds interactive dashboard, admin, and video-viewer components |
| Tailwind | Styles the dashboard |

**Purpose:** Build the MVP dashboard and admin UI as a dedicated frontend application.

**Why we use them:** The team now has a dedicated frontend coworker. Next.js/React gives that teammate a clear UI surface while FastAPI remains the backend/security authority.

**Security rule:** The frontend displays state and calls same-origin `/api/v1/*` routes, but it never decides permissions, never mints stream tokens, never receives gateway-publish tokens, and never receives camera RTSP credentials.

---

## 8. LiveKit JavaScript Client

**What it is:** A browser library for watching LiveKit video.

**Purpose:** It lets the user's browser receive live CCTV video.

**Why we use it:** Even with Python backend, the browser still needs JavaScript to play WebRTC video.

**Important:** This is only for viewing. Browser camera publishing is still banned.

---

## 9. Neon Postgres

**What it is:** Hosted Postgres database.

**Purpose:** Stores the app's main data.

Stores:

- users
- sessions
- cameras
- camera permissions
- gateways
- gateway-camera assignments
- stream token records
- audit logs
- privacy records
- backup records

**Why we use it:** Neon has a free prototype tier and a paid path for pilot with PITR checks.

**Why not Railway database by default:** We already decided Neon-first. Railway may host the app, but Neon is still our database plan.

**Rule:** Neon Free is for prototype only. Paid Postgres is required before pilot.

---

## 10. SQLAlchemy 2.x

**What it is:** Python database library.

**Purpose:** Lets FastAPI talk to Postgres safely.

**Why we use it:** It is standard in Python and avoids messy raw SQL everywhere.

**Why not Drizzle:** Drizzle is for TypeScript/Node. We are now using Python.

---

## 11. Alembic

**What it is:** Database migration tool for Python/SQLAlchemy.

**Purpose:** Tracks database changes over time.

**Why we use it:** It makes schema changes repeatable and reviewable.

**Why not manual database edits:** Manual edits are hard to track and easy to mess up.

---

## 12. Pydantic

**What it is:** Python data validation library.

**Purpose:** Validates API inputs, config, and internal data.

**Why we use it:** Bad input should be rejected early, especially for camera IDs, gateway IDs, tokens, webhooks, and admin actions.

---

## 13. LiveKit Cloud

**What it is:** The main video streaming service.

**Purpose:** Sends live camera video to browser viewers.

```text
Camera → Gateway → LiveKit → Browser viewer
```

**Why we use it:** It handles low-latency WebRTC video well.

**Why not direct camera viewing:** Direct camera viewing would expose camera networks and credentials.

---

## 14. LiveKit Fallback

**What it is:** A backup LiveKit server for emergencies.

**Purpose:** Used if LiveKit Cloud has an outage, quota problem, or pricing issue.

**Updated note:** The fallback host is separate from Railway. DigitalOcean Singapore is the first procurement candidate, with an equivalent UDP-capable APAC VPS/provider as fallback. The provider must be verified for UDP/media ports and TCP/TLS:443 fallback before pilot.

**Why not Railway automatically:** Railway is good for web apps, but media servers have special networking requirements.

---

## 15. On-site Gateway Mini-PC

**What it is:** A small computer installed where the cameras are.

**Purpose:** Pulls video from local cameras and sends it to LiveKit.

```text
IP Camera/NVR → Gateway → LiveKit → Viewer
```

**Why we use it:** Cameras stay private and do not need internet access.

**Why not connect cameras directly to cloud:** That would expose camera credentials and weaken security.

**Final gateway decision:** Real production cameras use an on-site physical NUC-class x86_64 mini-PC only. Virtual/cloud gateways are allowed only for dev/CI synthetic RTSP testing and are never connected to real cameras.

---

## 16. Ubuntu Server, Docker, and systemd

**What they are:** The operating system and service tools for the gateway.

| Component | Purpose |
|---|---|
| Ubuntu Server | Stable OS for the gateway |
| Docker | Runs gateway software consistently |
| systemd | Starts/restarts the gateway service |

**Why we use them:** They are common, stable, and easy to operate on mini-PC hardware.

---

## 17. mediamtx

**What it is:** Media software that can handle RTSP camera streams.

**Purpose:** Pulls RTSP streams from cameras on the local network.

**Why we use it:** It is mature and good for RTSP ingest.

**Why not browser RTSP:** Browsers do not handle RTSP well, and camera details must not be exposed.

---

## 18. Gateway Agent

**What it is:** Our small service running on the gateway.

**Purpose:** Talks to the Railway/FastAPI app, sends heartbeats, and starts/stops camera publishing.

**Why we need it:** mediamtx handles media, but the gateway agent handles app permissions, identity, and control commands.

---

## 19. Camera VLAN

**What it is:** A separate local network for cameras.

**Purpose:** Keeps cameras away from the normal school network and away from the internet.

**Why we use it:** Cameras are often weakly secured. Isolation protects both cameras and school devices.

---

## 20. Gateway Service Tokens and mTLS

**What they are:** Ways for the gateway to prove its identity.

**Decision:**

```text
MVP: service token per gateway
Pilot: mTLS certificate required
```

**Why this:** Service tokens are simple for MVP. mTLS is stronger for pilot.

**Why not shared token:** One leaked shared token would compromise all gateways.

---

## 21. FFmpeg Synthetic Camera

**What it is:** Fake test video generated by FFmpeg.

**Purpose:** Lets us test the video pipeline without a real camera.

**Why we use it:** It is safe, repeatable, and has no real people in the video.

---

## 22. Cloudflare R2, pg_dump, pg_restore, and age

**What they are:** Backup tools.

| Tool | Purpose |
|---|---|
| pg_dump | Exports Postgres backup |
| age | Encrypts the backup |
| R2 | Stores the encrypted backup |
| pg_restore | Verifies/restores the backup |

**Why we use them:** We need backups that are encrypted, portable, and testable.

**Why not provider backups only:** Provider backups are useful, but independent encrypted backups are safer for recovery and provider exit.

---

## 23. Audit Log with HMAC Chain

**What it is:** A tamper-evident log of important actions.

**Purpose:** Records who did what and when.

Examples:

- admin changes permissions
- user views a camera
- gateway rotates credential
- emergency break-glass opens

**Why we use it:** Normal logs are not enough for security evidence. The HMAC chain helps detect tampering.

---

## 24. Monitoring and Alerts

Tools:

| Tool | Purpose |
|---|---|
| Sentry | App error tracking |
| Better Stack | Logs and monitoring |
| UptimeRobot | External uptime checks |
| Telegram | Fast MVP alerts |
| Email | Backup alert channel |

**Why we use them:** They are low-cost and enough for MVP.

**Why not PagerDuty now:** PagerDuty is useful later, but MVP can start with simpler alerts.

---

## 25. GitHub and GitHub Actions

**What they are:** Code storage and automation.

**Purpose:** Store code/docs and run tests, scans, builds, and deploys.

**Why we use them:** They make development and deployment repeatable.

**Why not manual deployment:** Manual deployment is error-prone and hard to audit.

---

## 26. Testing and Security Scanning

| Tool | Purpose |
|---|---|
| pytest | Python tests |
| Playwright | Browser tests |
| Semgrep | Code security checks |
| osv-scanner | Dependency vulnerability checks |
| Trivy | Container/dependency scans |
| gitleaks | Secret leak detection |
| ZAP | Web security baseline scan |
| k6 | Load/rate-limit tests |

**Why we use them:** They catch problems before deployment.

---

## 27. Terraform

**What it is:** Infrastructure as code.

**Purpose:** Configure Cloudflare, Railway, Neon, R2, and related infrastructure where supported.

**Why we use it:** It makes infrastructure changes repeatable and reviewable.

**Why not dashboard clicks only:** Dashboard changes are easy to forget and hard to reproduce.

---

## What We Are Not Using in MVP

| Not using | Reason |
|---|---|
| Custom password login | Google Workspace handles login |
| Browser camera publishing | CCTV-only system; browsers only view |
| Phone/laptop camera publishing | Not allowed by product design |
| Server-side recording | MVP is live-view only |
| Public RTSP ports | Cameras must not be exposed to internet |
| Redis | Not needed for small MVP |
| Async queue | Not needed yet |
| Railway LiveKit fallback by default | Must verify media networking first |

---

## Final Summary

Current stack:

```text
Google Workspace
+ Cloudflare Access/DNS/WAF
+ Railway
+ Next.js/React/Tailwind
+ Python FastAPI
+ Neon Postgres
+ LiveKit Cloud
+ On-site gateway mini-PC
+ mediamtx
+ Camera VLAN
+ Cloudflare R2 backups
+ GitHub Actions CI/CD
```

This stack keeps the system secure while using Railway for the Next.js frontend and Python/FastAPI backend control-plane services.
