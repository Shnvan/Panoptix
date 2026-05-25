#!/usr/bin/env bash
# Panoptix encrypted R2 restore drill wrapper.
# Runs the Python operator job that downloads the latest .dump.age backup,
# decrypts it locally, validates it with pg_restore --list, and optionally
# restores into an isolated target database.

set -euo pipefail

usage() {
  echo "Usage: AGE_IDENTITY_FILE=<path> [TARGET_DB_URL=<isolated-db-url>] $0"
  echo "  AGE_IDENTITY_FILE  required local age private identity file"
  echo "  TARGET_DB_URL      optional isolated Postgres DSN; omit for dry-run validation"
  exit 1
}

[[ -z "${AGE_IDENTITY_FILE:-}" ]] && { echo "ERROR: AGE_IDENTITY_FILE is not set."; usage; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_DIR="${REPO_ROOT}/apps/api"

cd "${API_DIR}"

if [[ -z "${TARGET_DB_URL:-}" ]]; then
  python -m cctv_api.jobs.restore_drill_r2 --age-identity-file "${AGE_IDENTITY_FILE}"
else
  python -m cctv_api.jobs.restore_drill_r2 \
    --age-identity-file "${AGE_IDENTITY_FILE}" \
    --target-database-url "${TARGET_DB_URL}"
fi
