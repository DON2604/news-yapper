"use client";

import { ArrowRight, Timer } from "lucide-react";
import { useEffect, useState } from "react";
import { CandyButton, CandyLink } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";
import { ProgressBurst } from "@/components/design-system/ProgressBurst";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { Mascot, StarSticker } from "@/components/design-system/stickers";
import { QuizRunner } from "@/components/quiz/QuizRunner";
import type { DailyQuiz as DailyQuizData, FinishResult, QuizSession } from "@/lib/api-types";
import { categoryMeta } from "@/lib/categories";
import { api } from "@/lib/client-api";
import { cn } from "@/lib/cn";

export function DailyQuiz({ initial }: { initial: DailyQuizData }) {
  const [session, setSession] = useState<QuizSession | null>(initial.session);
  const [result, setResult] = useState<FinishResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    if (initial.session?.completed_at) {
      api<FinishResult>(`quizzes/sessions/${initial.session.id}/finish`, { method: "POST" }).then(setResult, () => undefined);
    }
  }, [initial.session]);

  async function start() {
    setStarting(true);
    setError(null);
    try {
      setSession(await api<QuizSession>("quizzes/sessions", { method: "POST", body: { type: "daily" } }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Quiz start hoyni.");
    } finally {
      setStarting(false);
    }
  }

  async function finish(s: QuizSession) {
    try {
      setResult(await api<FinishResult>(`quizzes/sessions/${s.id}/finish`, { method: "POST" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't finish the session.");
    }
  }

  if (result) return <Summary result={result} />;
  if (session && !session.completed_at) return <QuizRunner session={session} onComplete={() => void finish(session)} />;
  if (session?.completed_at) return <p className="text-center font-semibold">Loading your results...</p>;

  if (initial.pool_size === 0) {
    return (
      <EmptyState title="Question bank khali" mood="think">
        No validated questions yet. Seed the demo bank with <code>npm run db:seed</code>.
      </EmptyState>
    );
  }

  return (
    <section className="relative overflow-hidden rounded-[24px] border-2 border-ink bg-mango shadow-brutal-lg">
      <div aria-hidden="true" className="absolute -top-20 -left-16 size-60 rounded-full border-2 border-ink bg-punch" />
      <div aria-hidden="true" className="absolute -right-10 -bottom-16 size-56 rounded-full border-2 border-ink bg-lavender" />
      <div className="relative grid gap-6 p-6 sm:p-10 md:grid-cols-[1fr_auto] md:items-center">
        <div className="space-y-5">
          <StickerBadge tone="paper" tilt={-3}>
            Daily quiz · {initial.date}
          </StickerBadge>
          <h2 className="font-display text-4xl leading-[1.05] font-bold sm:text-6xl">
            Aajke-r {initial.target_count} MCQ.
            <br />
            <span className="marker">Ready, bondhu?</span>
          </h2>
          <ul className="flex flex-wrap gap-2 text-sm font-semibold">
            <li className="rounded-full border-2 border-ink bg-paper px-3 py-1">
              {initial.current_affairs_available} current affairs in pool
            </li>
            <li className="rounded-full border-2 border-ink bg-paper px-3 py-1">{initial.static_gk_available} static GK</li>
            <li className="flex items-center gap-1 rounded-full border-2 border-ink bg-paper px-3 py-1">
              <Timer className="size-4" aria-hidden="true" /> ~{Math.round(initial.target_count * 0.6)} min
            </li>
          </ul>
          <p className="max-w-lg text-ink/80">
            Picked for you from weak topics, recent mistakes and fresh current affairs. Questions are retrieved from
            stories already saved in the database, so opening this page reads that saved set. Bhul hole Mistake Vault-e
            chole jabe, porer bar thik hobe.
          </p>
          <CandyButton tone="ink" size="lg" onClick={start} disabled={starting}>
            {starting ? "Setting up..." : "Start quiz"} <ArrowRight className="size-5" aria-hidden="true" />
          </CandyButton>
          {error ? (
            <p role="alert" className="font-semibold text-pink-deep">
              {error}
            </p>
          ) : null}
        </div>
        <div className="relative hidden md:block" aria-hidden="true">
          <Mascot mood="wow" className="size-56 rotate-3" />
          <StarSticker className="absolute -top-4 -left-6 size-14 -rotate-12" />
        </div>
      </div>
    </section>
  );
}

function Summary({ result }: { result: FinishResult }) {
  const { session } = result;
  const ratio = session.question_count ? session.score / session.question_count : 0;
  const message =
    ratio >= 0.8 ? "Topper vibes! 🏆" : ratio >= 0.5 ? "Bhalo cholchhe - aro ektu!" : "Practice makes perfect. Kal abar!";
  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[24px] border-2 border-ink bg-ink p-8 text-center text-cream shadow-brutal-lg">
        <ProgressBurst fire pieces={30} />
        <Mascot mood={ratio >= 0.5 ? "happy" : "think"} className="mx-auto size-28" />
        <p className="mt-2 font-display text-sm font-bold tracking-[0.2em] text-mango uppercase">Daily quiz done</p>
        <p className="font-display text-7xl font-bold">
          {session.score}
          <span className="text-4xl text-cream/70">/{session.question_count}</span>
        </p>
        <p className="mt-1 font-display text-2xl font-bold">{message}</p>
        <p className="mt-3 inline-block rounded-full border-2 border-mango px-4 py-1 font-bold text-mango">
          +{result.xp_earned} XP
        </p>
      </section>

      <section className="rounded-[20px] border-2 border-ink bg-paper p-6 shadow-brutal">
        <h2 className="font-display text-2xl font-bold">Topic-wise</h2>
        <ul className="mt-4 space-y-3">
          {result.topic_breakdown.map((t) => {
            const meta = categoryMeta(t.topic);
            return (
              <li key={t.topic} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3">
                <span className="flex items-center gap-2 font-semibold">
                  <meta.Sticker className="size-6" /> {meta.short}
                </span>
                <span className="h-4 overflow-hidden rounded-full border-2 border-ink bg-cream" aria-hidden="true">
                  <span
                    className={cn("block h-full", t.accuracy >= 0.6 ? "bg-mint" : "bg-pink")}
                    style={{ width: `${Math.max(4, t.accuracy * 100)}%` }}
                  />
                </span>
                <span className="font-display font-bold">
                  {t.correct}/{t.attempts}
                </span>
              </li>
            );
          })}
        </ul>
        {result.weak_topics.length ? (
          <p className="mt-5 rounded-xl border-2 border-dashed border-ink bg-pink/50 p-3 font-semibold">
            Weak spots (30 days): {result.weak_topics.map((t) => categoryMeta(t).short).join(", ")} - tomorrow&apos;s quiz
            will lean into these.
          </p>
        ) : null}
      </section>

      <div className="flex flex-wrap justify-center gap-3">
        <CandyLink href="/revision" tone="punch" size="lg">
          Review mistakes
        </CandyLink>
        <CandyLink href="/" tone="paper" size="lg">
          Back to today&apos;s edition
        </CandyLink>
      </div>
    </div>
  );
}
