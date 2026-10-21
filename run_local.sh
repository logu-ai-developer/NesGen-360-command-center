#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/bootstrap.py
.venv/bin/python scripts/validate_environment.py
.venv/bin/python -m pytest -q
exec .venv/bin/python -m streamlit run app.py --server.port=8505 --server.address=127.0.0.1
