#!/usr/bin/env bash
set -euo pipefail

TS="$(date +%Y%m%d_%H%M%S)"

DB_CONTAINER="${DB_CONTAINER:-saas_db}"
DB_NAME="${DB_NAME:-saas}"
DB_USER="${DB_USER:-saas}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

OUT_DIR="${DB_DUMP_DIR:-backups}"


if [[ -z "$OUT_DIR" ]]; then
  if [[ -d "$DROPBOX_OUT_DIR" ]]; then
    OUT_DIR="$DROPBOX_OUT_DIR"
  else
    OUT_DIR="$DEFAULT_OUT_DIR"
  fi
fi

mkdir -p "$OUT_DIR"
OUT_FILE="${OUT_DIR}/moneyplanner_${TS}.dump"

# Unique temp file inside container for verification
VERIFY_TMP="/tmp/verify_${TS}_$$.dump"

cleanup() {
  # Best-effort cleanup; don't fail script if cleanup fails
  docker exec -i "$DB_CONTAINER" sh -c "rm -f '$VERIFY_TMP' >/dev/null 2>&1" || true
}
trap cleanup EXIT

echo "Dumping ${DB_NAME} from ${DB_CONTAINER} to ${OUT_FILE} ..."
# Important: DO NOT use -t with -Fc (binary). Use -i.
if ! docker exec -i "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc > "$OUT_FILE"; then
  echo "ERROR: pg_dump failed. The dump file may be incomplete: $OUT_FILE" >&2
  exit 1
fi

echo "Verifying dump archive (pg_restore -l)..."
docker cp "$OUT_FILE" "${DB_CONTAINER}:${VERIFY_TMP}" >/dev/null
docker exec -i "$DB_CONTAINER" sh -c "pg_restore -l '$VERIFY_TMP' > /dev/null"

echo "OK -> ${OUT_FILE}"
