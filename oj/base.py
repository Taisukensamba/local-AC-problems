from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class OjAdapter(Protocol):
    name: str

    def contest_uid(self, contest_id: str) -> str: ...

    def problem_uid(
        self,
        *,
        contest_id: str | None,
        index: str | None,
        name: str | None,
        problem_id: str | None = None,
        problemset_name: str | None = None,
    ) -> str: ...

    def submission_uid(self, submission_id: str | int) -> str: ...


@dataclass(frozen=True)
class OjNames:
    atcoder: str = "atcoder"
    codeforces: str = "codeforces"
