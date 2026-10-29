"use client";

import { Check, ExternalLink, X } from "lucide-react";
import { type ReactNode, useState } from "react";
import { CandyButton } from "@/components/design-system/CandyButton";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import type { Mistake } from "@/lib/api-types";
import { categoryMeta } from "@/lib/categories";
import { api } from "@/lib/client-api";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/format";

const LETTERS = ["A", "B", "C", "D"];

export function WrongAnswerCard({
  mistake,
  compact = false,
  onChange,
  selectControl,
}: {
  mistake: Mistake;
  compact?: boolean;
  onChange?: (m: Mistake) => void;
  selectControl?: ReactNode;
}) {
  const [current, setCurrent] = useState(mistake);
  const [mode, setMode] = useState<"view" | "retry">("view");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const meta = categoryMeta(current.topic);

  async function review(body: { action: "answer" | "snooze"; selected_index?: number }) {
    setBusy(true);
    try {
      const res = await api<{ mistake: Mistake; is_correct: boolean | null }>(`mistakes/${current.id}/review`, {
        method: "POST",
        body,
      });
      setCurrent(res.mistake);
      onChange?.(res.mistake);
      if (body.action === "snooze") setFeedback("Kal abar dekhabo ⏰");
      else setFeedback(res.is_correct ? "Ebar thik! Resolved - history stays in your attempts. ✅" : "Ekhono bhul - kal abar try kor.");
      setMode("view");
    } catch (err) {
      setFeedback(err instanceof Error ? err.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article
      className={cn(
        "relative flex flex-col gap-3 rounded-2xl border-2 border-ink p-4 shadow-brutal-sm",
        current.status === "resolved" ? "bg-mint" : "bg-pink",
      )}
    >
      <span aria-hidden="true" className="absolute -top-2.5 right-6 h-5 w-10 rounded-sm border border-ink/30 bg-paper/70" />
      <div className="flex flex-wrap items-center gap-1.5">
        {selectControl}
        <StickerBadge tone="paper" tilt={0} icon={<meta.Sticker />}>
          {meta.short}
        </StickerBadge>
        <StickerBadge tone={current.status === "resolved" ? "paper" : "ink"} tilt={0}>
          {current.status === "resolved" ? "Resolved" : `Wrong ×${current.error_count}`}
        </StickerBadge>
      </div>
      <h3 className={cn("font-display leading-snug font-bold", compact ? "text-base" : "text-lg")}>{current.prompt}</h3>
      {mode === "view" ? (
        <dl className="grid gap-1.5 text-sm">
          <div className="flex items-start gap-2">
            <dt className="flex shrink-0 items-center gap-1 font-bold">
              <X className="size-4" aria-hidden="true" /> You picked:
            </dt>
            <dd>{current.options[current.incorrect_choice]}</dd>
          </div>
          <div className="flex items-start gap-2">
            <dt className="flex shrink-0 items-center gap-1 font-bold">
              <Check className="size-4" aria-hidden="true" /> Correct:
            </dt>
            <dd>{current.options[current.correct_choice]}</dd>
          </div>
        </dl>
      ) : (
        <div className="grid gap-2" role="group" aria-label="Try again">
          {current.options.map((opt, i) => (
            <button
              key={i}
              type="button"
              disabled={busy}
              onClick={() => void review({ action: "answer", selected_index: i })}
              className="flex min-h-11 items-center gap-2 rounded-xl border-2 border-ink bg-paper px-3 text-left font-semibold hover:bg-mango"
            >
              <span className="font-display font-bold">{LETTERS[i]}</span> {opt}
            </button>
          ))}
        </div>
      )}
      {!compact ? (
        <details className="group rounded-xl border-2 border-ink bg-paper/80 p-3">
          <summary className="cursor-pointer list-none font-semibold marker:hidden">
            Why was mine wrong? <span className="text-ink-soft group-open:hidden">(tap)</span>
          </summary>
          <p className="mt-2 text-sm leading-relaxed">{current.explanation}</p>
          {current.evidence_urls.map((url) => (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="mt-2 inline-flex items-center gap-1 text-sm font-semibold text-punch-deep hover:underline"
            >
              Evidence <ExternalLink className="size-3.5" aria-hidden="true" />
              <span className="sr-only">(new tab)</span>
            </a>
          ))}
        </details>
      ) : null}
      {current.status === "active" ? (
        <div className="flex flex-wrap gap-2">
          {mode === "view" ? (
            <CandyButton tone="paper" size="sm" onClick={() => setMode("retry")} disabled={busy}>
              Review now
            </CandyButton>
          ) : (
            <CandyButton tone="paper" size="sm" onClick={() => setMode("view")} disabled={busy}>
              Cancel
            </CandyButton>
          )}
          <CandyButton tone="lavender" size="sm" onClick={() => void review({ action: "snooze" })} disabled={busy}>
            Review tomorrow
          </CandyButton>
        </div>
      ) : null}
      <p aria-live="polite" className="text-sm font-semibold">
        {feedback ?? (current.review_after ? `Next review: ${formatDate(current.review_after)}` : "")}
      </p>
    </article>
  );
}
