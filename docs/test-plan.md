# Test plan

## Automated suites

| Suite | Command | Count | Needs |
|---|---|---|---|
| API + worker (pytest) | `uv run pytest` | 101 (+1 opt-in live) | Postgres at `TEST_DATABASE_URL` (wiped per test) |
| Live feed check | `uv run python scripts/live_ingestion_check.py rbi-press un-news pib gdelt` | 1 real ingestion | Network; uses a temporary database |
| Python lint / types | `npm run lint:py`, `npm run typecheck:py` | ruff, ruff format, mypy (75 files) | - |
| Web unit (Vitest + Testing Library) | `npm run test --workspace apps/web` | 8 | - |
| Web lint / types / build | `npm run lint --workspace apps/web`, `npm run typecheck --workspace apps/web`, `npm run build --workspace apps/web` | ESLint, tsc, `next build` | - |
| End-to-end (Playwright) | `npm run test:e2e` | 2 | Full stack (auto-started) |
| Visual QA | `npm run screenshots --workspace apps/web` | 12 screens × 3 widths (+ interactive states with `SCREEN_FLOWS=1`) | Full stack |

The pytest session drops and recreates the test schema by running the Alembic migration, so
every run also proves the migration from an empty database.

## Definition of done → evidence

| Plan checklist item | Covered by |
|---|---|
| Clean install, documented startup, no credentials in DEMO mode | README quick start; `scripts/setup.mjs`, `scripts/local-postgres.mjs`, `scripts/dev.mjs` (run on Windows) |
| Migrations create tables/indexes; seed works | `conftest.py::migrated_database`; `npm run db:seed` twice (idempotent) |
| PIB + GDELT ingester with timeout, retry, dedupe, canonical URL, timestamps | `test_ingestion.py`: PIB/RBI/Google fixtures, GDELT parse + bounded window/spacing, retries, timeouts, 403 no-retry, end-to-end run with dedupe, clustering, corrections, failure isolation, backoff, same-source templated titles kept apart. Live check (2026-10-29): RBI 10 + UN 30 items → 40 events; PIB 403 and GDELT unreachable from the dev network, both recorded cleanly |
| Unique events, cross-source attribution, corrections, review labels | `test_run_ingestion_end_to_end`, `test_publisher_correction_flags_published_event`, `test_unpublished_ai_drafts_are_never_exposed` |
| Sequential worker, persistent RPM/TPM/RPD, retries, leases, caching | `test_quota.py` (budgets, safety factor, Pacific reset, RPM/TPM, min gap, concurrency, stale sweep, persistence, circuit breaker, Groq headers), `test_orchestrator.py` |
| Simulated 429 / 503 / daily quota: site still serves, jobs defer, no infinite retry | `test_rate_limit_falls_back_to_groq`, `test_outage_defers_without_ping_pong_and_site_keeps_working`, `test_daily_quota_defers_until_pacific_midnight`, `test_bounded_retries_end_in_dead_letter`, `test_auth_error_dead_letters_and_releases_events` |
| Responsive 360-1440, keyboard, contrast, states, reduced motion | Screenshots in `docs/screenshots`; skip link, focus rings, `prefers-reduced-motion` override, icon + text quiz feedback (`components.test.tsx`), keyboard sticky moves |
| Sticky CRUD persists, colours, tags, reorder, isolation | `test_note_crud_persists_and_sanitizes`, `test_user_a_cannot_touch_user_b_notes`, e2e sticky creation |
| Save article snapshot, attribution | `test_snapshot_saved_once_and_survives_article_edits`, `test_source_only_snapshot_and_isolation`, e2e pin |
| Mistake Vault records once, review state | `test_daily_quiz_flow_records_mistakes_once`, `test_mistake_review_resolves_without_erasing_history` |
| Crunch traceable output, cache hit, queued state without quota | `test_crunch_is_idempotent_and_cached`, `test_private_notes_never_reach_fallback_without_consent` (deferred state), e2e offline crunch |
| Daily quiz from validated pool, weak topics, no AI per answer | `test_weak_topics_are_prioritised`, quiz flow tests (no provider configured at all) |
| User A cannot read/change user B data | notes, snapshots, mistakes, quiz sessions, crunch jobs/outputs, flashcards isolation tests; e2e privacy test |
| SSRF, sanitised notes, prompt injection, admin role checks | `test_fetcher_blocks_*`, redirect test, robots test; sanitisation test + `StickyNote` render test; prompt-injection test; `test_all_admin_endpoints_forbidden_for_regular_users`, forged-claims test |
| Lint, typecheck, unit, integration, Playwright | table above |

## Manual QA checklist

1. `npm run dev`, open the home page at 375 px and 1440 px; confirm the DEMO banner and
   labels, no horizontal scrolling, readable contrast.
2. Keyboard only: Tab from the skip link through the header, a quiz (keys 1-4), the Brain
   Dump (arrow keys move a focused sticky, Enter edits) and the sticky composer (Esc closes).
3. OS "reduce motion" on: no confetti, no card flip animation, no steam animation.
4. Stop the API: pages show friendly offline states; restart and reload.
5. Stop the worker and queue a Crunch: the job stays "Waiting in the job queue"; start the
   worker and watch it complete.
6. With real provider keys (optional): set a tiny `GEMINI_RPD_BUDGET` (e.g. 2), run
   `worker sync-models`, enable ingestion, and confirm the admin desk shows spend, blocks and
   deferred jobs instead of a flood of requests.
