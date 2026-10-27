# Deploying NesGen 360 for team access

This is a Streamlit app. To let teammates reach it from their own machines you run it on a **host** (a server or a
hosting service) and share the URL — you do **not** run it from your laptop for the team (a laptop is not always on and
is not reachable from outside your network). The app has its own login (admin / end-user), so access is gated by that
login once the site is reachable.

The repo already contains a `Dockerfile` and `docker-compose.yml`, so the container options below need no new build setup.

## What any deployment needs

- **Python 3.12** and the pinned `requirements.txt` (the Docker image already has this).
- **A secret for Gemini**: `GEMINI_API_KEY` (only needed for the AI assistants). Set it as an environment variable or,
  for Streamlit Cloud, in the app's Secrets. Never commit it.
- **Persistent storage** for `data/nesgen360.db` (the SQLite file that holds the admin hash, sessions and usage
  counters) and the `data/` folder (workbooks / parquet, if you use real inputs). Without a persistent disk the DB
  resets on every restart and all logins are lost.
- **The first admin**: on a fresh database, bootstrap one admin account once (see "First run" below).
- Run command: `streamlit run app.py --server.port 8501 --server.address 0.0.0.0`.

## Option A — a cloud VM or Azure App Service / AWS (recommended for a stable team URL)

1. Provision a small Linux VM (or Azure App Service for Containers / AWS App Runner / ECS).
2. Put the repo on it, create the venv from `requirements.txt` (or use the Docker image).
3. Attach a **persistent disk/volume** and point `data/` at it (the DB lives there).
4. Set `GEMINI_API_KEY` in the environment.
5. Run `streamlit run app.py --server.port 8501 --server.address 0.0.0.0` behind HTTPS
   (a reverse proxy such as nginx/Caddy, or the platform's built-in TLS).
6. Share the HTTPS URL. Teammates open it and log in.

Pros: always on, stable URL, data persists, you control networking. This is the best fit for a shared team POC.

## Option B — the Docker image on a container host

1. Build/push the image from the existing `Dockerfile` (or use `docker-compose up` on a host).
2. Mount a volume for `data/` so the SQLite DB and any inputs persist across restarts.
3. Pass `GEMINI_API_KEY` as an environment variable.
4. Expose the container port behind HTTPS (Azure Container Apps, AWS ECS/Fargate, or a VM running Docker).

Pros: reproducible, matches the committed Dockerfile. Same persistence requirement as Option A.

## Option C — Streamlit Community Cloud (fastest, with caveats)

1. Push the repo to GitHub and connect it at share.streamlit.io.
2. Set `GEMINI_API_KEY` in the app's **Secrets**.
3. It builds from `requirements.txt` and gives you a public URL.

Caveats: Community Cloud storage is **ephemeral** — the SQLite DB resets on every rebuild/restart, so admin accounts
and sessions do not persist, and it is best for a quick shared demo rather than a durable team site. The repo must be
accessible to the Streamlit app. Good for a throwaway demo URL; use Option A/B for anything lasting.

## First run (bootstrap the admin)

On a brand-new database there is no admin yet. Create one once, on the host, in a terminal:

```
..\.venv\Scripts\python.exe -c "from src import auth; auth.bootstrap_admin('admin','<a long passphrase>')"
```

(`bootstrap_admin` refuses to create a second admin, so this is safe to leave in place.) After that, teammates register
as end-users through the app's login screen, or you create accounts as the admin.

## Data mode

The POC runs on the deterministic **synthetic scenario** data (the Real/Demo toggle was removed), so a deployment does
not need real telemetry or workbooks to be useful — it demonstrates the scenarios out of the box. If real input files
are later added to `data/`, the model inventory and adoption pages will read them; the telemetry pages stay on the
synthetic scenario by design.

## Security notes (carried from CLAUDE.md)

- Never commit `.env`, `*.db`, or files under `data/`.
- `data/nesgen360.db` holds the admin hash, sessions and usage counters — treat it as a secret; do not share it.
- The Gemini key is a personal-use key for this POC; keep it in host secrets, not in the repo.
