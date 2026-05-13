# Academic Lab Manual Crosswalk (COMP 012)

This document maps concepts from the professor's **IP Camera Network Setup Manual** (COMP 012 — Network Administration, PUP Sta. Rosa) to the Panoptix production system. It is intended for team members who completed the academic lab and need to understand how those concepts translate (or diverge) in the production codebase.

---

## Shared Foundations

These concepts from the lab manual are directly applicable to Panoptix:

| Lab Concept | Panoptix Equivalent | Where in Project |
|---|---|---|
| IP camera as RTSP video source | Edge gateway pulls RTSP from camera/NVR | `docs/procurement/camera-spec.md` |
| Hikvision RTSP URL (`/Streaming/Channels/101`) | Candidate RTSP format in procurement spec | `docs/procurement/camera-spec.md` |
| Dahua RTSP URL (`/cam/realmonitor?channel=1`) | Candidate RTSP format in procurement spec | `docs/procurement/camera-spec.md` |
| Reolink/Generic RTSP URL (`/stream1`) | Candidate RTSP format in procurement spec | `docs/procurement/camera-spec.md` |
| TP-Link RTSP URL (`/stream1`) | Candidate RTSP format in procurement spec | `docs/procurement/camera-spec.md` |
| FFmpeg converting RTSP to playable format | Gateway FFmpeg republishes RTSP to LiveKit | `docs/runbooks/edge-gateway-service.md` |
| Static IP assignment for camera | Gateway and camera use static IPs or DHCP reservation | `docs/procurement/camera-spec.md` |
| Ping test for camera reachability | Health checks and gateway heartbeat | `MANUAL_TESTING.md` §5.1 |
| Network switch in star topology | Camera VLAN uses switch infrastructure | `docs/procurement/camera-spec.md` §Site network requirements |
| Troubleshooting symptom/cause/solution | Runbooks for gateway, deploy, and access issues | `docs/runbooks/` |

---

## Conceptual Upgrades (Same Idea, Production Implementation)

| Lab Approach | Panoptix Approach | Why Different |
|---|---|---|
| Flask `app.run(debug=True)` | FastAPI + Uvicorn behind Cloudflare Access | Production needs async I/O, type safety, auto-generated OpenAPI docs |
| Direct camera MJPEG in `<img src>` | LiveKit JS SDK WebRTC viewer | Separate media plane; camera never exposed to browser |
| Snapshot polling (`snapshot.jpg?t=...`) | Real-time WebRTC via LiveKit Cloud | Lower latency, no server-side storage, scalable |
| Single flat LAN (`192.168.1.0/24`) | Camera VLAN isolated from operator LAN | Prevents lateral movement if camera is compromised |
| No authentication | Cloudflare Access → JWT → CSRF → RBAC/ACL | Multi-operator system with deny-by-default authorization |
| Camera credentials in HTML/URLs | Credentials locked to edge gateway only | Security invariant: credentials never reach browser/API/logs |
| Local PC hosting (`192.168.1.20:5000`) | Railway cloud + managed services | Redundancy, DDoS protection, no single point of failure |
| Manual `python app.py` startup | Docker + CI/CD + health checks + rollback runbooks | Repeatable, monitored, recoverable deployments |

---

## Lab Patterns Panoptix Explicitly Rejects

These patterns from the manual are **forbidden** in Panoptix by architectural invariant:

| Lab Pattern | Panoptix Rule | Invariant |
|---|---|---|
| Browser directly fetching camera MJPEG/HTTP | Browser connects only to `/api/v1/*` and LiveKit Cloud | REQ-SEC-01: origin non-exposure |
| `app.run(host='0.0.0.0', debug=True)` | Debug mode disabled; production auth guardrails reject unsafe config | §0 Locked Constraints |
| Camera web UI accessible from operator PC | Camera VLAN isolated; camera web UI on separate network | §13.9 Camera Network Design |
| No session management | JWT sessions with idle + absolute timeouts | §11 Authentication |
| No audit logging | Every state change recorded in HMAC-chained audit log | §15 Audit Architecture |
| Single camera only | System supports ≥2 cameras; extensible to many | §1 Project Understanding |

---

## Lab Concepts with No Panoptix Equivalent

These lab exercises are academic-only and do not map to production features:

| Lab Feature | Panoptix Stance |
|---|---|
| HLS.js player in HTML | Panoptix uses LiveKit JS SDK (WebRTC), not HLS, for browser playback |
| `ffmpeg -f hls -hls_time 2 ... static/stream.m3u8` | FFmpeg runs on the gateway to republish to LiveKit, not to generate HLS segments for direct serving |
| Direct camera access from web server PC | Web server (Railway) has no direct camera access; only the on-site gateway does |

---

## Quick Reference: "I Learned X in the Lab, Where Is It in Panoptix?"

| "In the lab we..." | "In Panoptix..." |
|---|---|
| "...set the camera IP to `192.168.1.10`" | "...the gateway discovers or is configured with the camera's static IP; the API stores camera records with `source_type='rtsp'` and a `livekit_room_name`" |
| "...used `rtsp://192.168.1.10:554/stream1`" | "...the gateway stores the RTSP URL in its local secret config; the API never sees the full URL or credentials" |
| "...ran `python app.py` to start the server" | "...`docker build` produces an image; Railway deploys it; health checks verify it is running" |
| "...opened `http://192.168.1.20:5000` in a browser" | "...navigate to `https://staging.panoptix.site`; Cloudflare Access handles login; the API verifies the JWT" |
| "...refreshed `snapshot.jpg` every second" | "...the browser subscribes to a LiveKit room; the gateway publishes the RTSP stream to that room" |
| "...pinged the camera to check connectivity" | "...the deep health endpoint checks `db`, `livekit`, and `gateway` status; the gateway sends heartbeats" |
| "...troubleshooted by checking cables and IPs" | "...follow `docs/runbooks/gateway-control-channel.md` for gateway issues and `MANUAL_TESTING.md` for API issues" |

---

## For Instructors

If you are evaluating this project against the COMP 012 curriculum, the following lab competencies are demonstrated at an advanced level:

- **IP addressing and subnetting** → Static IP plan, VLAN design, DHCP reservation strategy
- **Physical topology (star)** → Camera VLAN + operator LAN separation
- **RTSP stream configuration** → Gateway FFmpeg ingest, LiveKit room model
- **Basic web serving (Flask)** → Production FastAPI with OpenAPI, Pydantic, async I/O
- **Connectivity testing (ping)** → Automated health probes, deep health, external monitoring
- **Troubleshooting** → Structured runbooks with rollback procedures

Additional competencies not covered in the lab but demonstrated here:
- Zero Trust identity (Cloudflare Access)
- Role-based access control and ACLs
- Audit logging and tamper evidence
- CI/CD and supply chain security
- Cloud-native architecture and managed services
