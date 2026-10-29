"use client";

import { ExternalLink, RotateCcw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { candyClasses } from "@/components/design-system/CandyButton";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { StickyNote } from "@/components/design-system/StickyNote";
import { SparkleSticker } from "@/components/design-system/stickers";
import type { CrunchBullet, CrunchOutput, Flashcard } from "@/lib/api-types";
import { cn } from "@/lib/cn";

function RefChips({ refs, legend }: { refs: string[]; legend: Map<string, CrunchOutput["source_refs"][number]> }) {
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
      {refs.map((r) => {
        const src = legend.get(r);
        return (
          <a
            key={r}
            href={`#ref-${r}`}
            title={src ? `${src.type}: ${src.title}` : r}
            className={cn(
              "rounded-md border border-ink px-1 text-[0.7rem] font-bold leading-5",
              src?.verified ? "bg-mint" : "bg-paper",
            )}
          >
            {r}
          </a>
        );
      })}
    </span>
  );
}

function Bullet({ b, legend }: { b: CrunchBullet; legend: Map<string, CrunchOutput["source_refs"][number]> }) {
  return (
    <li className="flex gap-2 leading-relaxed">
      <span aria-hidden="true" className="mt-2 size-2 shrink-0 rounded-full border border-ink bg-punch" />
      <span>
        {b.text}
        <RefChips refs={b.source_refs} legend={legend} />
        {b.verified === false ? <span className="ml-1 text-xs font-semibold text-ink-soft">(your note · unverified)</span> : null}
      </span>
    </li>
  );
}

function FlipCard({ card }: { card: Flashcard }) {
  const [flipped, setFlipped] = useState(false);
  return (
    <button
      type="button"
      onClick={() => setFlipped((f) => !f)}
      aria-pressed={flipped}
      className={cn(
        "flex min-h-36 flex-col justify-between gap-2 rounded-2xl border-2 border-ink p-4 text-left shadow-brutal-sm transition-colors",
        flipped ? "bg-mint" : "bg-paper",
      )}
    >
      <span className="text-xs font-bold tracking-wide uppercase">{flipped ? "Answer" : "Question"}</span>
      <span className="font-display text-lg leading-snug font-bold">{flipped ? card.back : card.front}</span>
      <span className="flex items-center gap-1 text-xs font-semibold text-ink-soft">
        <RotateCcw className="size-3.5" aria-hidden="true" /> Tap to flip
      </span>
    </button>
  );
}

export function CrunchResult({ output }: { output: CrunchOutput }) {
  const legend = new Map(output.source_refs.map((r) => [r.ref, r]));
  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[24px] border-2 border-ink bg-mango p-6 shadow-brutal-lg sm:p-8">
        <SparkleSticker className="absolute top-3 right-4 size-16" />
        <div className="flex flex-wrap gap-2">
          <StickerBadge tone="ink" tilt={-2}>
            {output.engine === "ai" ? `AI · ${output.model}` : "Offline engine · no AI"}
          </StickerBadge>
          <StickerBadge tone="paper" tilt={1}>
            {output.flashcards.length} cards saved to Revision
          </StickerBadge>
        </div>
        <h2 className="mt-3 max-w-3xl font-display text-3xl leading-tight font-bold sm:text-4xl">Crunch it ✨ - {output.title}</h2>
        {output.warnings.length ? (
          <ul className="mt-4 space-y-1 text-sm">
            {output.warnings.map((w) => (
              <li key={w} className="flex gap-2">
                <span aria-hidden="true">•</span>
                {w}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-6">
          <section className="rounded-[20px] border-2 border-ink bg-paper p-6 shadow-brutal">
            <h3 className="font-display text-2xl font-bold">Revision points</h3>
            <ul className="mt-3 space-y-2">
              {output.concise_bullets.map((b, i) => (
                <Bullet key={i} b={b} legend={legend} />
              ))}
            </ul>
          </section>

          {output.topic_sections.length > 1 ? (
            <section className="grid gap-4 sm:grid-cols-2">
              {output.topic_sections.map((s) => (
                <div key={s.topic} className="rounded-2xl border-2 border-ink bg-lavender p-4">
                  <h3 className="font-display text-lg font-bold capitalize">{s.topic}</h3>
                  <ul className="mt-2 space-y-1.5 text-sm">
                    {s.bullets.map((b, i) => (
                      <Bullet key={i} b={b} legend={legend} />
                    ))}
                  </ul>
                </div>
              ))}
            </section>
          ) : null}

          {output.exam_traps.length ? (
            <section className="space-y-3">
              <h3 className="font-display text-2xl font-bold">Exam traps 🪤</h3>
              <ul className="grid gap-3">
                {output.exam_traps.map((t, i) => (
                  <li key={i} className="rounded-2xl border-2 border-ink bg-pink p-4">
                    {t.text}
                    <RefChips refs={t.source_refs} legend={legend} />
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {output.flashcards.length ? (
            <section className="space-y-3">
              <div className="flex flex-wrap items-end justify-between gap-2">
                <h3 className="font-display text-2xl font-bold">Flashcards</h3>
                <Link href="/revision" className={candyClasses("punch", "sm")}>
                  Review them now
                </Link>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {output.flashcards.map((c) => (
                  <FlipCard key={c.id} card={c} />
                ))}
              </div>
            </section>
          ) : null}
        </div>

        <aside className="space-y-5">
          {output.mnemonics.length ? (
            <StickyNote
              id={`mn-${output.id}`}
              title="Memory hooks 🧠"
              body={output.mnemonics.map((m) => `- ${m}`).join("\n")}
              color="mint"
            />
          ) : null}
          <section className="rounded-[20px] border-2 border-ink bg-cream-deep p-4">
            <h3 className="font-display text-lg font-bold">Sources used</h3>
            <ul className="mt-2 space-y-2 text-sm">
              {output.source_refs.map((r) => (
                <li key={r.ref} id={`ref-${r.ref}`} className="scroll-mt-28 rounded-xl border-2 border-ink bg-paper p-2.5">
                  <span className="mr-1 rounded-md border border-ink bg-mango px-1 text-xs font-bold">{r.ref}</span>
                  <span className="font-semibold">{r.title}</span>
                  <span className="block text-xs text-ink-soft">
                    {r.type} · {r.verified ? "verified source" : "user-provided, unverified"}
                  </span>
                  {r.url ? (
                    <a href={r.url} target="_blank" rel="noopener noreferrer nofollow" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-punch-deep hover:underline">
                      Open source <ExternalLink className="size-3" aria-hidden="true" />
                      <span className="sr-only">(new tab)</span>
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>
    </div>
  );
}
