# Security
GEMINI_API_KEY is read from the OS environment only. No real key, .env or secrets.toml is packaged. Non-secret defaults are in config.py and example TOML.

Approved read-only functions, parameterized filters, fixed Parquet views and read-only SQLite snapshots replace arbitrary model SQL. No filesystem/code-execution/export/mutation tool exists. Structured results exclude raw messages, credentials and personal owner fields. Only synthetic or approved sanitized data should be used.

Each Chat request reserves local quota atomically. Hidden SDK retries are disabled. Failed/in-flight calls count. No paid fallback. Local registration/settings are UI actions, not agent tools. Launchers and Docker port publication bind localhost. No authentication/RBAC is implemented.
