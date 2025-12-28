from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from db.schema import connect
from db.queries import list_contest_ids


def main() -> int:
    parser = argparse.ArgumentParser(description="List contest slugs by prefix.")
    parser.add_argument("--category", required=True, help="Contest prefix, e.g. abc")
    args = parser.parse_args()

    conn = connect()
    try:
        contest_ids = list_contest_ids(conn)
    finally:
        conn.close()

    prefix = args.category
    slugs = [cid for cid in contest_ids if cid.startswith(prefix)]
    print(" ".join(slugs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
