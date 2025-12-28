#!/usr/bin/env bash
set -euo pipefail

SLEEP_SEC=${SLEEP_SEC:-2}

run_for_category() {
  local category=$1
  local slugs
  slugs=$(python3 scripts/list_contests.py --category "$category")
  if [ -z "$slugs" ]; then
    return 0
  fi
  python3 scripts/calc_difficulty.py \
    --category "$category" \
    --continue-on-error \
    --sleep "$SLEEP_SEC" \
    --slugs $slugs
}

run_for_category "abc"
run_for_category "arc"
run_for_category "agc"
