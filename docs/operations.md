# Operations

## Processes

| Process | Command | Scale |
|---|---|---|
| Web | `npm run build --workspace apps/web && npm run start --workspace apps/web` | stateless, any number |
| API | `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` | stateless; the per-user rate limiter is in-process, so use a shared store before running many replicas |
| Worker | `uv run python -m worker run` | run one (extra copies stand by - the `worker_leases` row allows a single coordinator) |
| Database | Neon (pooled `DATABASE_URL`, direct `DIRECT_URL` for migrations) | - |

Deploy order: run `npm run db:migrate` (direct URL) → deploy API → deploy worker → deploy web.
Nothing in this repository deploys anything or creates paid resources.

## The worker loop

Every 15 seconds the coordinator (holding the lease, 90-second TTL):

1. runs admin-requested ingestion runs (`POST /api/v1/admin/ingestion/run`);
2. if `ENABLE_LIVE_INGESTION=true`, fetches sources that are due
   (`fetch_interval_minutes`, doubled per consecutive failure up to ×16);
3. plans news AI jobs when a provider is operational;
4. processes up to 3 queued jobs (offline Crunch always works, AI jobs need budget);
5. rebuilds today's edition every 10 minutes or after job activity.

One-off commands: `python -m worker tick`, `ingest`, `ai --max-jobs N`, `edition`,
`sync-models`, `status`. To check feed reachability from a new network without touching
real data: `uv run python scripts/live_ingestion_check.py rbi-press un-news pib gdelt`
(temporary database, dropped afterwards).

## Quotas and budgets

* Configure budgets from your provider consoles - the app never assumes free-tier numbers.
  Start small (e.g. `GEMINI_RPD_BUDGET=20`) and raise after watching real usage.
* Effective budget = value × `*_BUDGET_SAFETY_FACTOR` (default 0.65).
* The admin desk shows per-model spend, reservations, `blocked_until` with the reason
  (`rate_limited`, `daily_quota`, `auth_error`, provider-reported exhaustion), circuit state,
  and the routing table. `GET /api/v1/admin/ai/usage` returns 30 days of request/token counts.
* Do not rotate keys or projects to get around quotas.

## Failure and recovery

| Situation | What happens | Operator action |
|---|---|---|
| Provider 429 (minute limit) | Model blocked until Retry-After; job deferred; other candidate tried if eligible | none |
| Provider daily quota | Model blocked until its reset (Gemini: midnight America/Los_Angeles); jobs wait | none |
| Provider 5xx / timeouts | Bounded retries; circuit opens after 3 consecutive failures | none; check provider status if it persists |
| 401/403 (bad key, region) | Model blocked 6 h, job dead-lettered, visible in admin desk | fix the key/config, restart the worker |
| Model retired | `sync-models` or a 404 marks it unavailable | set a new model ID, re-run `sync-models` |
| Worker crashed mid-call | Lease expires (90 s); job lease expires (10 min) and is reclaimed; stale reservation counted as spent | none |
| Dead-lettered news job | Its events return to "discovered" with `review_note = AI generation failed: <code>` and are not re-planned automatically | inspect in admin desk; clear `review_note` to allow a retry |
| Dead-lettered / failed Crunch | User sees the message and can switch to the offline engine; re-submitting identical input re-queues it | none |
| Feed returns 403/5xx | Run marked failed, `last_error` shown, retries back off | check terms / robots; disable the source if access is refused |
| API down | Web shows friendly offline states | restart API |
| Database down | `/health` reports `degraded` | restore Neon / local Postgres |

Re-queue a dead-lettered job manually (SQL):
`UPDATE ai_jobs SET status='queued', attempts=0, next_run_at=now(), error_code=NULL WHERE id='<id>';`

## Secrets

* `.env` is git-ignored; `npm run setup` generates `AUTH_SECRET`, `API_JWT_SECRET` and the
  local Postgres password. Production secrets belong in the host's secret store.
* Rotating `API_JWT_SECRET` invalidates in-flight API tokens only (they live 5 minutes).
  Rotating `AUTH_SECRET` signs everyone out.
* Provider keys are only read by the worker; the API never needs them.

## Privacy operations

* Users can export everything (`GET /api/v1/me/export`, Settings → Your data) and delete
  their account (`DELETE /api/v1/me`), which cascades to notes, snapshots, mistakes, quiz
  history, Crunch jobs/outputs and flashcards, and removes their queued AI jobs.
* `audit_events` records security-relevant actions without note contents, prompts, e-mails
  or secrets.
* Private notes reach an AI provider only for an AI Crunch with user consent; consent is
  re-checked when the job runs.

## Local development notes

* The embedded Postgres keeps data in `%LOCALAPPDATA%\aajke-ki-scene\pgdata` (Windows),
  `~/Library/Application Support/aajke-ki-scene/pgdata` (macOS) or
  `~/.local/share/aajke-ki-scene/pgdata` (Linux). `node scripts/local-postgres.mjs reset --yes`
  wipes it.
* The repository can live in a cloud-synced folder, but `node_modules` and `.venv` are large;
  exclude them from sync or keep the checkout elsewhere for speed.
