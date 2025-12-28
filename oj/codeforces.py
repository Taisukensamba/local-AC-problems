from __future__ import annotations

import hashlib
from dataclasses import dataclass

from oj.base import OjNames


def _hash_name(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class CodeforcesOJ:
    name: str = OjNames.codeforces

    def contest_uid(self, contest_id: str) -> str:
        return f"{self.name}:{contest_id}"

    def problem_uid(
        self,
        *,
        contest_id: str | None,
        index: str | None,
        name: str | None,
        problem_id: str | None = None,
        problemset_name: str | None = None,
    ) -> str:
        if contest_id and index:
            return f"{self.name}:{contest_id}:{index}"
        safe_problemset = (problemset_name or "problemset").replace(":", "-")
        safe_index = index or "unknown"
        safe_name = _hash_name(name or "unknown")
        return f"{self.name}:{safe_problemset}:{safe_index}:{safe_name}"

    def submission_uid(self, submission_id: str | int) -> str:
        return f"{self.name}:{submission_id}"


codeforces_oj = CodeforcesOJ()
