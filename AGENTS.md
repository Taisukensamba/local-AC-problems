# Codex Agent Guide

## Project overview
- This repo syncs and serves AtCoder/Codeforces problems and submissions locally.
- Backend is Python (FastAPI + Uvicorn). Data lives under `data/` and `json/`.

## Setup
```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Common commands
- Run dev server: `make dev`
- Lint (bytecode compile): `make lint`
- Tests: `make test`

## Notes
- Config lives in `config/config.toml` and can be overridden by env vars.
- Generated artifacts include `data/atcoder.db`, `data/cache/`, and `json/`.
- Assumption: server runs single-process; no multi-worker deployment expected.
