# ADR 0012 â€” Camera Network Design

- **Status**: Accepted
- **Date**: 2026-05-07
- **Decision-makers**: Network Administrator, Software Architect, System Owner
- **Supersedes**: None
- **Plan references**: Â§10.1; Â§11.5; Â§13.8; Â§13.9; Â§18.2 T-61/T-62; Â§20.14; ADR 0001; ADR 0013

## Context

Production cameras are IP cameras or NVRs that expose RTSP streams on a local site network. These devices are often weakly secured, infrequently patched, and unsuitable for direct internet exposure. Camera credentials are highly sensitive because they grant access to live video feeds.

The system architecture isolates camera ingest into a **camera plane**: an on-site gateway pulls RTSP from cameras and publishes to LiveKit using short-lived gateway-publish tokens. To preserve that isolation, cameras must not share the operator's general LAN and must not have a route to the internet.

## Decision

**Every production site uses a dedicated camera VLAN isolated from the operator LAN and the internet. The gateway is the only bridge between the camera VLAN and the WAN, and that bridge is protocol-restricted: RTSP/ICMP on the camera side, outbound HTTPS/WebRTC on the WAN side, and no inbound WAN ports.**

## Reference topology

```text
                 [ Internet / WAN ]
                        |
              Operator router / firewall
                        |
          +-------------+-------------+
          |                           |
  Operator LAN                    Gateway WAN iface
  192.168.1.0/24                 DHCP / site LAN IP
                                      |
                         [ cctv gateway mini-PC ]
                                      |
                         Gateway camera iface
                         192.168.10.2/24
                                      |
                           Camera VLAN switch
                           192.168.10.0/24
                                      |
                         IP cameras / NVRs
```

Example site addressing:

| Element | Setting |
|---|---|
| Camera VLAN | `192.168.10.0/24` (example; per-site assignment) |
| Operator LAN | `192.168.1.0/24` (example) |
| Gateway camera-side interface | `192.168.10.2/24`, no default gateway |
| Gateway WAN-side interface | DHCP from operator router |
| Camera default gateway | None, or VLAN-local only; no internet route |

Actual subnets are assigned per site and recorded in the private site plan.

## NIC model

### Preferred: two physical NICs

The production standard is a two-NIC gateway where available:

- NIC 1: camera VLAN switch
- NIC 2: operator LAN / WAN

This gives physical separation, simple troubleshooting, and easier audit evidence.

### Acceptable: single NIC with VLAN tagging

A single-NIC gateway is acceptable only if the switch is VLAN-aware and ACLs enforce the same isolation:

- Tagged camera VLAN sub-interface on the gateway
- Untagged or tagged WAN/operator VLAN as configured by the site
- Switch ACL blocks camera VLAN â†” operator LAN and camera VLAN â†’ internet

Single-NIC deployments require an explicit site-network note in the private site plan.

## Firewall policy

| Direction | From | To | Allowed |
|---|---|---|---|
| Gateway â†’ WAN | Gateway WAN iface | LiveKit Cloud, `cctv-api`, CF Access endpoints, Ubuntu/Docker update endpoints | TCP 443 only |
| WAN â†’ Gateway | Any | Gateway | **None** â€” no port forwards, no NAT loopback |
| Cameras â†’ Gateway | Camera VLAN | Gateway camera iface | TCP 554 (RTSP) + ICMP only |
| Gateway â†’ Cameras | Gateway camera iface | Cameras | TCP 554 + ICMP only |
| Camera VLAN â†” Operator LAN | Any | Any | **Blocked at switch/firewall** |
| Camera VLAN â†’ Internet | Cameras | Any | **Blocked** â€” no route |
| Operator LAN â†’ Cameras | Operator devices | Cameras | **Blocked by default**; temporary maintenance exception only |

Temporary camera maintenance exceptions must be time-boxed, documented, and removed after use.

## Credential handling

Camera credentials are stored only on the gateway:

- `mediamtx.yml` or gateway secret file mode `0600`
- Owned by `cctv-gateway:cctv-gateway`
- Never stored in `cctv-api`
- Never returned by API responses
- Never written to audit payloads or application logs

The control plane stores only camera metadata, gateway assignments, and authorization state. It never stores RTSP passwords.

## Site bring-up checklist

1. Inventory cameras: model, serial, RTSP path, ONVIF profile support.
2. Assign per-site camera VLAN subnet.
3. Configure switch VLAN and ACLs.
4. Connect gateway camera-side interface to camera VLAN.
5. Connect gateway WAN-side interface to operator LAN / WAN.
6. Verify gateway can pull RTSP from each camera.
7. Verify cameras cannot reach `8.8.8.8` or any internet endpoint.
8. Verify cameras cannot reach operator workstations.
9. Verify operator workstations cannot reach cameras except during documented maintenance window.
10. Verify gateway can reach `cctv-api` and LiveKit over outbound TCP 443.
11. Verify no inbound WAN ports are open to the gateway.
12. Verify `mediamtx` HTTP API is disabled or bound to `127.0.0.1:9997` only.
13. Enrol gateway via admin UI.
14. Confirm end-to-end viewer subscription latency <2 s p95.
15. Confirm bystander signage attestation exists for the site.

## Consequences

### Positive

- **Camera hardening by isolation**: cameras have no internet path and cannot reach operator devices.
- **Credential containment**: RTSP passwords remain local to the gateway.
- **No inbound WAN exposure**: the gateway does not require static IPs, port forwarding, or exposed RTSP endpoints.
- **Operationally simple**: two-NIC mini-PC + VLAN switch is straightforward for small sites.

### Negative

- **Network setup required per site**: VLAN configuration may require access to managed switches or router/firewall admin.
- **Two-NIC hardware preferred**: may affect gateway SKU selection and cost.
- **Camera maintenance friction**: direct camera web UI access is blocked by default; maintenance windows are required.

### Risks accepted

- Some low-cost sites may lack managed switches. Single-NIC VLAN tagging is accepted as a fallback if equivalent ACLs are enforced and documented.

## Alternatives considered

### A. Cameras on the operator LAN

- **Rejected**: cameras could be reached by compromised operator workstations and could reach other LAN devices. This violates camera-plane isolation.

### B. Cameras with direct internet access

- **Rejected**: direct internet access exposes weak camera firmware and risks outbound vendor cloud telemetry. Cameras must have no internet route.

### C. Port-forward RTSP from cameras to the internet

- **Rejected**: unauthenticated or weakly authenticated RTSP over the internet is unacceptable. The system uses outbound gateway publish to LiveKit instead.

### D. VPN from cloud app directly into camera VLAN

- **Rejected for MVP**: gives the cloud control plane a network path to camera devices and increases blast radius. The gateway should be the only component that touches RTSP.

## Verification

- **T-61**: gateway hardening / network probe confirms `mediamtx` API not reachable from camera VLAN or WAN.
- **T-62**: API responses do not leak RTSP credentials.
- **Site bring-up checklist**: verifies camera internet block, operator LAN isolation, gateway outbound-only model, and end-to-end media flow.
- **Quarterly site verification**: repeats basic network isolation checks.

## References

- v4 plan Â§10.1 (Camera plane diagram)
- v4 plan Â§11.5 (Gateway identity / secret storage)
- v4 plan Â§13.8 (Camera Site Hardware)
- v4 plan Â§13.9 (Camera Network Design)
- v4 plan Â§20.14 (Gateway lifecycle runbook)
- ADR 0001 (Plane separation)
- ADR 0013 (Gateway hardware standard)

