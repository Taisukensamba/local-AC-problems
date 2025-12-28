import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config.loader import load_config
from crawler.difficulty_import import import_difficulty
from crawler.http import HttpClient, cache_config_from_app
from db.schema import connect, init_db


def main() -> None:
    config = load_config()
    init_db()
    conn = connect()
    try:
        client = HttpClient(config.rate_limit, cache_config_from_app(config))
        count = import_difficulty(client.get_text, conn, config.difficulty.source_url)
        conn.commit()
    finally:
        conn.close()
    print(f"updated {count}")


if __name__ == "__main__":
    main()
