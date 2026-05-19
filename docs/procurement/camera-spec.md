# Camera and Gateway Procurement Specification

<!-- PE-FIX: Added camera procurement spec referenced by Phase 0 -->

This document records the minimum hardware/network requirements before buying or accepting cameras and gateway hardware.

## Camera requirements

| Requirement | Minimum | Reject if |
|---|---|---|
| RTSP | Documented RTSP URL support | No RTSP/NVR RTSP output. |
| Codec | H.264 at 720p/1080p, 15 fps | Proprietary-only stream. |
| Credentials | Unique local admin/viewer credentials | Shared fixed password or cloud-only account. |
| Network | Static IP or DHCP reservation | Requires internet route after setup. |
| Cloud/P2P | Can be disabled | Vendor cloud required for local stream. |
| ONVIF | Profile S/T preferred | ONVIF-only without RTSP spike approval. |
| Power | PoE preferred | Unstable power for intended site. |

## Gateway hardware requirements

| Component | Minimum | Recommended |
|---|---|---|
| Form factor | x86_64 NUC-class mini-PC | Intel N100/N305 or Ryzen U-series mini-PC |
| RAM | 8 GB | 16 GB |
| Storage | 128 GB SSD | 256 GB NVMe |
| NIC | 1 GbE | 2 GbE |
| OS | Ubuntu 22.04 LTS Server | Same |
| Power | Mains | UPS-backed with camera switch |

## Site network requirements

- Camera VLAN isolated from operator LAN.
- Cameras have no internet route.
- Gateway camera-side interface can reach cameras on RTSP 554.
- Gateway WAN-side interface can reach `cctv-api`, Cloudflare Access, and LiveKit over outbound 443.
- No inbound WAN port forwards to gateway.
- `mediamtx` API disabled or loopback-only.

## Acceptance test before purchase/use

| Test | Pass condition |
|---|---|
| RTSP pull | Gateway can pull stable stream for 30 minutes. |
| Cloud disabled | Camera still streams locally with vendor cloud/P2P disabled. |
| VLAN isolation | Camera cannot reach internet or operator LAN. |
| Gateway outbound | Gateway can establish outbound control WebSocket and LiveKit publish path. |
| Credential isolation | RTSP credential exists only on gateway, not browser/API/logs. |

## Candidate log

| Candidate | RTSP | H.264 | Local-only | VLAN fit | Price | Decision |
|---|---|---|---|---|---|---|
| First RTSP camera/NVR candidate | Verify | Verify | Verify | Verify | To quote | Pending procurement check |

> **Update 2026-05-13:** LiveKit Cloud account is provisioned (APAC region). Once camera hardware passes the acceptance test above, the full end-to-end path (camera → gateway FFmpeg → LiveKit Cloud → browser viewer) is ready for integration testing. No additional cloud accounts are needed.

## Candidate RTSP URL formats

These formats are **candidate examples only**. No camera brand/model is selected yet. The same brands and RTSP URL patterns are covered in the COMP 012 academic lab manual (see [Academic Manual Crosswalk](../reference/academic-manual-crosswalk.md)).

| Brand / family | Example RTSP URL format | Decision |
|---|---|---|
| Hikvision | `rtsp://192.168.1.10:554/Streaming/Channels/101` | Candidate only; test later |
| Dahua | `rtsp://192.168.1.10:554/cam/realmonitor?channel=1&subtype=0` | Candidate only; test later |
| Generic / Reolink | `rtsp://192.168.1.10:554/stream1` | Candidate only; test later |
| TP-Link | `rtsp://192.168.1.10:554/stream1` | Candidate only; test later |

Testing note: replace `192.168.1.10` with the camera's VLAN IP and add credentials only in the gateway secret/config file. Do not place real camera usernames, passwords, or RTSP URLs in browser code, API responses, logs, screenshots, or committed files.
