#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load per-machine config (ignored by git): scripts/.env
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

FILE="${1:-}"
if [[ -z "$FILE" ]]; then
  echo "Usage: scripts/db_restore.sh /path/to/your_dump.dump"
  exit 1
fi

if [[ ! -f "$FILE" ]]; then
  echo "File not found: $FILE"
  exit 1
fi

DB_CONTAINER="${DB_CONTAINER:-saas_db}"
DB_NAME="${DB_NAME:-saas}"
DB_USER="${DB_USER:-saas}"

# Prefer DB_DUMP_DIR from scripts/.env, fallback to OUT_DIR, then backups/
OUT_DIR="${DB_DUMP_DIR:-${OUT_DIR:-backups}}"

mkdir -p "$OUT_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
TMP_IN_CONTAINER="/tmp/moneyplanner_restore_${TS}_$$.dump"

cleanup() {
  docker exec -i "$DB_CONTAINER" sh -c "rm -f '$TMP_IN_CONTAINER' >/dev/null 2>&1" || true
}
trap cleanup EXIT

echo "Copying dump into container..."
docker cp "$FILE" "${DB_CONTAINER}:${TMP_IN_CONTAINER}"

echo "Validating dump archive (pg_restore -l)..."
docker exec -i "$DB_CONTAINER" sh -c "pg_restore -l '$TMP_IN_CONTAINER' > /dev/null"
echo "Dump is valid."

# Safety backup BEFORE destructive operations
SAFETY="${OUT_DIR}/pre_restore_${TS}.dump"
echo "Creating safety backup -> ${SAFETY}"
docker exec -i "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$SAFETY"
echo "Safety backup created."

echo "Terminating connections..."
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" <<'SQL'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = current_database()
  AND pid <> pg_backend_pid();
SQL

echo "Reset schema public..."
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO public;
SQL

echo "Restoring from file inside container..."
docker exec -i "$DB_CONTAINER" sh -c "pg_restore -U '$DB_USER' -d '$DB_NAME' --no-owner --no-privileges '$TMP_IN_CONTAINER'"

echo "Restarting backend..."
docker compose restart backend

echo "Restore OK."
