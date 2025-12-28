from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.loader import load_config
from crawler.standings import get_standings

LO_CLIP = -1000.0
HI_CLIP = 5000.0
ITERATIONS = 70
LOW_SAMPLE_THRESHOLD = 30
EXP_CLIP = 50.0
SLEEP_SEC = 2
BASE_DIR = Path("json")
PROBLEM_MODELS_PATH = Path("data/problem-models.json")


def _prob_1pl(rating: float, difficulty: float) -> float:
    k = math.log(10.0) / 400.0
    x = k * (difficulty - rating)
    if x > EXP_CLIP:
        return 0.0
    if x < -EXP_CLIP:
        return 1.0
    return 1.0 / (1.0 + math.exp(x))


def estimate_difficulty_1pl(
    ratings: list[float],
    solved01: list[int],
    *,
    lo_clip: float = LO_CLIP,
    hi_clip: float = HI_CLIP,
    iterations: int = ITERATIONS,
    low_sample_threshold: int = LOW_SAMPLE_THRESHOLD,
) -> tuple[float | None, list[str]]:
    n = len(ratings)
    m = sum(solved01)
    flags: list[str] = []
    if n == 0:
        return None, ["NO_DATA"]
    if n < low_sample_threshold:
        flags.append("LOW_SAMPLE")
    if m == 0:
        return hi_clip, flags + ["NO_AC"]
    if m == n:
        return lo_clip, flags + ["ALL_AC"]

    lo = lo_clip
    hi = hi_clip
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        expected = 0.0
        for rating in ratings:
            expected += _prob_1pl(rating, mid)
        if expected > m:
            lo = mid
        else:
            hi = mid
    estimate = (lo + hi) / 2.0
    if not math.isfinite(estimate):
        return None, flags + ["INVALID_ESTIMATE"]
    return estimate, flags


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2 == 1:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _rating_summary(ratings: list[float]) -> dict:
    if not ratings:
        return {"min": None, "median": None, "max": None}
    return {
        "min": min(ratings),
        "median": _median(ratings),
        "max": max(ratings),
    }


def _load_standings(contest_slug: str, contest_category: str) -> dict:
    path = BASE_DIR / contest_category / f"{contest_slug}.json"
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    config = load_config()
    return get_standings(
        contest_slug,
        contest_category,
        base_dir=BASE_DIR,
        cookie_jar_path=BASE_DIR / "cookies.lwp",
        revel_session=config.atcoder.cookie.revel_session,
        sleep_sec=SLEEP_SEC,
    )


def _filter_participants(data: dict, rated_only: bool) -> list[tuple[float, dict]]:
    participants = []
    for row in data.get("StandingsData", []) or []:
        if row.get("UserIsDeleted"):
            continue
        if row.get("IsTeam"):
            continue
        if rated_only and not row.get("IsRated"):
            continue
        rating = row.get("OldRating")
        if rating is None:
            continue
        try:
            rating_value = float(rating)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(rating_value) or rating_value == 0:
            continue
        task_results = row.get("TaskResults") or {}
        participants.append((rating_value, task_results))
    return participants


def _task_keys(data: dict) -> list[str]:
    keys = []
    for entry in data.get("TaskInfo", []) or []:
        key = entry.get("TaskScreenName")
        if key:
            keys.append(key)
    return keys


def _estimate_for_contest(
    contest_slug: str,
    contest_category: str,
    rated_only: bool,
    models: dict,
    *,
    force: bool,
) -> tuple[dict, int]:
    out_path = BASE_DIR / "difficulty" / contest_category / f"{contest_slug}.json"
    if out_path.exists() and not force:
        return {}, 0
    data = _load_standings(contest_slug, contest_category)
    participants = _filter_participants(data, rated_only)
    ratings = [rating for rating, _ in participants]
    tasks = {}
    for task_key in _task_keys(data):
        solved01 = []
        for _, results in participants:
            res = results.get(task_key) or {}
            solved01.append(1 if res.get("Status") == 1 else 0)
        difficulty, flags = estimate_difficulty_1pl(ratings, solved01)
        if difficulty is not None:
            difficulty = int(round(difficulty))
        tasks[task_key] = {
            "difficulty": difficulty,
            "n": len(ratings),
            "ac": sum(solved01),
            "flags": flags,
        }
    imported = 0
    if models:
        imported = _apply_models_to_tasks(tasks, models)
        if imported:
            print(f"imported {imported} from problem-models", file=sys.stderr)
    payload = {
        "contest_slug": contest_slug,
        "contest_category": contest_category,
        "generated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "rated_only": rated_only,
        "participants_used": len(ratings),
        "rating_summary": _rating_summary(ratings),
        "tasks": tasks,
    }
    return payload, imported


