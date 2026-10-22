# Architecture
V0 UI shell and ten routes -> canonical source adapters -> Excel / DuckDB Parquet or deterministic synthetic fallback. SQLite stores settings, registrations, source status, usage and synthetic snapshots. core.py is retained for compatibility; startup uses storage.py and usage.py.

Question + bounded dialogue + scope -> Chat model -> allowlisted function -> local execution -> bounded evidence -> Chat response. The application-controlled function loop reserves each model request. No arbitrary model-generated SQL is executed. Query tools expose canonical frames, approved SQLite snapshots and fixed Parquet views.
