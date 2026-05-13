# mediamtx Threat Model — Panoptix Edge NUC

## Role in Panoptix

mediamtx runs on the edge NUC and acts as the media relay:

1. **Ingress** — receives RTSP streams from IP cameras on the camera VLAN (typically `192.168.20.0/24`).
2. **Egress** — re-publishes streams to LiveKit Cloud via WebRTC/SRT over the internet-facing interface.
3. **Control** — exposes an HTTP admin API (port 9997 by default) used for path management and metrics.

The edge NUC sits at the boundary between the untrusted camera VLAN and the internet; mediamtx is therefore a high-value attack target.

## Threat Surface

| Surface | Protocol / Port | Exposure |
|---|---|---|
| RTSP ingress | TCP 8554 | Camera VLAN (should not reach internet) |
| Admin API | HTTP 9997 | Loopback or LAN — no auth by default |
| SRT egress | UDP 8890 | Outbound to LiveKit Cloud |
| WebRTC egress | UDP/TCP (ICE) | Outbound to LiveKit Cloud |
| Metrics endpoint | HTTP 9998 | Same host as admin API |

## Threats, Mitigations, and Residual Risks

| # | Threat | Existing Mitigation | Residual Risk |
|---|---|---|---|
| T1 | Unauthenticated RTSP ingest — attacker on camera VLAN injects a fake stream | Camera VLAN is isolated; no route from corp LAN by default | LAN-side attacker already on camera VLAN can publish arbitrary paths with no credential check |
| T2 | mediamtx admin API abuse — read stream URLs, add/remove paths, pivot | Admin API not publicly exposed; Cloudflare Access controls the control plane | Admin API bound to `0.0.0.0` in default config; any process on the NUC can reach it |
| T3 | Stream eavesdropping on camera VLAN | VLAN segmentation limits blast radius | No SRTP between camera and mediamtx; traffic is cleartext on the VLAN |
| T4 | Credential theft via mediamtx config file | Config file owned by service account | `publishUser`/`publishPass` stored in plaintext YAML; secrets management not enforced |
| T5 | No mTLS between edge agent and mediamtx | N/A — not yet implemented | Edge agent communicates with mediamtx admin API over plain HTTP; impersonation possible on the NUC |
| T6 | SRT/WebRTC egress hijack | LiveKit handles authentication on its end | SRT stream ID carries no Panoptix-level token; stolen stream ID could be replayed |

## Recommendations

1. **Disable the admin API in production** — set `api: no` in `mediamtx.yml`. Use the mediamtx CLI or restart-based config reload instead of the live API.
2. **Bind RTSP to the camera VLAN interface only** — set `rtspAddress: 192.168.20.1:8554` (or the NUC's VLAN IP) instead of `0.0.0.0:8554`.
3. **Enforce path-level publish authentication** — add `publishUser` and `publishPass` (or `publishIPs` allowlist) to every path entry. Consider JWT path tokens via the `externalAuthenticationURL` hook.
4. **Enable SRTP** — set `encryption: strict` on paths to encrypt media between mediamtx and WebRTC consumers.
5. **Implement mTLS between edge agent and mediamtx** — the bootstrap scaffold at `apps/cctv-edge/agent/src/panoptix_edge_agent/mtls_bootstrap.py` will issue a short-lived client certificate; wire it into the admin API HTTP client.
6. **Firewall RTSP port to camera VLAN only** — add an `nftables`/`iptables` rule on the NUC to drop RTSP SYNs not sourced from `192.168.20.0/24`.

## Out of Scope

Camera firmware vulnerabilities and LiveKit Cloud-side security are covered in the broader STRIDE model (`threat-model-stride.md`).
