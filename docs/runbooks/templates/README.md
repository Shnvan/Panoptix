# Edge Gateway Service Templates

Docs-only service and environment templates for deploying the Panoptix edge gateway supervisor as a managed host service.

## Files

| Template | Purpose |
|----------|---------|
| `cctv-gateway.service.example` | Linux systemd unit file for the edge gateway supervisor |
| `gateway.env.example` | Environment file with placeholder-only values for gateway configuration |
| `Dockerfile.edge-agent.example` | Docker image template for the edge gateway (no EXPOSE, non-root user) |
| `docker-compose.edge-agent.example.yml` | Docker Compose template with no ports, external env file, read-only FS |
| `nssm-install.example.ps1` | Windows/NSSM service install script with placeholder values |

## Usage

These templates are reference artifacts for operator review. They are **not** installed or enabled by any automated process.

To use them on a target gateway host:

1. Review `docs/runbooks/edge-gateway-service.md` for the full operational runbook.
2. Copy and adapt the templates to the target host paths and credentials.
3. Complete all network security gates before enabling the service.
4. Do not commit real secrets, API keys, LiveKit credentials, RTSP passwords, or generated JWTs.

## Security Rules

- Real environment files must be stored outside the repository with mode `0600`.
- Do not expose RTSP, HLS, WebRTC, RTMP, or mediamtx API ports to WAN.
- Keep `PANOPTIX_MEDIA_PUBLISHER_MODE=stub` unless real publishing is explicitly approved.
- Rotate gateway credentials if they are exposed.
- See the runbook incident checklist for response procedures.

## Not Included

- Real credentials or production configuration values
- Automated installation scripts
- Production-ready Docker registry or CI/CD pipeline configuration
