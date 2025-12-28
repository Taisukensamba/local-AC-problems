import pathlib
import tempfile
import unittest

from crawler.codeforces_api import normalize_problemset, parse_problemset, parse_user_status
from db.dao import replace_problem_tags, upsert_contests, upsert_problems, upsert_submissions
from db.schema import connect, init_db
from oj.codeforces import codeforces_oj


class CodeforcesApiTest(unittest.TestCase):
    def test_parse_problemset(self) -> None:
        payload = pathlib.Path("data/fixtures/codeforces_problemset.json").read_text(
            encoding="utf-8"
        )
        problems, stats_map = parse_problemset(payload)
        normalized, tags_by_uid, contests = normalize_problemset(problems, stats_map)
        self.assertEqual(len(normalized), 2)
        contest_problem_uid = codeforces_oj.problem_uid(
            contest_id="1000", index="A", name="Problem A"
        )
        self.assertEqual(normalized[0]["problem_uid"], contest_problem_uid)
        self.assertEqual(normalized[0]["solved_count"], 1234)
        self.assertIn("dp", tags_by_uid[contest_problem_uid])
        contest_uids = {c["contest_uid"] for c in contests}
        self.assertIn(codeforces_oj.contest_uid("1000"), contest_uids)

    def test_parse_user_status(self) -> None:
        payload = pathlib.Path("data/fixtures/codeforces_user_status.json").read_text(
            encoding="utf-8"
        )
        submissions = parse_user_status(payload, "alice_cf")
        self.assertEqual(submissions[0]["submission_uid"], codeforces_oj.submission_uid(111))
        self.assertEqual(
            submissions[0]["problem_uid"],
            codeforces_oj.problem_uid(contest_id="1000", index="A", name="Problem A"),
        )
        self.assertEqual(
            submissions[1]["problem_uid"],
            codeforces_oj.problem_uid(
                contest_id=None, index="B", name="Non Contest", problemset_name="special"
            ),
        )

    def test_upsert_and_progress(self) -> None:
        problem_payload = pathlib.Path("data/fixtures/codeforces_problemset.json").read_text(
            encoding="utf-8"
        )
        status_payload = pathlib.Path("data/fixtures/codeforces_user_status.json").read_text(
            encoding="utf-8"
        )
        problems, stats_map = parse_problemset(problem_payload)
        normalized, tags_by_uid, contests = normalize_problemset(problems, stats_map)
        submissions = parse_user_status(status_payload, "alice_cf")

        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            init_db(f.name)
            conn = connect(f.name)
            try:
                upsert_contests(conn, contests)
                upsert_problems(conn, normalized)
                for problem_uid, tags in tags_by_uid.items():
                    replace_problem_tags(conn, problem_uid, tags)
                upsert_submissions(conn, submissions)
                conn.commit()
                rows = conn.execute(
                    "SELECT is_ac FROM progress WHERE user_id = ? ORDER BY problem_uid",
                    ("alice_cf",),
                ).fetchall()
            finally:
                conn.close()
        self.assertEqual([row[0] for row in rows], [1, 0])
