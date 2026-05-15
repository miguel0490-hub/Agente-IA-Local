#!/usr/bin/env bash
# Volcado lógico de PostgreSQL (Docker Compose o URL directa).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups/postgres}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [[ -n "${DATABASE_URL:-}" ]]; then
  OUT="$BACKUP_DIR/superagente_${STAMP}.sql.gz"
  pg_dump "$DATABASE_URL" | gzip -9 > "$OUT"
  echo "Backup: $OUT"
elif docker compose ps postgres 2>/dev/null | grep -q running; then
  OUT="$BACKUP_DIR/superagente_${STAMP}.sql.gz"
  docker compose exec -T postgres pg_dump -U superagente superagente | gzip -9 > "$OUT"
  echo "Backup: $OUT"
else
  echo "Define DATABASE_URL o levanta el servicio postgres con docker compose."
  exit 1
fi

find "$BACKUP_DIR" -name '*.sql.gz' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
echo "Retención: ${RETENTION_DAYS} días"
