"use client";

import { ArrowRight, ExternalLink } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CandyButton } from "@/components/design-system/CandyButton";
import { ProgressBurst } from "@/components/design-system/ProgressBurst";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { Mascot } from "@/components/design-system/stickers";
import { type OptionState, QuizOption } from "@/components/quiz/QuizOption";
import type { AnsweredState, AnswerResult, QuizSession } from "@/lib/api-types";
import { categoryMeta } from "@/lib/categories";
import { api } from "@/lib/client-api";
import { cn } from "@/lib/cn";

const LETTERS = ["A", "B", "C", "D"];

export function QuizRunner({ session, onComplete }: { session: QuizSession; onComplete: () => void }) {
  const [answers, setAnswers] = useState<Record<string, AnsweredState>>(() =>
    Object.fromEntries(session.answers.map((a) => [a.question_id, a])),
  );
  const firstOpen = session.questions.findIndex((q) => !answers[q.id]);
  const [index, setIndex] = useState(firstOpen === -1 ? session.questions.length - 1 : firstOpen);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [burst, setBurst] = useState(0);
  const [lastMistake, setLastMistake] = useState(false);
  const shownAt = useRef<number>(0);
  const cardRef = useRef<HTMLElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);

  const question = session.questions[index];
  const answer = question ? answers[question.id] : undefined;
  const answeredCount = Object.keys(answers).length;
  const allDone = answeredCount >= session.questions.length;

  useEffect(() => {
    shownAt.current = performance.now();
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    cardRef.current?.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
    headingRef.current?.focus({ preventScroll: true });
  }, [index]);

  const choose = useCallback(
    async (selected: number) => {
      if (!question || answer || busy) return;
      setBusy(true);
      setError(null);
      try {
        const res = await api<AnswerResult>(`quizzes/sessions/${session.id}/answers`, {
          method: "POST",
          body: {
            question_id: question.id,
            selected_index: selected,
            response_ms: Math.round(performance.now() - shownAt.current),
          },
        });
        setAnswers((prev) => ({ ...prev, [question.id]: res }));
        setLastMistake(!res.is_correct && Boolean(res.mistake));
        if (res.is_correct) setBurst((b) => b + 1);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Answer save hoyni - abar try kor.");
      } finally {
        setBusy(false);
      }
    },
    [question, answer, busy, session.id],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      const map: Record<string, number> = { "1": 0, "2": 1, "3": 2, "4": 3, a: 0, b: 1, c: 2, d: 3 };
      const choice = map[e.key.toLowerCase()];
      if (choice !== undefined && !answer) void choose(choice);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [answer, choose]);

  const states: OptionState[] = useMemo(() => {
    if (!question) return [];
    return question.options.map((_, i) => {
      if (!answer) return "idle";
      if (i === answer.correct_index) return "correct";
      if (i === answer.selected_index) return "wrong";
      return "dimmed";
    });
  }, [question, answer]);

  if (!question) return null;
  const meta = categoryMeta(question.exam_topic);

  return (
    <div className="space-y-5">
      <ol className="flex gap-1.5" aria-label={`Question ${index + 1} of ${session.questions.length}`}>
        {session.questions.map((q, i) => {
          const a = answers[q.id];
          return (
            <li
              key={q.id}
              className={cn(
                "h-3 flex-1 rounded-full border-2 border-ink",
                a ? (a.is_correct ? "bg-mint" : "bg-pink") : i === index ? "bg-mango" : "bg-paper",
              )}
            >
              <span className="sr-only">
                Question {i + 1}: {a ? (a.is_correct ? "correct" : "wrong") : i === index ? "current" : "not answered"}
              </span>
            </li>
          );
        })}
      </ol>

      <section ref={cardRef} className="relative scroll-mt-24 rounded-[22px] border-2 border-ink bg-paper p-5 shadow-brutal-lg sm:p-8" aria-live="off">
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <StickerBadge tone={meta.tone === "paper" ? "mango" : meta.tone} icon={<meta.Sticker />}>
            {meta.short}
          </StickerBadge>
          <StickerBadge tone="paper" tilt={1}>
            {question.kind === "static_gk" ? "Static GK" : "Current affairs"}
          </StickerBadge>
          {question.is_demo ? (
            <StickerBadge tone="ink" tilt={-1}>
              Demo
            </StickerBadge>
          ) : null}
          {question.reason === "Mistake Vault revision" ? (
            <StickerBadge tone="pink" tilt={2}>
              Revisiting a mistake
            </StickerBadge>
          ) : null}
          <span className="ml-auto font-display font-bold text-ink-soft">
            {index + 1}/{session.questions.length}
          </span>
        </div>
        <h2 ref={headingRef} tabIndex={-1} className="font-display text-2xl leading-snug font-bold focus:outline-none sm:text-3xl">
          {question.prompt}
        </h2>
        <div className="relative mt-6 grid gap-3" role="group" aria-label="Answer options">
          <ProgressBurst key={burst} fire={burst > 0 && Boolean(answer?.is_correct)} />
          {question.options.map((opt, i) => (
            <QuizOption
              key={i}
              letter={LETTERS[i]}
              text={opt}
              state={states[i]}
              disabled={Boolean(answer) || busy}
              onSelect={() => void choose(i)}
            />
          ))}
        </div>
        {!answer ? <p className="mt-4 text-sm text-ink-soft">Tip: press 1-4 or A-D to answer.</p> : null}
        {error ? (
          <p role="alert" className="mt-4 rounded-xl border-2 border-ink bg-pink px-3 py-2 font-semibold">
            {error}
          </p>
        ) : null}
      </section>

      <div role="status" aria-live="polite">
        {answer ? (
          <section
            className={cn(
              "flex animate-rise flex-col gap-4 rounded-[22px] border-2 border-ink p-5 shadow-brutal sm:flex-row sm:items-start sm:p-6",
              answer.is_correct ? "bg-mint" : "bg-pink",
            )}
          >
            <Mascot mood={answer.is_correct ? "happy" : "oops"} className="size-20 shrink-0" steam={answer.is_correct} />
            <div className="flex-1 space-y-2">
              <p className="font-display text-2xl font-bold">
                {answer.is_correct
                  ? "Correct! Shabash 🎉"
                  : lastMistake
                    ? "Oops, eta bhul hoyeche. Mistake Vault-e rekhe dilam 😭"
                    : "Not quite."}
              </p>
              <p className="leading-relaxed">
                <strong>Answer: {question.options[answer.correct_index]}.</strong> {answer.explanation}
              </p>
              {answer.evidence_urls.length ? (
                <ul className="flex flex-wrap gap-2">
                  {answer.evidence_urls.map((url) => (
                    <li key={url}>
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className="inline-flex min-h-11 items-center gap-1 rounded-xl border-2 border-ink bg-paper px-3 text-sm font-semibold hover:bg-mango"
                      >
                        Evidence <ExternalLink className="size-4" aria-hidden="true" />
                        <span className="sr-only">(opens {new URL(url).hostname} in a new tab)</span>
                      </a>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
            <div className="sm:self-end">
              {allDone ? (
                <CandyButton tone="ink" size="lg" onClick={onComplete}>
                  See results <ArrowRight className="size-5" aria-hidden="true" />
                </CandyButton>
              ) : (
                <CandyButton
                  tone="ink"
                  size="lg"
                  onClick={() => {
                    const next = session.questions.findIndex((q, i) => i > index && !answers[q.id]);
                    setIndex(next === -1 ? session.questions.findIndex((q) => !answers[q.id]) : next);
                  }}
                >
                  Next question <ArrowRight className="size-5" aria-hidden="true" />
                </CandyButton>
              )}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
