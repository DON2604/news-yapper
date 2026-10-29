# Backend

This folder is everything that is not the website:

| Path | What it is |
|---|---|
| `api/` | FastAPI. Users, news, quiz, notes, settings |
| `worker/` | Background process. Live news, AI summaries, editions, Crunch jobs |
| `pyproject.toml` | Python project for both |

Render should use **this folder** as the root directory. Create **two** Render services from it. One service cannot do both jobs: the API answers HTTP requests, and the worker loops forever.

Neon stays the database. Do not add a database on Render.

## API service

| Setting | Value |
|---|---|
| Type | Web service |
| Root Directory | `backend` |
| Runtime | Python |
| Build command | `uv sync --frozen` |
| Pre-deploy command | `uv run alembic -c api/alembic.ini upgrade head` |
| Start command | `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

If the build says `uv` is missing:

```bash
pip install uv && uv sync --frozen
```

## Worker service

| Setting | Value |
|---|---|
| Type | Background worker |
| Root Directory | `backend` |
| Runtime | Python |
| Build command | `uv sync --frozen` |
| Start command | `uv run python -m worker run` |

Run one worker. A second copy waits, because a lease row allows only one coordinator.

## Environment variables

Set the same values on the API service and the worker service.

| Name | Value |
|---|---|
| `DATABASE_URL` | Neon **pooled** URL (host contains `-pooler`) |
| `DIRECT_URL` | Neon **direct** URL |
| `API_JWT_SECRET` | Same secret as `API_JWT_SECRET` on Vercel |
| `APP_BASE_URL` | The Vercel site URL, for example `https://your-app.vercel.app` |
| `API_BASE_URL` | This API's public Render URL |
| `DEMO_MODE` | `true` or `false`, matching Vercel |
| `ADMIN_EMAILS` | Comma-separated emails that should be admins when demo mode is off |

Gemini, Groq, and live ingestion use the same names as in the repo `.env`. See [`../LOCAL_SETUP.md`](../LOCAL_SETUP.md).

After the first migration, load the demo edition once from a Render shell in this folder:

```bash
uv run python -m app.cli seed-demo
```

`render.yaml` in the repo root describes these two services. Filling the secret values in the Render dashboard is still required.
