# Panoptix Edge Gateway — NSSM service install template (Windows)
#
# This is a docs-only template with placeholder values.
# Do not run it without operator review, credential provisioning,
# and network security gates.
#
# Prerequisites:
#   - NSSM installed and on PATH (https://nssm.cc/)
#   - Python 3.12+ installed and on PATH
#   - Edge-agent package deployed to $AgentDir
#   - gateway.env placed at $EnvFile with appropriate permissions
#
# See docs/runbooks/edge-gateway-service.md for the full operational runbook.

# --- Configuration (replace placeholders before use) ---

$ServiceName = "cctv-gateway"
$AgentDir    = "C:\Panoptix\edge-agent"
$EnvFile     = "C:\Panoptix\config\gateway.env"
$LogDir      = "C:\Panoptix\logs"
$PythonExe   = "python"

# --- Safety checks ---

Write-Host "WARNING: Review all placeholder values before running this script."
Write-Host "WARNING: Do not commit real secrets, API keys, or credentials."
Write-Host ""

if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    Write-Error "NSSM is not installed or not on PATH."
    exit 1
}

if (-not (Test-Path $AgentDir)) {
    Write-Error "Agent directory not found: $AgentDir"
    exit 1
}

if (-not (Test-Path $EnvFile)) {
    Write-Error "Environment file not found: $EnvFile"
    exit 1
}

# Create log directory if it does not exist.
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# --- Install service ---

nssm install $ServiceName $PythonExe "-m panoptix_edge_agent.cli --supervise"
nssm set $ServiceName AppDirectory $AgentDir
nssm set $ServiceName AppStdout "$LogDir\cctv-gateway-stdout.log"
nssm set $ServiceName AppStderr "$LogDir\cctv-gateway-stderr.log"
nssm set $ServiceName AppRotateFiles 1
nssm set $ServiceName AppRotateBytes 10485760

# --- Environment ---
# NSSM can load environment from the service or from a wrapper.
# Option A: Set variables individually via nssm set AppEnvironmentExtra.
# Option B: Use a wrapper script that sources $EnvFile before starting Python.
#
# Example for Option A (one variable at a time):
#   nssm set $ServiceName AppEnvironmentExtra "PANOPTIX_API_BASE_URL=https://<backend-host>"
#   nssm set $ServiceName AppEnvironmentExtra +"PANOPTIX_GATEWAY_ID=<gateway-id>"
#
# The operator must decide which approach fits their deployment model.

Write-Host ""
Write-Host "Service '$ServiceName' installed."
Write-Host "Start with:  nssm start $ServiceName"
Write-Host "Status:       nssm status $ServiceName"
Write-Host "Logs:         $LogDir"
Write-Host ""
Write-Host "IMPORTANT: Verify Windows Firewall does not allow inbound WAN media/API ports."
Write-Host "IMPORTANT: Do not expose RTSP, HLS, WebRTC, RTMP, or mediamtx API to WAN."
