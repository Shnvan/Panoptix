#!/usr/bin/env bash
# restore-drill.sh — Panoptix backup restore drill
# Tests that a backup stored in Cloudflare R2 can be successfully restored.
# Required env vars : R2_BUCKET, TARGET_DB_URL (omit for dry-run)
# Optional env vars : BACKUP_FILE (defaults to most recent .dump in the bucket)

set -euo pipefail

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------
usage() {
  echo "Usage: R2_BUCKET=<bucket> [BACKUP_FILE=<file>] [TARGET_DB_URL=<url>] $0"
  echo "  R2_BUCKET      required — rclone remote path, e.g. 'panoptix-backups'"
  echo "  BACKUP_FILE    optional — specific .dump file; defaults to latest"
  echo "  TARGET_DB_URL  optional — postgres DSN; omit to perform a dry-run only"
  exit 1
}

for cmd in rclone pg_restore psql; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "ERROR: '$cmd' not found in PATH."; exit 1; }
done

[[ -z "${R2_BUCKET:-}" ]] && { echo "ERROR: R2_BUCKET is not set."; usage; }

TMPFILE="/tmp/panoptix-restore-drill-$$.dump"

# ---------------------------------------------------------------------------
# Step 1: List available backups
# ---------------------------------------------------------------------------
echo "==> Listing backups in r2:${R2_BUCKET} ..."
rclone ls "r2:${R2_BUCKET}"

# ---------------------------------------------------------------------------
# Step 2: Resolve backup file
# ---------------------------------------------------------------------------
if [[ -z "${BACKUP_FILE:-}" ]]; then
  echo "==> BACKUP_FILE not set — picking most recent .dump ..."
  BACKUP_FILE=$(rclone ls "r2:${R2_BUCKET}" | grep '\.dump$' | sort -k2 | tail -n1 | awk '{print $2}')
  [[ -z "$BACKUP_FILE" ]] && { echo "ERROR: No .dump files found in r2:${R2_BUCKET}"; exit 1; }
  echo "    Selected: ${BACKUP_FILE}"
fi

# ---------------------------------------------------------------------------
# Step 3: Download backup
# ---------------------------------------------------------------------------
echo "==> Downloading r2:${R2_BUCKET}/${BACKUP_FILE} -> ${TMPFILE} ..."
rclone copy "r2:${R2_BUCKET}/${BACKUP_FILE}" "$(dirname "$TMPFILE")" \
  --transfers=1 -v
mv "$(dirname "$TMPFILE")/${BACKUP_FILE}" "$TMPFILE"

# ---------------------------------------------------------------------------
# Step 4: Restore (or dry-run)
# ---------------------------------------------------------------------------
if [[ -z "${TARGET_DB_URL:-}" ]]; then
  echo "Dry-run: TARGET_DB_URL not set — skipping actual restore."
  rm -f "$TMPFILE"
  exit 0
fi

echo "==> Restoring into TARGET_DB_URL ..."
pg_restore --clean --no-owner -d "$TARGET_DB_URL" "$TMPFILE"

# ---------------------------------------------------------------------------
# Step 5: Smoke test
# ---------------------------------------------------------------------------
echo "==> Smoke-test: checking user count ..."
psql "$TARGET_DB_URL" -c "SELECT COUNT(*) AS user_count FROM users;"

# ---------------------------------------------------------------------------
# Step 6: Cleanup
# ---------------------------------------------------------------------------
rm -f "$TMPFILE"
echo "==> Restore drill completed successfully."
