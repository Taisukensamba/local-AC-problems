#!/usr/bin/env bash
set -euo pipefail

START=${1:-235}
END=${2:-320}
BASE_URL=${BASE_URL:-http://127.0.0.1:8000}

wait_sync() {
  while true; do
    running=$(python3 - <<PY
import json
import sys
import urllib.request

url = "${BASE_URL}/api/sync/status"
try:
    with urllib.request.urlopen(url, timeout=5) as res:
        raw = res.read().decode("utf-8")
except Exception:
    print("unknown")
    raise SystemExit(0)

try:
    s = json.loads(raw)
except json.JSONDecodeError:
    print("unknown")
    raise SystemExit(0)

print(str(s.get("running", False)).lower())
PY
)
    [ "$running" = "false" ] && break
    sleep 1
  done
}

for n in $(seq -w "$START" "$END"); do
  echo "sync tasks abc${n}"
  curl -s -X POST "$BASE_URL/api/sync" \
    -H 'Content-Type: application/json' \
    -d "{\"contest\": false, \"tasks\": true, \"submissions\": false, \"contest_ids\": [\"abc${n}\"]}" >/dev/null
  wait_sync
  sleep 1
  done
