import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


DEFAULT_URL = "https://kenkoooo.com/atcoder/resources/problem-models.json"


def _read_meta(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _write_text(path: str, payload: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)


def _write_meta(path: str, headers: dict) -> None:
    meta = {
        "etag": headers.get("ETag"),
        "last_modified": headers.get("Last-Modified"),
        "fetched_at": int(time.time()),
    }
    _write_text(path, json.dumps(meta, indent=2))


def fetch_and_update(url: str, output_path: str, meta_path: str, timeout: int) -> int:
    meta = _read_meta(meta_path)
    headers = {}
    if meta.get("etag"):
        headers["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        headers["If-Modified-Since"] = meta["last_modified"]
    headers.setdefault(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            status = res.status
            if status == 304:
                print("problem-models: up-to-date")
                return 0
            payload = res.read().decode("utf-8")
            _write_text(output_path, payload)
            _write_meta(meta_path, dict(res.headers))
            print(f"problem-models: updated ({len(payload)} bytes)")
            return 0
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            print("problem-models: up-to-date")
            return 0
        print(f"problem-models: fetch failed ({exc.code})", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"problem-models: fetch error ({exc})", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Update local problem-models.json")
    parser.add_argument("--url", default=DEFAULT_URL, help="Source URL")
    parser.add_argument(
        "--output",
        default="data/problem-models.json",
        help="Output file path",
    )
    parser.add_argument(
        "--meta",
        default="data/problem-models.meta.json",
        help="Metadata file path",
    )
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout (sec)")
    args = parser.parse_args()
    return fetch_and_update(args.url, args.output, args.meta, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
