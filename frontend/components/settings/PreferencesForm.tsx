"use client";

import { Download, ShieldCheck, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ReactNode, useState } from "react";
import { CandyButton } from "@/components/design-system/CandyButton";
import type { Category, CrunchDisclosure, Exam, Preferences } from "@/lib/api-types";
import { CATEGORY_META, CATEGORY_ORDER } from "@/lib/categories";
import { api } from "@/lib/client-api";
import { cn } from "@/lib/cn";
import { EXAM_LABELS } from "@/lib/format";

const REGIONS = ["West Bengal", "Assam", "Tripura", "Jharkhand", "Odisha", "Bihar", "Delhi", "Maharashtra", "Karnataka", "Tamil Nadu", "Other / All India"];
const INTENSITY = [
  "Formal English summaries, minimal Banglish.",
  "Halka Banglish - mostly English with a little flavour.",
  "Banglish balanced - 'Bro, eta bookmark kore rakh, exam-e kaje lagbe.'",
  "Full adda mode - 'Demnn, eta ekdom must-know scene dudee!'",
];

function Section({ title, children, id }: { title: string; children: ReactNode; id?: string }) {
  return (
    <section id={id} className="scroll-mt-28 space-y-4 rounded-[22px] border-2 border-ink bg-paper p-5 shadow-brutal sm:p-6">
      <h2 className="font-display text-2xl font-bold">{title}</h2>
      {children}
    </section>
  );
}

