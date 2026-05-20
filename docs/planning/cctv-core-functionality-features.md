# Panoptix — Core Functionality and Features

This document explains what the CCTV web monitoring system does, who uses it, and what features are included. It is written for school staff, security operators, admins, and submission reviewers.

---

## 1. Overview

Panoptix is a secure, web-based CCTV monitoring system. Authorized users open a website in their browser to view live camera feeds from IP cameras installed on site.

The system has three parts:

| Part | What it does |
|---|---|
| **Control plane** | Login, dashboard, permissions, admin tools, audit logs, and database. Hosted on Railway. |
| **Media plane** | Delivers live video from cameras to the browser using LiveKit. |
| **Camera plane** | Physical IP cameras on site, connected to a local gateway computer on a private network. |

### How it works (simplified)

```text
User opens the CCTV website
→ Cloudflare checks if the user is allowed in
→ Google Workspace confirms the user's identity
→ Railway serves the dashboard
→ The user selects a camera
→ LiveKit sends live video to the browser
→ The on-site gateway pulls the camera feed and sends it to LiveKit
→ Cameras stay private on their own isolated network
```

Users never connect directly to cameras. Cameras never touch the internet. The gateway is the only bridge between the camera network and the cloud.

---

## 2. Who Uses the System

| Role | Description |
|---|---|
| **Viewer** | School staff or security personnel who watch live camera feeds. They can only see cameras they are assigned to. |
| **Admin** | Manages users, cameras, gateways, permissions, audit logs, system configuration, and compliance records. |
| **Gateway** | Not a person — this is the on-site computer's machine identity. It authenticates to the system to publish camera video. |

### Key rules

- New users start with **no permissions** until an admin assigns a role.
- Camera access is granted per user, per camera — your role alone does not give you cameras.
- Admin pages require Cloudflare Access verification.

---

## 3. Core Viewer Features

These are the features available to normal users who watch cameras.

### Secure login

- Users log in with their **school Google Workspace account** through Cloudflare Access.
- **Passkey or hardware security key** is required — password-only login is not allowed.
- There is no separate username/password page inside the app. Cloudflare and Google handle login.

### Live camera dashboard

- View live video from assigned IP cameras in a web browser.
- **Layout options**: 1×1 (single camera), 2×1 (two cameras), 2×2 (four cameras).
- **Fullscreen mode** for any camera.
- Works on desktop and mobile browsers (responsive web — no app to install).

### Camera status indicators

Each camera tile shows a clear status so viewers always know what is happening:

| Status | Meaning |
|---|---|
| **Online** | Camera is live and streaming. |
| **Offline** | Camera is not sending video. |
| **Reconnecting** | The system is trying to restore the connection. |
| **Unavailable** | The camera cannot be reached right now. |
| **Gateway unavailable** | The on-site gateway computer is not responding. |
| **Permission denied** | You do not have access to this camera. |

### Privacy notice

- On first login (and when the notice is updated), users see a privacy notice and must accept it before proceeding.
- Acceptance is recorded for compliance.

---

## 4. Admin and Operator Features

These features are available to Admins.

### User management

- **Invite users** through the identity provider (Google Workspace).
- **Assign roles**: Viewer or Admin.
- **Disable users** immediately — active sessions are terminated.
- **Reset MFA** for a user (admin-mediated; users cannot reset their own MFA).
- By default, no user holds both viewer and admin roles unless explicitly approved.

### Camera management

- **Register cameras**: add a camera with its name, source type, and assigned gateway.
- **Assign cameras to users**: per-user, per-camera access control.
- **Disable or retire cameras**: disabling a camera immediately stops all active viewer sessions for that camera (within 10 seconds).

### Gateway management

- **Register gateways**: add a gateway with its name and identity credentials.
- **Assign cameras to gateways**: each gateway only publishes video for its assigned cameras.
- **Disable or retire gateways**: disabling a gateway immediately stops all its active publish sessions (within 10 seconds).
- **Gateway health dashboard**: view heartbeat status, last-seen time, and certificate expiry (when mTLS is enabled).

### Camera and gateway health

A single admin dashboard shows:

- Which cameras are online, offline, or degraded.
- Which gateways are healthy and when they last checked in.
- Certificate expiry warnings for gateways (pilot phase and later).

### Audit logs

- **Full audit trail** of all privileged actions (login, role changes, camera assignments, gateway operations, security key rotations).
- **Tamper-evident**: audit records are chained with versioned cryptographic hashes — any tampering is detectable.
- **Filter** by user, action, or time range.
- **Export**: download a signed JSONL file for compliance or investigation.

### Break-glass emergency access

- A sealed emergency admin account that can be activated when normal admin access fails.
- **Automatically disabled after 90 minutes** — enforced by the system even if background processes fail.
- Requires a **hardware security key** to activate.
- Every action during the window is logged and flagged.

### Lost-MFA recovery

- If a user loses their MFA device, an admin can initiate recovery.
- Users **cannot** reset their own MFA — this prevents social engineering attacks.

---

## 5. Security Features Users Should Know

These security features protect the system. Users do not need to configure them, but should be aware of how they work.

| Feature | What it means for users |
|---|---|
| **No self-registration** | You cannot create your own account. An admin must add you. |
| **Deny-by-default** | New accounts have no access until an admin grants permissions. |
| **Passkey/MFA required** | You must use a passkey, hardware key, or strong MFA to log in. Email-only codes are not allowed as the primary login method. |
| **Short-lived stream access** | Your video viewing token expires in 60 seconds and is automatically refreshed while you watch. If your session is revoked, video stops within seconds. |
| **No browser camera publishing** | The system will never ask for your webcam, phone camera, or microphone. Video comes only from registered IP cameras. |
| **Camera credentials are hidden** | Camera passwords and network details are never shown in the dashboard, API, or browser. They exist only on the on-site gateway. |
| **Identity verified at every request** | Every page load and API call is checked against your Cloudflare Access identity. Bypassing the login page does not grant access. |
| **Admin actions require re-authentication** | Sensitive actions (like changing roles or disabling users) require a fresh login confirmation. |

