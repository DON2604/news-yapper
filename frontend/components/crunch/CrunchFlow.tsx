"use client";

import { Check, Loader2, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { CandyButton } from "@/components/design-system/CandyButton";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { Mascot } from "@/components/design-system/stickers";
import { CrunchResult } from "@/components/crunch/CrunchResult";
import type { CrunchJob, CrunchOutput, CrunchPreview, CrunchSettings, Mistake, Note, Snapshot } from "@/lib/api-types";
import { api } from "@/lib/client-api";
import { cn } from "@/lib/cn";
import { EXAM_LABELS } from "@/lib/format";

type Kind = "notes" | "snapshots" | "mistakes";
const STAGES = [
  { key: "collect", label: "Collecting your items" },
  { key: "digest", label: "Fingerprinting the exact versions (SHA-256)" },
  { key: "queue", label: "Waiting in the job queue" },
  { key: "crunch", label: "Crunching" },
  { key: "save", label: "Saving points + flashcards" },
] as const;

function stageIndex(job: CrunchJob | null): number {
  if (!job) return 1;
  if (job.status === "queued" || job.status === "deferred") return 2;
  if (job.status === "running") return 3;
  if (job.status === "completed") return 5;
  return 2;
}

export function CrunchFlow({
  notes,
  snapshots,
  mistakes,
  preselected,
  initialOutput,
  consent,
}: {
  notes: Note[];
  snapshots: Snapshot[];
  mistakes: Mistake[];
  preselected: Record<Kind, string[]>;
  initialOutput: CrunchOutput | null;
  consent: string;
}) {
  const [tab, setTab] = useState<Kind>(preselected.snapshots.length && !preselected.notes.length ? "snapshots" : "notes");
  const [selected, setSelected] = useState<Record<Kind, string[]>>(preselected);
  const [lastWeek, setLastWeek] = useState(false);
  const [settings, setSettings] = useState<CrunchSettings>({ length: "short", language: "banglish", exam: "SSC", flashcards: 8, include_traps: true });
  const [engine, setEngine] = useState<"auto" | "offline" | "ai">("auto");
  const [preview, setPreview] = useState<CrunchPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [job, setJob] = useState<CrunchJob | null>(null);
  const [output, setOutput] = useState<CrunchOutput | null>(initialOutput);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const pollRef = useRef<number | null>(null);

  const body = useMemo(
    () => ({
      note_ids: selected.notes,
      snapshot_ids: selected.snapshots,
      mistake_ids: selected.mistakes,
      last_week: lastWeek,
      settings,
      engine,
    }),
    [selected, lastWeek, settings, engine],
  );
  const count = selected.notes.length + selected.snapshots.length + selected.mistakes.length;

  useEffect(() => {
    if (!count && !lastWeek) return;
    const t = window.setTimeout(async () => {
      try {
        setPreview(await api<CrunchPreview>("crunch/preview", { method: "POST", body }));
        setPreviewError(null);
      } catch (err) {
        setPreview(null);
        setPreviewError(err instanceof Error ? err.message : "Preview failed");
      }
    }, 350);
    return () => window.clearTimeout(t);
  }, [body, count, lastWeek]);

  useEffect(() => () => {
    if (pollRef.current) window.clearTimeout(pollRef.current);
  }, []);

  async function poll(id: string) {
    try {
      const next = await api<CrunchJob>(`crunch/jobs/${id}`);
      setJob(next);
      if (next.status === "completed" && next.output_id) {
        setOutput(await api<CrunchOutput>(`crunch/outputs/${next.output_id}`));
        return;
      }
      if (next.status === "failed") return;
      pollRef.current = window.setTimeout(() => void poll(id), next.status === "deferred" ? 5000 : 1500);
    } catch {
      pollRef.current = window.setTimeout(() => void poll(id), 4000);
    }
  }

  async function crunch() {
    setSubmitting(true);
    setError(null);
    setOutput(null);
    try {
      const created = await api<CrunchJob>("crunch", { method: "POST", body });
      setJob(created);
      if (created.cached && created.output_id) {
        setOutput(await api<CrunchOutput>(`crunch/outputs/${created.output_id}`));
      } else {
        void poll(created.id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Crunch start hoyni.");
    } finally {
      setSubmitting(false);
    }
  }

  function toggle(kind: Kind, id: string) {
    setSelected((s) => ({ ...s, [kind]: s[kind].includes(id) ? s[kind].filter((x) => x !== id) : [...s[kind], id] }));
  }

  if (output) {
    return (
      <div className="space-y-5">
        {job?.cached ? (
          <p className="rounded-2xl border-2 border-ink bg-mint px-4 py-3 font-semibold">
            Same items, same settings - served from cache instantly, no model call needed. ⚡
          </p>
        ) : null}
        <CrunchResult output={output} />
        <div className="flex justify-center">
          <CandyButton tone="paper" onClick={() => { setOutput(null); setJob(null); }}>
            Crunch something else
          </CandyButton>
        </div>
      </div>
    );
  }

  if (job && job.status !== "completed") {
    const active = stageIndex(job);
    return (
      <section className="mx-auto max-w-2xl rounded-[24px] border-2 border-ink bg-ink p-6 text-cream shadow-brutal-lg sm:p-8" aria-live="polite">
        <div className="flex items-center gap-4">
          <Mascot mood={job.status === "deferred" ? "sleepy" : job.status === "failed" ? "oops" : "think"} className="size-24 shrink-0" />
          <div>
            <p className="font-display text-xs font-bold tracking-[0.2em] text-mango uppercase">
              {job.engine === "ai" ? "AI crunch" : "Offline crunch"} · {job.item_count} items
            </p>
            <h2 className="font-display text-3xl font-bold">
              {job.status === "failed" ? "Crunch atke gelo" : job.status === "deferred" ? "Queue-e wait korchhi..." : "Crunching..."}
            </h2>
          </div>
        </div>
        <ol className="mt-6 space-y-3">
          {STAGES.map((stage, i) => {
            const done = i < active;
            const current = i === active && job.status !== "failed";
            return (
              <li key={stage.key} className={cn("flex items-center gap-3", !done && !current && "opacity-50")}>
                <span className={cn("grid size-8 place-items-center rounded-full border-2", done ? "border-mint bg-mint text-ink" : "border-cream")}>
                  {done ? <Check className="size-4" aria-hidden="true" /> : current ? <Loader2 className="size-4 motion-safe:animate-spin" aria-hidden="true" /> : i + 1}
                </span>
                <span className="font-semibold">{stage.label}</span>
              </li>
            );
          })}
        </ol>
        {job.status_message ? <p className="mt-5 rounded-xl border-2 border-cream/40 p-3 text-sm">{job.status_message}</p> : null}
        {job.status === "failed" || job.status === "deferred" ? (
          <div className="mt-5 flex flex-wrap gap-2">
            {job.engine === "ai" ? (
              <CandyButton tone="mango" onClick={() => { setEngine("offline"); setJob(null); }}>
                Use the offline engine instead
              </CandyButton>
            ) : null}
            <CandyButton tone="paper" onClick={() => setJob(null)}>
              Back to selection
            </CandyButton>
          </div>
        ) : null}
      </section>
    );
  }

  const tabs: { kind: Kind; label: string; total: number }[] = [
    { kind: "notes", label: "Stickies", total: notes.length },
    { kind: "snapshots", label: "Saved articles", total: snapshots.length },
    { kind: "mistakes", label: "Mistakes", total: mistakes.length },
  ];
  const listItems =
    tab === "notes"
      ? notes.map((n) => ({ id: n.id, title: n.title || n.body.slice(0, 60) || "Untitled", sub: n.tags.map((t) => `#${t}`).join(" ") }))
      : tab === "snapshots"
        ? snapshots.map((s) => ({ id: s.id, title: s.saved_title, sub: s.verified ? "source-checked" : "headline only" }))
        : mistakes.map((m) => ({ id: m.id, title: m.prompt, sub: `wrong ×${m.error_count}` }));

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <section className="space-y-4 rounded-[22px] border-2 border-ink bg-paper p-5 shadow-brutal">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-2xl font-bold">1 · Ki ki crunch korbi?</h2>
          <label className="inline-flex min-h-11 items-center gap-2 rounded-xl border-2 border-ink bg-lavender px-3 font-semibold">
            <input type="checkbox" checked={lastWeek} onChange={(e) => setLastWeek(e.target.checked)} className="size-4 accent-[#F05A28]" />
            Add last week&apos;s study
          </label>
        </div>
        <div role="tablist" aria-label="Item type" className="flex flex-wrap gap-2">
          {tabs.map((t) => (
            <button
              key={t.kind}
              role="tab"
              type="button"
              aria-selected={tab === t.kind}
              onClick={() => setTab(t.kind)}
              className={cn("min-h-11 rounded-xl border-2 border-ink px-3 font-display font-bold", tab === t.kind ? "bg-mango shadow-brutal-sm" : "bg-cream")}
            >
              {t.label} <span className="text-ink-soft">({selected[t.kind].length}/{t.total})</span>
            </button>
          ))}
        </div>
        {listItems.length === 0 ? (
          <p className="rounded-xl border-2 border-dashed border-ink p-4 text-ink-soft">
            Nothing here yet.{" "}
            {tab === "notes" ? (
              <Link href="/brain-dump" className="font-semibold underline">Write a sticky</Link>
            ) : tab === "snapshots" ? (
              <Link href="/news" className="font-semibold underline">Pin an article</Link>
            ) : (
              <Link href="/quiz/daily" className="font-semibold underline">Take the daily quiz</Link>
            )}{" "}
            first.
          </p>
        ) : (
          <>
            <div className="flex gap-2 text-sm">
              <button type="button" className="min-h-10 rounded-lg px-2 font-semibold underline" onClick={() => setSelected((s) => ({ ...s, [tab]: listItems.map((i) => i.id) }))}>
                Select all
              </button>
              <button type="button" className="min-h-10 rounded-lg px-2 font-semibold underline" onClick={() => setSelected((s) => ({ ...s, [tab]: [] }))}>
                Clear
              </button>
            </div>
            <ul className="grid max-h-[28rem] gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
              {listItems.map((item) => {
                const checked = selected[tab].includes(item.id);
                return (
                  <li key={item.id}>
                    <label className={cn("flex min-h-14 cursor-pointer items-start gap-3 rounded-xl border-2 border-ink p-3", checked ? "bg-mint" : "bg-cream hover:bg-cream-deep")}>
                      <input type="checkbox" checked={checked} onChange={() => toggle(tab, item.id)} className="mt-1 size-4 shrink-0 accent-[#F05A28]" />
                      <span>
                        <span className="line-clamp-2 font-semibold">{item.title}</span>
                        {item.sub ? <span className="text-xs text-ink-soft">{item.sub}</span> : null}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </section>

      <aside className="space-y-5">
        <section className="space-y-4 rounded-[22px] border-2 border-ink bg-cream-deep p-5 shadow-brutal">
          <h2 className="font-display text-2xl font-bold">2 · Kemon chai?</h2>
          <fieldset className="space-y-2">
            <legend className="font-semibold">Length</legend>
            <div className="flex gap-2">
              {(["short", "detailed"] as const).map((v) => (
                <button key={v} type="button" aria-pressed={settings.length === v} onClick={() => setSettings({ ...settings, length: v })} className={cn("min-h-11 flex-1 rounded-xl border-2 border-ink font-semibold", settings.length === v ? "bg-mango" : "bg-paper")}>
                  {v === "short" ? "Very short" : "Detailed"}
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset className="space-y-2">
            <legend className="font-semibold">Language</legend>
            <div className="flex gap-2">
              {(["banglish", "english"] as const).map((v) => (
                <button key={v} type="button" aria-pressed={settings.language === v} onClick={() => setSettings({ ...settings, language: v })} className={cn("min-h-11 flex-1 rounded-xl border-2 border-ink font-semibold capitalize", settings.language === v ? "bg-mango" : "bg-paper")}>
                  {v}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="flex flex-col gap-1 font-semibold">
            Exam
            <select value={settings.exam} onChange={(e) => setSettings({ ...settings, exam: e.target.value as CrunchSettings["exam"] })} className="min-h-11 rounded-xl border-2 border-ink bg-paper px-2">
              {Object.entries(EXAM_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 font-semibold">
            Flashcards: {settings.flashcards}
            <input type="range" min={5} max={15} value={settings.flashcards} onChange={(e) => setSettings({ ...settings, flashcards: Number(e.target.value) })} className="accent-[#F05A28]" />
          </label>
          <label className="flex items-center gap-2 font-semibold">
            <input type="checkbox" checked={settings.include_traps} onChange={(e) => setSettings({ ...settings, include_traps: e.target.checked })} className="size-4 accent-[#F05A28]" />
            Include exam traps
          </label>
          <label className="flex flex-col gap-1 font-semibold">
            Engine
            <select value={engine} onChange={(e) => setEngine(e.target.value as typeof engine)} className="min-h-11 rounded-xl border-2 border-ink bg-paper px-2">
              <option value="auto">Auto (AI if allowed, else offline)</option>
              <option value="offline">Offline - nothing leaves this server</option>
              <option value="ai">AI provider (needs consent)</option>
            </select>
          </label>
        </section>

        <section className="space-y-3 rounded-[22px] border-2 border-ink bg-paper p-5 shadow-brutal">
          <h2 className="font-display text-2xl font-bold">3 · Preview</h2>
          {!count && !lastWeek ? (
            <p className="text-ink-soft">Select a few items to see the preview.</p>
          ) : previewError ? (
            <p role="alert" className="rounded-xl border-2 border-ink bg-pink p-3 text-sm font-semibold">{previewError}</p>
          ) : preview ? (
            <>
              <div className="flex flex-wrap gap-2">
                <StickerBadge tone={preview.within_budget ? "mint" : "pink"} tilt={0}>
                  {preview.items.length} items · {preview.total_chars}/{preview.max_chars} chars
                </StickerBadge>
                <StickerBadge tone="paper" tilt={0}>~{preview.token_estimate} tokens</StickerBadge>
                <StickerBadge tone={preview.engine_resolved === "ai" ? "lavender" : "mango"} tilt={0}>
                  {preview.engine_resolved === "ai" ? "AI engine" : "Offline engine"}
                </StickerBadge>
              </div>
              {preview.engine_resolved === "ai" ? (
                <p className="flex gap-2 rounded-xl border-2 border-ink bg-lavender p-3 text-sm">
                  <ShieldAlert className="size-5 shrink-0" aria-hidden="true" />
                  <span>
                    Your selected private notes will be sent to{" "}
                    <strong>{preview.disclosure.recipients_with_current_consent.join(" then ") || preview.disclosure.primary_provider || "an AI provider once one is configured"}</strong>
                    {" "}for this Crunch. Consent: <strong>{consent.replace("_", " ")}</strong> -{" "}
                    <Link href="/settings#privacy" className="font-semibold underline">change</Link>.
                  </span>
                </p>
              ) : null}
              {preview.warnings.map((w) => (
                <p key={w} className="text-sm text-ink-soft">• {w}</p>
              ))}
              {preview.existing_job?.status === "completed" ? (
                <p className="text-sm font-semibold text-mint-deep">Already crunched with these exact versions - you&apos;ll get the cached result instantly.</p>
              ) : null}
            </>
          ) : (
            <p className="text-ink-soft">Calculating...</p>
          )}
          {error ? <p role="alert" className="rounded-xl border-2 border-ink bg-pink p-3 text-sm font-semibold">{error}</p> : null}
          <CandyButton
            tone="punch"
            size="lg"
            className="w-full"
            disabled={!preview || !preview.within_budget}
            loading={submitting}
            loadingText="Starting..."
            onClick={() => void crunch()}
          >
            Crunch it ✨
          </CandyButton>
        </section>
      </aside>
    </div>
  );
}
