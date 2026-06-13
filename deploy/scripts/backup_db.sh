#!/usr/bin/env bash
# Nightly PostgreSQL backup with N-day retention.
# Invoked by cron — see deploy/crontab.txt.
# Reads DB creds from the project's .env. Stores gzipped dumps under ~/backups/db/.

set -euo pipefail

PROJECT_DIR=/home/vaishnavi/vaishnavi-backend
BACKUP_DIR=/home/vaishnavi/backups/db
RETENTION_DAYS=14
DATE=$(date +%Y%m%d_%H%M%S)
FILE="$BACKUP_DIR/vaishnavi_${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

# Source .env so DB_* are available. Use `set -a` to auto-export.
set -a
# shellcheck disable=SC1091
source "$PROJECT_DIR/.env"
set +a

PGPASSWORD="$DB_PASSWORD" pg_dump \
    -h "${DB_HOST:-127.0.0.1}" \
    -p "${DB_PORT:-5432}" \
    -U "$DB_USER" \
    --no-owner \
    --no-acl \
    "$DB_NAME" \
  | gzip -9 > "$FILE"

# Prune older than RETENTION_DAYS
find "$BACKUP_DIR" -name 'vaishnavi_*.sql.gz' -mtime "+$RETENTION_DAYS" -delete

SIZE=$(du -h "$FILE" | cut -f1)
echo "[$(date +'%Y-%m-%d %H:%M:%S')] DB backup OK: $FILE ($SIZE)"