---

## 6. Video Streaming Behavior

### How live video reaches your browser

1. **IP cameras** are connected to a private network at the site.
2. The **on-site gateway** (a small dedicated computer) pulls video from the cameras using the RTSP protocol.
3. When a viewer opens a camera on the dashboard, the gateway sends the video to **LiveKit Cloud**.
4. **LiveKit** delivers the live video stream to the viewer's browser using WebRTC.

### On-demand streaming

- The gateway **only publishes video while at least one authorized viewer is watching**.
- When all viewers leave, the gateway stops streaming after a short grace period (to handle brief page refreshes).
- This keeps bandwidth and cloud costs low.

### Latency

- Target: **under 2 seconds** from camera to browser (glass-to-glass).

### What is not included

- **No recording or playback** in the initial release. This may be added in a future phase with a separate approval process.
- **No snapshots** in the initial release.
- **No motion detection** in the initial release.

---

## 7. Privacy and Compliance Features

The system is designed to comply with Philippine data privacy law (RA 10173 / NPC guidelines).

| Feature | Purpose |
|---|---|
| **Privacy notice** | Shown to every user on first login and when updated. Acceptance is recorded. |
| **Bystander signage tracking** | Admins record that physical privacy signs are posted at each camera site. |
| **Audit trail** | Every privileged action is logged with tamper-evident cryptographic chaining. |
| **DPA artefact support** | Admins can generate and export compliance documents (ROPA, PIAs, processor DPAs, breach logs, retention policies, signage attestations). |
| **No recording in MVP** | Recording is explicitly excluded from the initial release to limit data exposure and privacy risk. |
| **Camera isolation** | Cameras are on a private network with no internet access. Camera credentials never leave the gateway. |
| **Minimal data collection** | The system collects only what is needed: login identity, access logs, camera assignments, and audit records. |

---

## 8. MVP Features vs Future Features

### MVP (initial release)

| Feature | Included |
|---|---|
| Live camera viewing (up to 2 cameras, expandable) | Yes |
| Camera dashboard with grid layouts (1×1, 2×1, 2×2) | Yes |
| Fullscreen viewing | Yes |
| Camera and gateway status indicators | Yes |
| Secure login with Google Workspace + Cloudflare Access | Yes |
| Role-based access control (RBAC) | Yes |
| Per-camera, per-user access control | Yes |
| Camera and gateway registration | Yes |
| Camera-to-gateway assignment | Yes |
| Gateway and camera health dashboard | Yes |
| Disable/retire cameras and gateways | Yes |
| Audit logs with tamper-evident hash chain | Yes |
| Signed audit export (JSONL) | Yes |
| Break-glass emergency admin (90-minute window) | Yes |
| Lost-MFA recovery (admin-mediated) | Yes |
| Privacy notice and acceptance tracking | Yes |
| Bystander signage attestation | Yes |
| Login history | Yes |
| Session management with immediate revocation | Yes |

### Pilot (second phase)

| Feature | Status |
|---|---|
| Viewer identity watermark on video | Planned |
| Alerting and notifications | Backend alert records and SMTP email foundation implemented; email disabled by default until SMTP settings are configured; frontend alerts UI still pending |
| Tamper detection with 5-minute verification | Planned |
| mTLS gateway certificates with rotation alerts | Planned |
| NVR integration (nvr_rtsp source type) | Planned |
| Suspicious login detection | Planned |
| Device posture enforcement for admins (WARP) | Included from MVP |
| Actor profile enrichment | Planned |
| Detection and incident workflow | Planned |
| Analyst notes and investigation timeline | Planned |
| Behavior baseline and actor risk scoring | Planned |

### Future (later phases)

| Feature | Status |
|---|---|
| Recording and playback | Future — requires separate approval (ADR-gated) |
| Snapshots | Future — requires separate approval (ADR-gated) |
| Motion detection | Future |
| Multi-site management | Future |
| Firmware inventory | Future |

For a full catalog of additional future feature ideas beyond these, see [Future Functionality Idea Catalog](cctv-future-functionality-features.md).

### Permanently not supported

These features will **never** be part of the system. This is a deliberate security decision.

| Feature | Reason |
|---|---|
| Webcam viewing/publishing | This is a CCTV system, not a video call app. Only registered IP cameras are allowed. |
| Phone camera publishing | Same reason — no user device cameras. |
| Browser camera/microphone access | The app will never request camera or microphone permissions from your browser. |
| Self-registration | All accounts are created by admins. |
| Self-service MFA reset | MFA resets must go through an admin to prevent social engineering. |

---

## 9. Non-Technical Summary

Panoptix is a secure website for watching live security camera feeds.

**For viewers:** You log in with your school Google account, and you see only the cameras you are assigned to. Video plays live in your browser with minimal delay. You do not need to install anything. The system never asks for your webcam or microphone.

**For admins:** You manage who can see which cameras, register new cameras and gateways, and review a full audit trail of everything that happens in the system. You can disable users or cameras instantly, and compliance documents are always ready for export.

**For the school:** Cameras stay on a private network and never touch the internet directly. All access goes through Cloudflare's security layer and Google Workspace login. Every action is logged. The system is designed from the ground up for Philippine data privacy compliance.

**What it is not:** This is not a video call app, a phone camera app, or a recording system. It is a purpose-built CCTV monitoring platform for live viewing of fixed IP cameras.
