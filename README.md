# Local CP Problems

AtCoder / Codeforces の問題や提出をローカルで見られるツールです。

## まずは設定（必須）

`config/config.toml` を編集します。

```toml
[atcoder]
user_id = "your_atcoder_id"

[codeforces]
handle = "your_codeforces_handle"
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

## 同期（任意）

初回だけ:
```bash
./scripts/sync_all.sh init
```

更新:
```bash
./scripts/sync_all.sh
```

## 生成されるもの

- `data/atcoder.db`
- `data/cache/`
- `json/`

## REVEL_SESSION の取り方（AtCoder）

- Chrome: DevTools → Application → Cookies → `https://atcoder.jp` → `REVEL_SESSION`
- Firefox: DevTools → Storage → Cookies → `https://atcoder.jp` → `REVEL_SESSION`
