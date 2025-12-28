#!/usr/bin/env bash
set -euo pipefail

MODE=${1:-update}
BASE_URL=${BASE_URL:-http://127.0.0.1:8000}
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

post_sync() {
  local payload=$1
  curl -s -X POST "$BASE_URL/api/sync" \
    -H 'Content-Type: application/json' \
    -d "$payload" >/dev/null
}

post_sync_cf() {
  local endpoint=$1
  curl -s -X POST "$BASE_URL/api/sync/codeforces/${endpoint}" >/dev/null
}

list_contests_by_prefix() {
  local prefix=$1
  python3 - <<PY
from db.schema import connect
from db.queries import list_contest_uids
from oj.atcoder import contest_id_from_uid, atcoder_oj

conn = connect()
try:
    contest_uids = list_contest_uids(conn, atcoder_oj.name)
finally:
    conn.close()

contests = [contest_id_from_uid(uid) for uid in contest_uids]
print(" ".join([cid for cid in contests if cid.startswith("${prefix}")]))
PY
}

has_sync_state() {
  python3 - <<PY
from db.schema import connect
conn = connect()
try:
    row = conn.execute("SELECT COUNT(*) FROM sync_state").fetchone()
finally:
    conn.close()
print("true" if row and row[0] > 0 else "false")
PY
}

wait_sync() {
  while true; do
    output=$(python3 - <<PY
import json
import sys
import urllib.request

url = "${BASE_URL}/api/sync/status"
try:
    with urllib.request.urlopen(url, timeout=5) as res:
        raw = res.read().decode("utf-8")
except Exception as exc:
    print(f"progress: status error {exc}")
    print("RUNNING=unknown")
    raise SystemExit(0)

try:
    s = json.loads(raw)
except json.JSONDecodeError:
    print(f"progress: status invalid head={raw[:120]}")
    print("RUNNING=unknown")
    raise SystemExit(0)

progress = s.get("progress") or {}
phase = progress.get("phase")
if not phase:
    print("progress: none")
    print(f"RUNNING={str(s.get('running', False)).lower()}")
    raise SystemExit(0)

running = s.get("running")
if not running:
    print(f"progress: {phase} done")
    print("RUNNING=false")
    raise SystemExit(0)

total = progress.get("total") or 0
done = progress.get("done") or 0
current = progress.get("current")
if total:
    pct = int(done * 100 / total)
    msg = f"progress: {phase} {done}/{total} ({pct}%)"
else:
    msg = f"progress: {phase}"
if current:
    msg += f" current={current}"
print(msg)
print("RUNNING=true")
PY
)
    running=$(printf "%s" "$output" | tail -n 1 | cut -d= -f2)
    printf "%s\n" "$output" | sed '$d'
    if [ "$running" = "false" ]; then
      break
    fi
    if [ "$running" = "unknown" ]; then
      sleep 5
      continue
    fi
    sleep 5
  done
}

if [ "$MODE" = "init" ]; then
  has_state=$(has_sync_state)
  post_sync '{"contest": true, "tasks": false, "submissions": false}'
  wait_sync
  post_sync '{"contest": false, "tasks": true, "submissions": false}'
  wait_sync
  SLEEP_SEC=2 bash "$SCRIPT_DIR/calc_difficulty_all.sh"
  python3 "$SCRIPT_DIR/import_difficulty.py"
  if [ "$has_state" = "true" ]; then
    post_sync '{"contest": false, "tasks": false, "submissions": true, "mode": "cookie", "submissions_incremental": true}'
  else
    post_sync '{"contest": false, "tasks": false, "submissions": true, "mode": "cookie"}'
  fi
  wait_sync
  post_sync_cf "problems"
  post_sync_cf "contests"
  post_sync_cf "submissions"
else
  post_sync '{"contest": true, "tasks": false, "submissions": false}'
  wait_sync
  post_sync '{"contest": false, "tasks": true, "submissions": false, "tasks_incremental": true}'
  wait_sync
  SLEEP_SEC=2 bash "$SCRIPT_DIR/calc_difficulty_all.sh"
  python3 "$SCRIPT_DIR/import_difficulty.py"
  post_sync '{"contest": false, "tasks": false, "submissions": true, "mode": "cookie", "submissions_incremental": true}'
  wait_sync
  post_sync_cf "problems"
  post_sync_cf "submissions"
fi
