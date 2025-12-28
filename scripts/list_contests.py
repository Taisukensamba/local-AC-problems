from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from db.schema import connect
from db.queries import list_contest_uids
from oj.atcoder import contest_id_from_uid, atcoder_oj


def main() -> int:
    parser = argparse.ArgumentParser(description="List contest slugs by prefix.")
    parser.add_argument("--category", required=True, help="Contest prefix, e.g. abc")
    args = parser.parse_args()

    conn = connect()
    try:
        contest_uids = list_contest_uids(conn, atcoder_oj.name)
    finally:
        conn.close()

    prefix = args.category
    slugs = [
        contest_id_from_uid(uid)
        for uid in contest_uids
        if contest_id_from_uid(uid).startswith(prefix)
    ]
    print(" ".join(slugs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