export function PreferencesForm({
  initial,
  disclosure,
  displayName,
  mode = "settings",
  logoutAction,
}: {
  initial: Preferences;
  disclosure: CrunchDisclosure;
  displayName: string;
  mode?: "settings" | "onboarding";
  logoutAction?: () => Promise<void>;
}) {
  const router = useRouter();
  const [prefs, setPrefs] = useState<Preferences>(initial);
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [confirmName, setConfirmName] = useState("");
  const set = <K extends keyof Preferences>(key: K, value: Preferences[K]) => setPrefs((p) => ({ ...p, [key]: value }));

  async function save(markOnboarded = false) {
    setSaving(true);
    setMessage(null);
    try {
      const saved = await api<Preferences>("me/preferences", { method: "PUT", body: { ...prefs, mark_onboarded: markOnboarded } });
      setPrefs(saved);
      setMessage("Saved ✓ - tomorrow's quiz will follow these settings.");
      if (mode === "onboarding") {
        router.push("/");
        router.refresh();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Save hoyni.");
    } finally {
      setSaving(false);
    }
  }

  async function exportData() {
    setExporting(true);
    try {
      const res = await fetch("/api/backend/me/export");
      if (!res.ok) {
        setMessage("Export failed - try again.");
        return;
      }
      const blob = new Blob([JSON.stringify(await res.json(), null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "news-yapper-export.json";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  async function deleteAccount() {
    setDeleting(true);
    try {
      await api("me", { method: "DELETE" });
      if (logoutAction) await logoutAction();
    } catch (err) {
      setDeleting(false);
      setMessage(err instanceof Error ? err.message : "Delete failed.");
    }
  }

  const examSection = (
    <Section title="Exam & region">
      <fieldset>
        <legend className="mb-2 font-semibold">Main target exam</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {(Object.keys(EXAM_LABELS) as Exam[]).map((exam) => (
            <label key={exam} className="cursor-pointer">
              <input type="radio" name="target_exam" className="peer sr-only" checked={prefs.target_exam === exam} onChange={() => set("target_exam", exam)} />
              <span className="flex min-h-14 items-center justify-center rounded-2xl border-2 border-ink bg-cream px-3 text-center font-display font-bold peer-checked:bg-mango peer-checked:shadow-brutal-sm peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ink">
                {EXAM_LABELS[exam]}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <label className="flex flex-col gap-1 font-semibold">
        Region (for state PSC flavour)
        <select value={prefs.region} onChange={(e) => set("region", e.target.value)} className="min-h-11 rounded-xl border-2 border-ink bg-cream px-2">
          {REGIONS.map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </label>
    </Section>
  );

  const topicsSection = (
    <Section title="Topics you love (or need)">
      <div className="flex flex-wrap gap-2">
        {CATEGORY_ORDER.map((c: Category) => {
          const on = prefs.topics.includes(c);
          const meta = CATEGORY_META[c];
          return (
            <button
              key={c}
              type="button"
              aria-pressed={on}
              onClick={() => set("topics", on ? prefs.topics.filter((t) => t !== c) : [...prefs.topics, c])}
              className={cn("inline-flex min-h-11 items-center gap-2 rounded-full border-2 border-ink px-3 font-display font-bold", on ? "bg-ink text-cream" : "bg-cream")}
            >
              <meta.Sticker className="size-6" />
              {meta.short}
            </button>
          );
        })}
      </div>
      <p className="text-sm text-ink-soft">Picked topics get a small boost in your daily quiz. Weak topics get one automatically.</p>
    </Section>
  );

  const styleSection = (
    <Section title="Style & time">
      <label className="flex flex-col gap-2 font-semibold">
        Banglish intensity: {prefs.banglish_intensity}
        <input type="range" min={0} max={3} value={prefs.banglish_intensity} onChange={(e) => set("banglish_intensity", Number(e.target.value))} className="accent-[#F05A28]" />
        <span className="rounded-xl border-2 border-dashed border-ink bg-cream p-3 font-normal">{INTENSITY[prefs.banglish_intensity]}</span>
      </label>
      <fieldset>
        <legend className="mb-2 font-semibold">Tone</legend>
        <div className="flex flex-wrap gap-2">
          {(["chill", "balanced", "serious"] as const).map((t) => (
            <button key={t} type="button" aria-pressed={prefs.tone_preference === t} onClick={() => set("tone_preference", t)} className={cn("min-h-11 rounded-xl border-2 border-ink px-4 font-semibold capitalize", prefs.tone_preference === t ? "bg-mango" : "bg-cream")}>
              {t}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 font-semibold">
          Minutes per day: {prefs.daily_minutes}
          <input type="range" min={5} max={60} step={5} value={prefs.daily_minutes} onChange={(e) => set("daily_minutes", Number(e.target.value))} className="accent-[#F05A28]" />
        </label>
        <label className="flex flex-col gap-1 font-semibold">
          Daily quiz goal: {prefs.daily_goal} questions
          <input type="range" min={10} max={15} value={Math.min(15, Math.max(10, prefs.daily_goal))} onChange={(e) => set("daily_goal", Number(e.target.value))} className="accent-[#F05A28]" />
        </label>
      </div>
    </Section>
  );

  if (mode === "onboarding") {
    const steps = [examSection, topicsSection, styleSection];
    return (
      <div className="space-y-5">
        <ol className="flex gap-2" aria-label={`Step ${step + 1} of 3`}>
          {steps.map((_, i) => (
            <li key={i} className={cn("h-3 flex-1 rounded-full border-2 border-ink", i <= step ? "bg-punch" : "bg-paper")} />
          ))}
        </ol>
        {steps[step]}
        <div className="flex justify-between gap-2">
          <CandyButton tone="paper" disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
            Back
          </CandyButton>
          {step < steps.length - 1 ? (
            <CandyButton tone="mango" onClick={() => setStep((s) => s + 1)}>
              Next
            </CandyButton>
          ) : (
            <CandyButton tone="punch" loading={saving} loadingText="Saving..." onClick={() => void save(true)}>
              Let&apos;s go! ☕
            </CandyButton>
          )}
        </div>
        {message ? <p aria-live="polite" className="font-semibold">{message}</p> : null}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {examSection}
      {topicsSection}
      {styleSection}
      <Section title="Reminders & community">
        <label className="flex items-center gap-3 font-semibold">
          <input type="checkbox" checked={prefs.study_reminders} onChange={(e) => set("study_reminders", e.target.checked)} className="size-5 accent-[#F05A28]" />
          Daily study reminder
        </label>
        {prefs.study_reminders ? (
          <label className="flex items-center gap-2 font-semibold">
            Time
            <input type="time" value={prefs.reminder_time ?? "20:00"} onChange={(e) => set("reminder_time", e.target.value)} className="min-h-11 rounded-xl border-2 border-ink bg-cream px-2" />
          </label>
        ) : null}
        <p className="text-sm text-ink-soft">Your reminder preference is saved; notification delivery isn&apos;t switched on in this build.</p>
        <label className="flex items-center gap-3 font-semibold">
          <input type="checkbox" checked={prefs.leaderboard_opt_in} onChange={(e) => set("leaderboard_opt_in", e.target.checked)} className="size-5 accent-[#F05A28]" />
          Show me on public leaderboards (opt-in, off by default)
        </label>
      </Section>
      <Section title="Privacy: AI & your notes" id="privacy">
        <p className="flex gap-2 text-sm">
          <ShieldCheck className="size-5 shrink-0 text-mint-deep" aria-hidden="true" />
          Sticky notes and mistakes are private. They only leave this server if you run an <strong>AI</strong> Crunch, and
          only to the providers you allow below. The offline Crunch engine never sends them anywhere.
        </p>
        <fieldset className="space-y-2">
          <legend className="sr-only">AI consent for Crunch</legend>
          {(
            [
              ["none", "No AI - offline Crunch only"],
              ["primary_only", `Primary AI provider only${disclosure.primary_provider ? ` (${disclosure.primary_provider})` : ""}`],
              ["allow_fallback", `Primary + fallback provider${disclosure.fallback_providers.length ? ` (${disclosure.fallback_providers.join(", ")})` : ""}`],
            ] as const
          ).map(([value, label]) => (
            <label key={value} className={cn("flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border-2 border-ink px-3", prefs.crunch_ai_consent === value ? "bg-mint" : "bg-cream")}>
              <input type="radio" name="consent" checked={prefs.crunch_ai_consent === value} onChange={() => set("crunch_ai_consent", value)} className="size-4 accent-[#F05A28]" />
              <span className="font-semibold">{label}</span>
            </label>
          ))}
        </fieldset>
        <p className="text-sm text-ink-soft">
          {disclosure.ai_available
            ? disclosure.private_fallback_allowed_by_server
              ? "This server allows private-note fallback only for users who choose it."
              : "This server never sends private notes to a fallback provider, whatever you choose."
            : "No AI provider is configured on this server right now, so Crunch runs offline."}
        </p>
      </Section>

      <div className="sticky bottom-24 z-20 flex flex-wrap items-center gap-3 rounded-2xl border-2 border-ink bg-cream/95 p-3 shadow-brutal backdrop-blur lg:bottom-6">
        <CandyButton tone="punch" loading={saving} loadingText="Saving..." onClick={() => void save()}>
          Save settings
        </CandyButton>
        <p aria-live="polite" className="text-sm font-semibold">
          {message}
        </p>
      </div>

      <Section title="Your data">
        <div className="flex flex-wrap gap-3">
          <CandyButton tone="lavender" loading={exporting} loadingText="Preparing export..." onClick={() => void exportData()}>
            <Download className="size-5" aria-hidden="true" /> Export everything (JSON)
          </CandyButton>
        </div>
        <div className="space-y-2 rounded-xl border-2 border-dashed border-pink-deep p-4">
          <p className="font-semibold">Delete account</p>
          <p className="text-sm text-ink-soft">
            Permanently deletes your notes, snapshots, mistakes, quiz history, crunches and flashcards. Type your display
            name (<strong>{displayName}</strong>) to confirm.
          </p>
          <div className="flex flex-wrap gap-2">
            <input value={confirmName} onChange={(e) => setConfirmName(e.target.value)} aria-label="Type your display name to confirm deletion" className="min-h-11 rounded-xl border-2 border-ink bg-paper px-3" />
            <CandyButton
              tone="pink"
              disabled={confirmName !== displayName}
              loading={deleting}
              loadingText="Deleting..."
              onClick={() => void deleteAccount()}
            >
              <Trash2 className="size-5" aria-hidden="true" /> Delete forever
            </CandyButton>
          </div>
        </div>
      </Section>
    </div>
  );
}
