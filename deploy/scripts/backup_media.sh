#!/usr/bin/env bash
# Nightly media-folder sync to a backup mount. Mirror with --delete so
# removed media stays removed in the backup (no accumulating cruft).
#
# For offsite: layer an rclone job on top of /home/vaishnavi/backups/
# (S3 / Backblaze B2 / Google Drive). See deploy/DEPLOY.md.

set -euo pipefail

SRC=/home/vaishnavi/vaishnavi-backend/media/
DST=/home/vaishnavi/backups/media/

mkdir -p "$DST"

rsync -a --delete --human-readable "$SRC" "$DST" > /dev/null

SIZE=$(du -sh "$DST" | cut -f1)
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Media backup OK: $DST ($SIZE total)"
