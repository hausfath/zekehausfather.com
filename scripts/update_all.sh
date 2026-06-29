#!/usr/bin/env bash
# Local refresh: regenerate the ERA5 chart data from the Climate Dashboard CSV,
# refresh the blog/media feeds, and (optionally) push to GitHub.
#
# Handy for a local cron entry, e.g. daily at 7am:
#   0 7 * * *  /path/to/Personal\ Website/scripts/update_all.sh >> /tmp/zh-site.log 2>&1
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[$(date)] Refreshing ERA5 data…"
python3 scripts/process_era5.py || echo "  (ERA5 source CSV not found — skipping)"

echo "[$(date)] Refreshing feeds…"
python3 scripts/update_feeds.py

echo "[$(date)] Refreshing publications…"
python3 scripts/update_publications.py

# Uncomment to auto-commit & push when run inside a git repo:
# if git rev-parse --git-dir >/dev/null 2>&1; then
#   git add site/data/*.json
#   git diff --staged --quiet || git commit -m "chore: refresh site data"
#   git push
# fi

echo "[$(date)] Done."
