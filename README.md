# Local CP Problems

AtCoder / Codeforces の問題や提出をローカルで見られるツールです。

## まずは設定（必須）

`config/config.toml` を編集します。（このファイルは .gitignore してあるため、README にベースを載せています）

```toml
[atcoder]
user_id = "your_atcoder_id"

[atcoder.sync]
mode = "cookie"

[atcoder.cookie]
revel_session = "REVEL_SESSION_HERE"

[codeforces]
handle = "your_codeforces_handle"
include_gym = false

[rate_limit]
atcoder_rps = 1.0
codeforces_min_interval_seconds = 2.0

[cache]
enabled = true
ttl_sec = 3600
dir_path = "data/cache"
```

提出まで同期したい場合は `REVEL_SESSION` が必要です。

```toml
[atcoder.cookie]
revel_session = "REVEL_SESSION_HERE"
```

## 起動

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
make dev
```

ブラウザで `http://127.0.0.1:8000/` を開きます。

## UI の同期ボタンの使い方

- `AtCoder同期`: 入力欄にコンテストIDをスペース区切りで入力してクリックします。（例: `abc331 arc121 agc060`）
  - 問題のみ同期します。提出まで同期したい場合は `REVEL_SESSION` の設定が必要です。
- `Codeforces同期`: クリックすると Codeforces のコンテスト・問題・提出を順に同期します。

進捗は画面の `sync: ...` 表示で確認できます。

## 同期（任意）

初回だけ:
```bash
./scripts/sync_all.sh init
```

更新:
```bash
./scripts/sync_all.sh
```

実行中に 403 で弾かれる場合:

- `http.py` の `min_delay` と `delay` を少し大きくしてください。（例: `1.00`）

## 生成されるもの

- `data/atcoder.db`
- `data/cache/`
- `json/`

## REVEL_SESSION の取り方（AtCoder）

- Chrome: DevTools → Application → Cookies → `https://atcoder.jp` → `REVEL_SESSION`
- Firefox: DevTools → Storage → Cookies → `https://atcoder.jp` → `REVEL_SESSION`
