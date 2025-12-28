#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:8000}

if [ $# -lt 1 ]; then
  echo "usage: $0 <contest_id> [contest_id...]" >&2
  exit 1
fi

payload=$(python3 - "$@" <<'PY'
import json
import sys

contest_ids = sys.argv[1:]
print(json.dumps({
    "contest": False,
    "tasks": True,
    "submissions": True,
    "mode": "cookie",
    "submissions_incremental": True,
    "contest_ids": contest_ids,
}))
PY
)

curl -s -X POST "$BASE_URL/api/sync" \
  -H 'Content-Type: application/json' \
  -d "$payload" >/dev/null

echo "queued sync for: $*"
