"use client";

import Link from "next/link";
import { useState } from "react";
import { CandyButton, candyClasses } from "@/components/design-system/CandyButton";
import { QuizRunner } from "@/components/quiz/QuizRunner";
import type { QuizSession } from "@/lib/api-types";
import { api } from "@/lib/client-api";

export function PracticeQuiz({ slug, count, signedIn }: { slug: string; count: number; signedIn: boolean }) {
  const [session, setSession] = useState<QuizSession | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!count) return null;
  if (!signedIn) {
    return (
      <Link href={`/signin?callbackUrl=/news/${slug}`} className={candyClasses("punch", "md")}>
        Login to practise {count} question{count > 1 ? "s" : ""}
      </Link>
    );
  }
  if (done && session) {
    return (
      <p className="rounded-2xl border-2 border-ink bg-mint p-4 font-semibold">
        Practice done! Wrong answers (if any) are waiting in your Mistake Vault.
      </p>
    );
  }
  if (session) return <QuizRunner session={session} onComplete={() => setDone(true)} />;
  return (
    <div className="space-y-2">
      <CandyButton
        tone="punch"
        onClick={async () => {
          setError(null);
          try {
            setSession(await api<QuizSession>("quizzes/sessions", { method: "POST", body: { type: "practice", article_slug: slug } }));
          } catch (err) {
            setError(err instanceof Error ? err.message : "Couldn't start practice.");
          }
        }}
      >
        Practise {count} question{count > 1 ? "s" : ""} from this story
      </CandyButton>
      {error ? (
        <p role="alert" className="text-sm font-semibold text-pink-deep">
          {error}
        </p>
      ) : null}
    </div>
  );
}
