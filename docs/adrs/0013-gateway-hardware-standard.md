# ADR 0013 - Gateway Hardware Standard

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: System Owner, Software Architect, Operations Owner
- **Supersedes**: None
- **Plan references**: Section 11.5; Section 12 stack table; Section 13.7; Section 13.8; Section 13.9; Section 20.14; ADR 0001; ADR 0012

## Context

The edge gateway is MVP-critical because browser publishing has been permanently removed (ADR 0009). The gateway ingests RTSP from IP cameras or NVRs, manages local camera credentials, and publishes to LiveKit using short-lived gateway-publish tokens.

For production sites, the gateway must sit physically on the same LAN/VLAN as the cameras. A cloud-hosted gateway cannot pull private RTSP streams without opening inbound camera network access, VPNs, or port forwards - all of which weaken the camera-plane isolation model.

The hardware standard must be simple enough for small-site deployment while strong enough to run `mediamtx`, the gateway agent, Docker, OS hardening, and future pilot features such as mTLS client certificates.

## Decision

**Production edge gateways use an on-site x86_64 NUC-class mini-PC running Ubuntu 22.04 LTS Server and a single pinned Docker image. Raspberry Pi-class ARM SBCs are not the production standard. Virtual/cloud servers are not used as production real-camera gateways. Any cloud-hosted dev/CI gateway is reserved for synthetic RTSP only and is never connected to real cameras.**

## Standard hardware class

| Spec | Minimum | Recommended | Notes |
|---|---|---|---|
| Form factor | NUC / mini-PC | Same | Beelink Mini S / Intel N100-class first procurement candidate; Intel NUC, MeLE Quieter, ASUS PN-series, Minisforum UM-series acceptable if they meet requirements |
| CPU | x86_64 quad-core, AES-NI | Intel N100/N305 or Ryzen 5xxx U-series | Single architecture, single Docker image |
| RAM | 8 GB | 16 GB | `mediamtx` + gateway agent + headroom |
| Storage | 128 GB SSD | 256 GB NVMe | OS + Docker; no recording on box |
| NIC | 1 x GbE | 2 x GbE | Two NICs preferred for camera VLAN isolation |
| Power | Standard mains | UPS-backed | UPS recommended for gateway + camera VLAN switch |
| OS | Ubuntu 22.04 LTS Server x86_64 | Same | No GUI; minimal install |
| Hostname | `cctv-gw-<site-slug>` | Same | Used as enrolment label |

## Software baseline

- One x86_64 Docker image shipped from CI.
- Image tag pinned per release; never `:latest`.
- `mediamtx` version pinned per ADR 0007.
- Gateway agent runs in the same image and handles token minting, heartbeat, camera status, and start/stop commands.
- Systemd unit: `cctv-gateway.service`.
- Dedicated Unix user: `cctv-gateway:cctv-gateway`, no shell, no sudo.
- Hardening:
  - `NoNewPrivileges=yes`
  - `ProtectSystem=strict`
  - `ProtectHome=yes`
  - `ReadWritePaths=/var/lib/cctv-gateway`
  - Docker `--read-only` where feasible
- Secrets file: `/etc/cctv-gateway/gateway.env`, mode `0600`, owner `cctv-gateway:cctv-gateway`, loaded via `EnvironmentFile=`.
- No GUI packages, no remote desktop, no SSH from WAN.
- SSH allowed only from the WARP-protected admin laptop subnet, if enabled.

## Network posture

- No inbound WAN ports.
- Gateway WAN side uses outbound TCP 443 only for:
  - `cctv-api` gateway API
  - Cloudflare Access service-token route
  - LiveKit publish path / TURN TLS fallback
  - OS and container image updates
- Gateway camera side pulls RTSP from cameras on the dedicated camera VLAN.
- Camera VLAN design follows ADR 0012.
- `mediamtx` HTTP API is disabled or bound to `127.0.0.1:9997` only.

## Dev/CI exception

The cloud-hosted dev/CI gateway, if used, is allowed only for dev/CI/staging with the `synthetic_rtsp_test_source` source type:

