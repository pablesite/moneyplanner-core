#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load per-machine config (ignored by git): scripts/.env
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

# Prefer DB_DUMP_DIR from scripts/.env, fallback to local backups/
OUT_DIR="${DB_DUMP_DIR:-${OUT_DIR:-backups}}"

LATEST="$(ls -1t "$OUT_DIR"/*.dump 2>/dev/null | head -n 1 || true)"

if [[ -z "$LATEST" ]]; then
  echo "No dump files found in $OUT_DIR/"
  exit 1
fi

echo "Latest dump found:"
echo "  $LATEST"
echo

read -r -p "Restore this dump? Type YES to continue: " CONFIRM
if [[ "$CONFIRM" != "YES" ]]; then
  echo "Aborted."
  exit 0
fi

echo "Starting restore..."

# Use the current bash if available; fallback to bash
BASH_BIN="${BASH:-bash}"
"$BASH_BIN" "$SCRIPT_DIR/db_restore.sh" "$LATEST"
