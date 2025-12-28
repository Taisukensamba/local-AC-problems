from __future__ import annotations

from dataclasses import dataclass

from oj.base import OjNames


@dataclass(frozen=True)
class AtCoderOJ:
    name: str = OjNames.atcoder

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
        if not problem_id:
            raise ValueError("AtCoder problem_id is required")
        return f"{self.name}:{problem_id}"

    def submission_uid(self, submission_id: str | int) -> str:
        return f"{self.name}:{submission_id}"


atcoder_oj = AtCoderOJ()


def contest_id_from_uid(contest_uid: str) -> str:
    prefix = f"{atcoder_oj.name}:"
    if not contest_uid.startswith(prefix):
        raise ValueError(f"invalid contest_uid: {contest_uid}")
    return contest_uid[len(prefix) :]
