# Run News-Yapper locally (Neon only, no Docker)

Use this after you clone the repo onto your own machine. The website, API, and worker run on your computer. The database is a [Neon](https://neon.tech) Postgres database. This setup does not install or start PostgreSQL on the machine.

The website is **News-Yapper**. Open it at <http://localhost:3000>.

You always run the commands below from the **repo root** (the folder that contains `frontend/` and `backend/`). One `.env` file in that root is shared by the site, the API, and the worker.

## Where the code lives

```text
newsYapper/
  frontend/          Next.js site. This is what Vercel builds.
  backend/
    api/             FastAPI. Users, news, quiz, notes.
    worker/          Background loop. Editions, live news, AI jobs.
    pyproject.toml   Python project for api + worker
  .env               Secrets and the Neon URLs. Never commit this.
  package.json       Starts frontend and backend together
  LOCAL_SETUP.md     This guide
```

| Folder | Runs locally as | Host it on |
|---|---|---|
| `frontend/` | <http://localhost:3000> | Vercel. Root Directory: `frontend` |
| `backend/` | API on <http://127.0.0.1:8000> plus the worker | Render. Root Directory: `backend`, as two services |

Locally, `npm run dev` starts both folders for you. You do not open two terminals. Hosting steps are in [`frontend/README.md`](frontend/README.md) and [`backend/README.md`](backend/README.md).

## What you install first

| Tool | Version | Why |
|---|---|---|
| [Git](https://git-scm.com/) | any recent | Clone the repo |
| [Node.js](https://nodejs.org/) | **20.9 or newer** | `frontend/` |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | any recent | Installs Python 3.11+ into `backend/.venv` |
| A Neon project | free tier is enough | The only database |

You do not install PostgreSQL, and you do not run Docker.

Check the local tools:

```bash
node -v
uv --version
```

`node -v` must print `v20.9` or higher.

## Create the Neon database

1. In the Neon console, create a project.
2. Open **Connect** and copy two strings:
   - **Pooled connection** into `DATABASE_URL`. The host contains `-pooler`. The API and the worker use this.
   - **Direct connection** into `DIRECT_URL`. The host does not contain `-pooler`. Migrations use this.
3. Paste each string exactly as Neon shows it, including `sslmode=require`.

`npm run dev` starts a database on this computer only when `DATABASE_URL` points at `127.0.0.1` or `localhost`. A Neon host skips that step.

## First run

From the folder where you keep projects:

```bash
git clone <repository-url> newsYapper
cd newsYapper
npm install
uv --directory backend sync
npm run setup
```

What each command does:

1. `npm install` installs the Next.js app in `frontend/`.
2. `uv --directory backend sync` creates `backend/.venv` and installs the API and the worker. uv downloads Python if you do not already have 3.11+.
3. `npm run setup` creates `.env` in the repo root and fills empty secrets. It also fills empty `DATABASE_URL`, `DIRECT_URL`, and `TEST_DATABASE_URL` with a local Postgres address. Replace those three before you start the app.

Open `.env` in the repo root (not inside `frontend/` or `backend/`) and set:

```env
DATABASE_URL=postgresql://...-pooler....neon.tech/neondb?sslmode=require
DIRECT_URL=postgresql://....neon.tech/neondb?sslmode=require
TEST_DATABASE_URL=
```

Leave `TEST_DATABASE_URL` empty unless you are running pytest. Pytest wipes that database. Never point it at the same Neon database as `DATABASE_URL`.

`npm run setup` does not overwrite a value that is already filled. If you run it again later, your Neon URLs stay put.

Start the app:

```bash
npm run dev
```

That applies migrations through `DIRECT_URL`, loads the demo edition when `DEMO_MODE=true`, then starts the API (`backend/api`), the worker (`backend/worker`), and the website (`frontend/`). Leave the terminal open.

Open <http://localhost:3000>. Click **Login** and type any name of at least two letters. The same name on this machine is the same account, stored in Neon. Use the name `admin` to open the admin desk. API docs are at <http://localhost:8000/docs>.

Stop the site with **Ctrl+C**. There is no local database to shut down.

## The next time you want to work

From the repo root, with the Neon URLs still in `.env`:

```bash
npm run dev
```

Install and setup only need to happen again if you delete `.env`, `backend/.venv`, or `node_modules`. The demo seed is safe to run more than once.

## Windows PowerShell

If `npm` fails with "running scripts is disabled", use `npm.cmd` for every npm command:

```powershell
npm.cmd install
uv --directory backend sync
npm.cmd run setup
npm.cmd run dev
```

## What `npm run dev` starts

| Process | Code | Address |
|---|---|---|
| Neon Postgres | your Neon project | the host in `DATABASE_URL` |
| API | `backend/api` | <http://127.0.0.1:8000> |
| Worker | `backend/worker` | no port. Editions, offline Crunch, and AI jobs when you enable them |
| Web | `frontend/` | <http://localhost:3000> |

The browser only talks to `frontend/`. The website talks to the API. The API and the worker talk to Neon. Gemini and Groq are not required for this path.

`.env` holds the Neon URLs and generated secrets. Do not commit it.

`DEMO_MODE=true` keeps the password-free login, which is what you want on your own machine. Turn it off, and configure GitHub or Google OAuth plus `ADMIN_EMAILS`, before you put the site on the public internet.

## Optional: your Gemini and Groq keys

The demo edition, quiz, notes, and offline Crunch work with the keys left blank. To let the worker call the models, edit the root `.env`, then stop `npm run dev` and start it again. The worker reads `.env` only at startup.

```env
ENABLE_GEMINI=true
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=the-model-id-from-ai-studio
GEMINI_RPM_BUDGET=2
GEMINI_RPD_BUDGET=20

ENABLE_GROQ=true
GROQ_API_KEY=your-groq-key
GROQ_MODEL_FAST=a-smaller-groq-model
GROQ_MODEL_QUALITY=a-stronger-groq-model
GROQ_RPM_BUDGET=30
GROQ_RPD_BUDGET=1000
```

Copy the model ids and the budget numbers from [Google AI Studio](https://aistudio.google.com/) and the [Groq console](https://console.groq.com/). The worker will not call a provider until that provider is enabled, has a model id, and has both an RPM budget and an RPD budget. A safety factor of `0.65` means a daily cap of 20 allows about 13 calls.

Check the model ids, then watch the admin desk (log in as `admin`):

```bash
uv --directory backend run python -m worker sync-models
```

Keys do not rewrite the labelled **DEMO** stories. AI summaries are planned only for real, non-demo news. **Crunch It** stays on the offline engine until you turn on the AI engine in settings and consent.

## Optional: live news

Still in the root `.env`:

```env
ENABLE_LIVE_INGESTION=true
INGESTION_CONTACT=you@example.com
```

`INGESTION_CONTACT` is an email or URL placed in the crawler's user agent. Restart `npm run dev` after saving. Feed notes are in [`docs/source-licenses.md`](docs/source-licenses.md).

## If it does not start

| What you see | What to do |
|---|---|
| `DATABASE_URL is empty` | Paste the Neon pooled URL into the root `.env`, then run `npm run dev` again |
| `uv sync` cannot find a project | You are in the wrong folder, or the command is missing the directory. From the repo root run `uv --directory backend sync` |
| `npm run dev` says it is starting local Postgres | `DATABASE_URL` still points at `127.0.0.1`. Replace it with the Neon pooled URL and start again |
| Migrations fail, or the error mentions PgBouncer | `DIRECT_URL` is missing or still points at the pooler. Paste the Neon **direct** URL |
| Connection timeout or SSL error | Paste the Neon string again, including `sslmode=require` |
| `running scripts is disabled` | Use `npm.cmd` instead of `npm` |
| `uv` is not recognized | Install uv, then open a new terminal |
| `node -v` is below 20.9 | Install a current Node.js and open a new terminal |
| Port 3000 or 8000 is already in use | Stop the other copy of this app, then run `npm run dev` again |
| The home page says the API is asleep | The API process exited. Read the `[api]` lines in the `npm run dev` terminal |
| You changed `.env` and nothing new happens | Ctrl+C, then `npm run dev` again |

## When you host it

Keep using Neon. Point each host at one folder:

| Folder | Host | What you select |
|---|---|---|
| `frontend/` | Vercel | Root Directory: `frontend` |
| `backend/` | Render | Root Directory: `backend`, twice: one web service for the API and one background worker |

Details are in [`frontend/README.md`](frontend/README.md) and [`backend/README.md`](backend/README.md). Use the same Neon database and the same `API_JWT_SECRET` on Vercel and both Render services.
