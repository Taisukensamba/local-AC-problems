from __future__ import annotations

import json
import time
from typing import Callable

from db.dao import update_problem_difficulties


def parse_problem_models(payload: str) -> list[dict]:
    data = json.loads(payload)
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            data = data["data"]
        else:
            items = []
            for key, value in data.items():
                if isinstance(value, dict) and "difficulty" in value:
                    items.append({"id": key, "difficulty": value.get("difficulty")})
                elif isinstance(value, (int, float)):
                    items.append({"id": key, "difficulty": value})
            data = items
    items = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        if "problem_id" in entry:
            problem_id = entry["problem_id"]
        else:
            problem_id = entry.get("id")
        if not problem_id:
            continue
        items.append(
            {
                "problem_id": problem_id,
                "difficulty": entry.get("difficulty"),
            }
        )
    return items


def import_difficulty(
    fetch_json: Callable[[str], str],
    conn,
    source_url: str,
) -> int:
    payload = fetch_json(source_url)
    items = parse_problem_models(payload)
    updated_epoch = int(time.time())
    for item in items:
        item["updated_epoch"] = updated_epoch
    return update_problem_difficulties(conn, items)