def _write_output(
    payload: dict,
    contest_slug: str,
    contest_category: str,
    *,
    force: bool,
) -> Path | None:
    out_dir = BASE_DIR / "difficulty" / contest_category
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{contest_slug}.json"
    if path.exists() and not force:
        print(f"skip existing {path}", file=sys.stderr)
        return None
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _load_problem_models(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _apply_models_to_tasks(tasks: dict, models: dict) -> int:
    imported = 0
    for key, entry in tasks.items():
        model = models.get(key)
        if not model:
            continue
        if isinstance(model, dict):
            difficulty = model.get("difficulty")
        else:
            difficulty = model
        if difficulty is None:
            continue
        prev = entry.get("difficulty")
        entry["difficulty"] = int(round(float(difficulty)))
        flags = entry.get("flags", [])
        if prev is None:
            flags.append("IMPORTED")
        else:
            flags.append("IMPORTED_OVERWRITE")
        entry["flags"] = flags
        imported += 1
    return imported


def _update_problem_models(data: dict, tasks: dict) -> int:
    updated = 0
    for key, entry in tasks.items():
        difficulty = entry.get("difficulty")
        if difficulty is None:
            continue
        if key in data and isinstance(data[key], dict):
            data[key]["difficulty"] = difficulty
        else:
            data[key] = {"difficulty": difficulty}
        updated += 1
    return updated


def _write_problem_models(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate task difficulty from standings/json."
    )
    parser.add_argument("--category", required=True, help="Contest category (abc/arc/...)")
    parser.add_argument("--slug", help="Contest slug, e.g. arc121")
    parser.add_argument("--slugs", nargs="+", help="Multiple contest slugs")
    parser.add_argument("--include-unrated", action="store_true", help="Include unrated")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue on errors")
    parser.add_argument("--sleep", type=int, default=SLEEP_SEC, help="Sleep seconds between downloads")
    parser.add_argument("--run-tests", action="store_true", help="Run self tests")
    return parser.parse_args()


def _run_tests() -> None:
    ratings = [0.0, 400.0, 800.0]
    d_more, _ = estimate_difficulty_1pl(ratings, [0, 1, 1])
    d_less, _ = estimate_difficulty_1pl(ratings, [0, 0, 1])
    assert d_more is not None and d_less is not None
    assert d_more < d_less

    d_none, flags_none = estimate_difficulty_1pl([], [])
    assert d_none is None and "NO_DATA" in flags_none

    d_all, flags_all = estimate_difficulty_1pl([100, 200], [1, 1])
    assert d_all == LO_CLIP and "ALL_AC" in flags_all

    d_zero, flags_zero = estimate_difficulty_1pl([100, 200], [0, 0])
    assert d_zero == HI_CLIP and "NO_AC" in flags_zero

    print("tests: ok", file=sys.stderr)


def main() -> int:
    args = _parse_args()
    global SLEEP_SEC
    SLEEP_SEC = max(0, int(args.sleep))
    if args.run_tests:
        _run_tests()
        return 0

    slugs = []
    if args.slug:
        slugs.append(args.slug)
    if args.slugs:
        slugs.extend(args.slugs)
    if not slugs:
        print("error: --slug or --slugs required", file=sys.stderr)
        return 2

    rated_only = not args.include_unrated
    category = args.category
    models = _load_problem_models(PROBLEM_MODELS_PATH)
    models_dirty = 0
    failures = 0
    for slug in slugs:
        try:
            payload, _ = _estimate_for_contest(
                slug, category, rated_only, models, force=args.force
            )
            if not payload:
                print(f"skip existing {category}/{slug}", file=sys.stderr)
                continue
            out_path = _write_output(payload, slug, category, force=args.force)
            if out_path:
                print(f"saved {out_path}", file=sys.stderr)
                models_dirty += _update_problem_models(models, payload.get("tasks", {}))
        except Exception as exc:
            failures += 1
            print(f"failed {slug}: {exc}", file=sys.stderr)
            if not args.continue_on_error:
                return 1
    if models_dirty:
        _write_problem_models(PROBLEM_MODELS_PATH, models)
        print(f"problem-models: updated {models_dirty}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
