"use client";

import { Play, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CandyButton } from "@/components/design-system/CandyButton";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { api } from "@/lib/client-api";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";

/* eslint-disable @typescript-eslint/no-explicit-any -- admin JSON is rendered generically */
type Overview = Record<string, any>;
type ReviewItem = Record<string, any>;
type Job = Record<string, any>;

function Tile({ label, value, tone = "paper" }: { label: string; value: string; tone?: "paper" | "mint" | "pink" | "mango" | "lavender" }) {
  const bg = { paper: "bg-paper", mint: "bg-mint", pink: "bg-pink", mango: "bg-mango", lavender: "bg-lavender" }[tone];
  return (
    <div className={cn("rounded-2xl border-2 border-ink p-4 shadow-brutal-sm", bg)}>
      <p className="text-xs font-bold tracking-wide uppercase">{label}</p>
      <p className="font-display text-2xl font-bold break-words">{value}</p>
    </div>
  );
}

export function AdminPanel({ overview, queue, jobs }: { overview: Overview; queue: ReviewItem[]; jobs: Job[] }) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function act(key: string, path: string, body: unknown = {}) {
    setBusy(key);
    setMessage(null);
    try {
      const res = await api<{ message?: string; status?: string }>(path, { method: "POST", body });
      setMessage(res.message ?? `Done: ${res.status ?? "ok"}`);
      router.refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  const worker = overview.worker ?? {};
  const byStatus: Record<string, number> = overview.queue?.by_status ?? {};
  return (
    <div className="space-y-8">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Tile label="Worker" value={worker.alive ? "Running" : "Not running"} tone={worker.alive ? "mint" : "pink"} />
        <Tile label="Live ingestion" value={overview.live_ingestion_enabled ? "Enabled" : "Disabled"} tone={overview.live_ingestion_enabled ? "mint" : "mango"} />
        <Tile label="Review queue" value={String(overview.review_queue_count)} tone={overview.review_queue_count ? "pink" : "paper"} />
        <Tile label="Last AI success" value={overview.last_ai_success_at ? formatDateTime(overview.last_ai_success_at) : "Never"} tone="lavender" />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <CandyButton tone="punch" disabled={busy !== null} onClick={() => void act("ingest", "admin/ingestion/run")}>
          <Play className="size-4" aria-hidden="true" /> Run ingestion now
        </CandyButton>
        <CandyButton tone="paper" onClick={() => router.refresh()}>
          <RefreshCw className="size-4" aria-hidden="true" /> Refresh
        </CandyButton>
        <p aria-live="polite" className="font-semibold">
          {message}
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="font-display text-2xl font-bold">AI providers & quota</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {(overview.providers ?? []).map((p: any) => (
            <div key={p.name} className={cn("rounded-2xl border-2 border-ink p-4 shadow-brutal-sm", p.operational ? "bg-mint" : "bg-paper")}>
              <div className="flex items-center justify-between">
                <h3 className="font-display text-xl font-bold capitalize">{p.name}</h3>
                <StickerBadge tone={p.operational ? "ink" : "pink"} tilt={0}>
                  {p.operational ? "Operational" : "Off"}
                </StickerBadge>
              </div>
              {p.problems.length ? <p className="mt-2 text-sm">Needs: {p.problems.join(" · ")}</p> : null}
              <p className="mt-2 text-sm">
                Models: {Object.entries(p.models).map(([k, v]) => `${k}=${v}`).join(", ") || "none configured"}
              </p>
              <p className="text-sm">
                Budgets (×{p.budgets.safety_factor}): RPM {p.budgets.rpm ?? "-"} · TPM {p.budgets.tpm ?? "-"} · RPD {p.budgets.rpd ?? "-"}
                {p.budgets.tpd ? ` · TPD ${p.budgets.tpd}` : ""} · gap {p.budgets.min_seconds_between_requests}s · reset {p.daily_reset_tz}
              </p>
            </div>
          ))}
        </div>
        {overview.quota_states?.length ? (
          <div className="overflow-x-auto rounded-2xl border-2 border-ink bg-paper">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-cream-deep text-left font-display">
                <tr>
                  <th className="p-2">Provider/model</th>
                  <th className="p-2">Day</th>
                  <th className="p-2">Spent</th>
                  <th className="p-2">Reserved</th>
                  <th className="p-2">Blocked until</th>
                  <th className="p-2">Circuit</th>
                </tr>
              </thead>
              <tbody>
                {overview.quota_states.map((q: any) => (
                  <tr key={`${q.provider}-${q.model}`} className="border-t border-ink/20">
                    <td className="p-2 font-semibold">{q.provider}/{q.model}{q.available === false ? " (unavailable)" : ""}</td>
                    <td className="p-2">{q.day_key ?? "-"}</td>
                    <td className="p-2">{q.daily_spent_requests} req / {q.daily_spent_tokens} tok</td>
                    <td className="p-2">{q.daily_reserved_requests}</td>
                    <td className="p-2">{q.blocked_until ? `${formatDateTime(q.blocked_until)} (${q.block_reason})` : "-"}</td>
                    <td className="p-2">{q.circuit_open_until ? `open until ${formatDateTime(q.circuit_open_until)}` : "closed"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-soft">No provider calls recorded yet.</p>
        )}
        <details className="rounded-2xl border-2 border-ink bg-paper p-4">
          <summary className="cursor-pointer font-semibold">Task routing table</summary>
          <ul className="mt-2 space-y-1 text-sm">
            {Object.entries(overview.routing ?? {}).map(([task, cands]: [string, any]) => (
              <li key={task}>
                <strong>{task}</strong>: {cands.map((c: any) => `${c.provider}:${c.model ?? `(${c.model_role} unset)`}`).join(" → ")}
              </li>
            ))}
          </ul>
        </details>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-2xl font-bold">Approval queue ({queue.length})</h2>
        {queue.length === 0 ? (
          <p className="rounded-2xl border-2 border-dashed border-ink p-4 text-ink-soft">Nothing waiting for review.</p>
        ) : (
          <ul className="grid gap-4 lg:grid-cols-2">
            {queue.map((item) => (
              <li key={item.event_id} className="space-y-2 rounded-2xl border-2 border-ink bg-paper p-4 shadow-brutal-sm">
                <div className="flex flex-wrap gap-2">
                  <StickerBadge tone="pink" tilt={0}>{item.status}</StickerBadge>
                  {item.sensitive ? <StickerBadge tone="ink" tilt={0}>sensitive</StickerBadge> : null}
                  <StickerBadge tone="paper" tilt={0}>relevance {item.relevance_score}</StickerBadge>
                </div>
                <h3 className="font-display text-lg font-bold">{item.draft?.headline ?? item.title}</h3>
                {item.draft ? <p className="text-sm">{item.draft.neutral_summary}</p> : <p className="text-sm text-ink-soft">No draft (AI generation failed or pending).</p>}
                {item.draft?.confidence_flags?.validation_flags?.length ? (
                  <p className="text-sm font-semibold text-pink-deep">Flags: {item.draft.confidence_flags.validation_flags.join(", ")}</p>
                ) : null}
                <p className="text-xs text-ink-soft">Sources: {item.sources.map((s: any) => s.name).join(", ")}</p>
                <div className="flex flex-wrap gap-2 pt-1">
                  {item.draft ? (
                    <CandyButton tone="mint" size="sm" disabled={busy !== null} onClick={() => void act(`a-${item.event_id}`, `admin/events/${item.event_id}/approve`, { approve_questions: false })}>
                      Approve & publish
                    </CandyButton>
                  ) : null}
                  <CandyButton tone="pink" size="sm" disabled={busy !== null} onClick={() => void act(`r-${item.event_id}`, `admin/events/${item.event_id}/reject`, { note: "rejected in admin desk" })}>
                    Reject
                  </CandyButton>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-2xl font-bold">Sources</h2>
        <div className="overflow-x-auto rounded-2xl border-2 border-ink bg-paper">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-cream-deep text-left font-display">
              <tr>
                <th className="p-2">Source</th>
                <th className="p-2">Type</th>
                <th className="p-2">Last fetch</th>
                <th className="p-2">Status</th>
                <th className="p-2">Enabled</th>
              </tr>
            </thead>
            <tbody>
              {(overview.sources ?? []).map((s: any) => (
                <tr key={s.slug} className="border-t border-ink/20 align-top">
                  <td className="p-2">
                    <p className="font-semibold">{s.name}</p>
                    <p className="max-w-md text-xs text-ink-soft">{s.legal_notes}</p>
                  </td>
                  <td className="p-2">{s.type} · tier {s.tier}</td>
                  <td className="p-2">{s.last_fetch_at ? formatDateTime(s.last_fetch_at) : "never"}</td>
                  <td className="max-w-xs p-2 text-xs">{s.last_error ? <span className="font-semibold text-pink-deep">{s.last_error}</span> : s.last_success_at ? "ok" : "-"}</td>
                  <td className="p-2">
                    {s.type === "manual" ? (
                      <span className="text-xs text-ink-soft">manual</span>
                    ) : (
                      <button
                        type="button"
                        disabled={busy !== null}
                        onClick={() => void act(`s-${s.slug}`, `admin/sources/${s.slug}/toggle`, { enabled: !s.enabled })}
                        className={cn("min-h-10 rounded-lg border-2 border-ink px-3 font-semibold", s.enabled ? "bg-mint" : "bg-cream")}
                        aria-pressed={s.enabled}
                      >
                        {s.enabled ? "On" : "Off"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="font-display text-2xl font-bold">Job queue</h2>
          <p className="text-sm">{Object.entries(byStatus).map(([k, v]) => `${k}: ${v}`).join(" · ") || "empty"}</p>
          <ul className="space-y-2">
            {jobs.slice(0, 12).map((j) => (
              <li key={j.id} className="rounded-xl border-2 border-ink bg-paper p-3 text-sm">
                <p className="font-semibold">
                  {j.kind} · {j.status} · attempts {j.attempts}/{j.max_attempts}
                  {j.contains_private_data ? " · private" : ""}
                </p>
                <p className="text-xs text-ink-soft">
                  next {formatDateTime(j.next_run_at)} {j.error_code ? `· ${j.error_code}` : ""} {j.last_provider ? `· ${j.last_provider}/${j.last_model}` : ""}
                </p>
              </li>
            ))}
          </ul>
        </div>
        <div className="space-y-3">
          <h2 className="font-display text-2xl font-bold">Ingestion runs</h2>
          <ul className="space-y-2">
            {(overview.ingestion_runs ?? []).map((r: any) => (
              <li key={r.id} className="rounded-xl border-2 border-ink bg-paper p-3 text-sm">
                <p className="font-semibold">
                  {r.status} · {r.trigger} · {formatDateTime(r.created_at)}
                </p>
                <p className="text-xs text-ink-soft">
                  fetched {r.fetched} · new {r.inserted} · dup {r.duplicates} · clustered {r.clustered}
                  {r.errors?.length ? ` · ${r.errors.map((e: any) => e.error).join("; ")}` : ""}
                </p>
              </li>
            ))}
            {!overview.ingestion_runs?.length ? <li className="text-sm text-ink-soft">No runs yet.</li> : null}
          </ul>
        </div>
      </section>
    </div>
  );
}