- It runs FFmpeg synthetic RTSP -> local `mediamtx` -> LiveKit.
- It is never connected to real cameras.
- It is never assigned a production site identity.
- Gateway boot script refuses to start synthetic FFmpeg when its identity indicates a production site.

This gives CI an end-to-end media path without violating the CCTV-only invariant or requiring physical hardware.

## Procurement guidance

Shortlist devices using this priority order:

1. Beelink Mini S / Intel N100-class or equivalent x86_64 mini-PC as the first procurement candidate.
2. x86_64 CPU with AES-NI.
3. 2 x GbE NICs if budget allows.
4. Fanless or low-noise design if installed in occupied areas.
5. SSD/NVMe storage, not eMMC.
6. Vendor availability and replacement lead time in the deployment region.
7. BIOS support for auto-power-on after power loss.
8. Compatible with Ubuntu 22.04 LTS without vendor drivers.

A UPS is strongly recommended when the camera VLAN switch is also UPS-backed. Without UPS, WAN or mains flaps can interrupt live monitoring; the system should show the camera as gateway-unavailable and alert after the 2-minute threshold.

## Why not Raspberry Pi as the standard?

Raspberry Pi-class ARM SBCs were considered and rejected as the production standard:

- Would require a second `arm64` container image and separate test matrix.
- Weaker AES-NI / crypto acceleration story compared with x86_64 mini-PCs.
- Less predictable storage reliability if booting from microSD.
- More fragile supply chain and enclosure/power variations.
- Many candidate sites already have or can procure x86_64 mini-PCs.

ARM is not banned. It may be used only if this ADR is reopened and a site-specific exception documents the image, testing, and support burden.

## Consequences

### Positive

- **Single production image**: one x86_64 Docker image simplifies CI, SBOM, signing, and incident response.
- **Stronger isolation**: on-site gateway can access the camera VLAN without exposing cameras to the internet.
- **Operational consistency**: identical OS, systemd unit, file paths, and hardening across sites.
- **Future-ready**: enough CPU/RAM/headroom for mTLS, certificate rotation, and additional health probes.

### Negative

- **Higher cost than SBCs**: NUC-class mini-PCs cost more than Raspberry Pi-class devices.
- **Physical deployment required**: someone must image, ship, install, and maintain the box.
- **Two-NIC preference narrows SKU choices**: some low-cost mini-PCs have only one NIC, requiring VLAN tagging.

### Risks accepted

- Low-cost mini-PC vendors may have variable BIOS/firmware quality. Mitigated by procurement shortlist testing before standardizing a SKU.

## Alternatives considered

### A. Cloud-hosted gateway for production

- **Rejected**: would require cameras/NVRs to expose RTSP to the internet or a VPN path into the site. This violates the camera-plane isolation model.

### B. Raspberry Pi / ARM SBC standard

- **Rejected as default**: adds multi-arch image complexity and reliability concerns. May be revisited only with a new ADR.

### C. One gateway per camera

- **Rejected for MVP**: increases hardware count and operational overhead. One gateway per site can handle the small MVP camera count; scale-out can be revisited for larger sites.

### D. Run gateway directly on camera/NVR firmware

- **Rejected**: vendor firmware is heterogeneous, poorly controlled, and hard to update. The gateway must be controlled infrastructure with reproducible images.

## Verification

- Site bring-up confirms hostname, OS version, Docker image digest, systemd hardening, secret-file permissions, and network posture.
- `mediamtx` API probe confirms API is disabled or loopback-only.
- Gateway enrolment confirms service-token or mTLS identity is stored only on the gateway.
- End-to-end test confirms gateway can publish assigned camera to LiveKit and viewer can subscribe with <2 s p95 latency.
- Quarterly review checks OS patch level and image digest against release manifest.

## References

- v4 plan Section 11.5 (Gateway identity and secret storage)
- v4 plan Section 12 (Technology Stack - edge gateway rows)
- v4 plan Section 13.7 (Synthetic RTSP test source)
- v4 plan Section 13.8 (Camera Site Hardware)
- v4 plan Section 13.9 (Camera Network Design)
- v4 plan Section 20.14 (Gateway lifecycle runbook)
- ADR 0001 (Plane separation)
- ADR 0012 (Camera network design)

