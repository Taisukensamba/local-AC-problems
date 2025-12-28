# AC-problems

AtCoder Problems 関連データを同期して、ローカルで閲覧・確認するためのツールです。

## セットアップ

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## 設定

`config/config.toml` を編集します（環境変数でも可）。

```toml
user_id = "your_atcoder_id"
rate_limit = 1.0

[sync]
mode = "cookie" # api / cookie / hybrid

[difficulty]
source_url = "/path/to/local-AC-problems/data/problem-models.json"

[cookie]
revel_session = "REVEL_SESSION_HERE"

[cache]
enabled = true
ttl_sec = 3600
dir_path = "data/cache"
```

環境変数で上書きする場合:
```bash
export AC_USER_ID=your_atcoder_id
export AC_REVEL_SESSION=REVEL_SESSION_HERE
export AC_DIFFICULTY_SOURCE_URL=/path/to/local-AC-problems/data/problem-models.json
export AC_CONFIG_PATH=config/config.toml
```

## 起動

```bash
make dev
```

ブラウザで `http://127.0.0.1:8000/` を開きます。

## 同期

```bash
# 初期化
./scripts/sync_all.sh init

# 更新（差分）
./scripts/sync_all.sh
```

### 個別同期

contests:
```bash
curl -s -X POST http://127.0.0.1:8000/api/sync \
  -H 'Content-Type: application/json' \
  -d '{"contest": true, "tasks": false, "submissions": false}'
```

tasks:
```bash
curl -s -X POST http://127.0.0.1:8000/api/sync \
  -H 'Content-Type: application/json' \
  -d '{"contest": false, "tasks": true, "submissions": false}'
```

tasks（差分）:
```bash
curl -s -X POST http://127.0.0.1:8000/api/sync \
  -H 'Content-Type: application/json' \
  -d '{"contest": false, "tasks": true, "submissions": false, "tasks_incremental": true}'
```

submissions（cookie）:
```bash
curl -s -X POST http://127.0.0.1:8000/api/sync \
  -H 'Content-Type: application/json' \
  -d '{"contest": false, "tasks": false, "submissions": true, "mode": "cookie"}'
```

submissions（差分）:
```bash
curl -s -X POST http://127.0.0.1:8000/api/sync \
  -H 'Content-Type: application/json' \
  -d '{"contest": false, "tasks": false, "submissions": true, "mode": "cookie", "submissions_incremental": true}'
```

進捗の確認:
```bash
curl -s http://127.0.0.1:8000/api/sync/status
```

## 難易度の推定（standings/jsonベース）

```bash
# 単発
python3 scripts/calc_difficulty.py --category arc --slug arc121

# 全件
bash scripts/calc_difficulty_all.sh
```

推定後にDBへ反映:
```bash
python3 scripts/import_difficulty.py
```

## difficultyモデルの更新（AtCoder Problems準拠）

```bash
python3 scripts/update_problem_models.py
python3 scripts/import_difficulty.py
```

## 生成物

以下は実行時に生成されます。

- `data/atcoder.db`（SQLite）
- `data/cache`（HTTPキャッシュ）
- `data/problem-models.json`（difficultyモデル）
- `json/`（standings/difficulty の保存先）

## REVEL_SESSION の取り方

- Chrome: DevTools → Application → Cookies → `https://atcoder.jp` → `REVEL_SESSION`
- Firefox: DevTools → Storage → Cookies → `https://atcoder.jp` → `REVEL_SESSION`
