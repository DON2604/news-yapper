"use client";

import { ExternalLink, RotateCcw } from "lucide-react";
import { useState } from "react";
import { CandyButton, CandyLink } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";
import { ProgressBurst } from "@/components/design-system/ProgressBurst";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import type { Flashcard } from "@/lib/api-types";
import { api } from "@/lib/client-api";
import { cn } from "@/lib/cn";
import { intervalLabel, nextIntervalDays, type Outcome } from "@/lib/srs";

const RATINGS: { outcome: Outcome; label: string; tone: "pink" | "mango" | "mint" | "lavender" }[] = [
  { outcome: "again", label: "Again", tone: "pink" },
  { outcome: "hard", label: "Hard", tone: "mango" },
  { outcome: "good", label: "Good", tone: "mint" },
  { outcome: "easy", label: "Easy", tone: "lavender" },
];

export function FlashcardDeck({ cards }: { cards: Flashcard[] }) {
  const [queue, setQueue] = useState(cards);
  const [flipped, setFlipped] = useState(false);
  const [rating, setRating] = useState<Outcome | null>(null);
  const [reviewed, setReviewed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const card = queue[0];

  if (!cards.length) {
    return (
      <EmptyState
        title="Kono card due nei 🎉"
        mood="happy"
        action={
          <CandyLink href="/brain-dump/crunch" tone="mango">
            Crunch notes into cards
          </CandyLink>
        }
      >
        Flashcards come from Crunch. Review them here on an SM-2 schedule - no AI call on flips or ratings.
      </EmptyState>
    );
  }

  if (!card) {
    return (
      <section className="relative overflow-hidden rounded-[24px] border-2 border-ink bg-mint p-8 text-center shadow-brutal-lg">
        <ProgressBurst fire />
        <p className="font-display text-4xl font-bold">Deck clear! {reviewed} reviewed ✅</p>
        <p className="mt-2 text-ink/80">Next reviews are scheduled automatically. Come back when they&apos;re due.</p>
      </section>
    );
  }

  async function rate(outcome: Outcome) {
    setRating(outcome);
    setError(null);
    try {
      await api(`flashcards/${card.id}/reviews`, { method: "POST", body: { outcome } });
      setReviewed((n) => n + 1);
      setFlipped(false);
      setQueue((q) => (outcome === "again" ? [...q.slice(1), card] : q.slice(1)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rating save hoyni.");
    } finally {
      setRating(null);
    }
  }

  const source = card.source_ref.items?.[0];
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between text-sm font-semibold">
        <span>{queue.length} left in this session</span>
        <span>{reviewed} reviewed</span>
      </div>
      <div className="[perspective:1400px]">
        <button
          type="button"
          onClick={() => setFlipped((f) => !f)}
          aria-label={flipped ? "Show question" : "Show answer"}
          className={cn(
            "relative block h-72 w-full rounded-[24px] text-left transition-transform duration-300 [transform-style:preserve-3d] motion-reduce:transition-none sm:h-80",
            flipped && "[transform:rotateY(180deg)]",
          )}
        >
          <span className="absolute inset-0 flex flex-col justify-between rounded-[24px] border-2 border-ink bg-paper p-6 shadow-brutal-lg [backface-visibility:hidden] sm:p-8">
            <span className="flex items-center gap-2">
              <StickerBadge tone="mango" tilt={-2}>
                Question
              </StickerBadge>
              {card.exam_topic ? <span className="text-sm font-semibold capitalize text-ink-soft">{card.exam_topic}</span> : null}
            </span>
            <span className="font-display text-2xl leading-snug font-bold sm:text-3xl">{card.front}</span>
            <span className="flex items-center gap-1 text-sm font-semibold text-ink-soft">
              <RotateCcw className="size-4" aria-hidden="true" /> Tap / Space to flip
            </span>
          </span>
          <span className="absolute inset-0 flex flex-col justify-between rounded-[24px] border-2 border-ink bg-mint p-6 shadow-brutal-lg [backface-visibility:hidden] [transform:rotateY(180deg)] sm:p-8">
            <StickerBadge tone="paper" tilt={2}>
              Answer
            </StickerBadge>
            <span className="font-display text-2xl leading-snug font-bold sm:text-3xl">{card.back}</span>
            <span className="text-sm font-semibold">
              {source ? `From ${source.type}: ${source.title}${source.verified ? "" : " (your note, unverified)"}` : ""}
            </span>
          </span>
        </button>
      </div>
      {source?.url ? (
        <a href={source.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1 text-sm font-semibold text-punch-deep hover:underline">
          Source <ExternalLink className="size-3.5" aria-hidden="true" />
          <span className="sr-only">(new tab)</span>
        </a>
      ) : null}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4" role="group" aria-label="How well did you remember?">
        {RATINGS.map((r) => (
          <CandyButton
            key={r.outcome}
            tone={r.tone}
            disabled={rating !== null || !flipped}
            loading={rating === r.outcome}
            loadingText="Saving..."
            onClick={() => void rate(r.outcome)}
            className="flex-col gap-0 py-2"
          >
            <span>{r.label}</span>
            <span className="text-xs font-semibold opacity-80">{intervalLabel(nextIntervalDays(card, r.outcome))}</span>
          </CandyButton>
        ))}
      </div>
      {!flipped ? <p className="text-center text-sm text-ink-soft">Flip the card first, then rate honestly.</p> : null}
      {error ? (
        <p role="alert" className="font-semibold text-pink-deep">
          {error}
        </p>
      ) : null}
    </div>
  );
}
