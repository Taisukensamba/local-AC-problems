import os
import sqlite3
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config.loader import load_config
from crawler.difficulty_import import import_difficulty
from crawler.http import HttpClient, cache_config_from_app
from db.schema import connect, init_db


def main() -> None:
    config = load_config()
    init_db()
    retries = 3
    for attempt in range(1, retries + 1):
        conn = connect()
        try:
            client = HttpClient(config.rate_limit.atcoder_rps, cache_config_from_app(config))
            count = import_difficulty(
                client.get_text, conn, config.atcoder.difficulty.source_url
            )
            conn.commit()
            break
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt >= retries:
                raise
            wait = 2 ** attempt
            print(f"database locked, retrying in {wait}s...", file=sys.stderr)
            time.sleep(wait)
        finally:
            conn.close()
    print(f"updated {count}")


if __name__ == "__main__":
    main()
