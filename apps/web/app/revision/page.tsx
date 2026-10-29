import Link from "next/link";
import { EmptyState } from "@/components/design-system/EmptyState";
import { SectionTitle } from "@/components/design-system/SectionTitle";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { CardsSticker } from "@/components/design-system/stickers";
import { WrongAnswerCard } from "@/components/quiz/WrongAnswerCard";
import { FlashcardDeck } from "@/components/revision/FlashcardDeck";
import type { Mistake, RevisionDue } from "@/lib/api-types";
import { formatDate, plural } from "@/lib/format";
import { backendOrNull } from "@/lib/server/api";
import { requireUser } from "@/lib/server/session";

export const metadata = { title: "Revision" };

export default async function RevisionPage() {
  const user = await requireUser("/revision");
  const [due, mistakes] = await Promise.all([
    backendOrNull<RevisionDue>("/revision/due", { userId: user.id }),
    backendOrNull<Mistake[]>("/mistakes", { userId: user.id }),
  ]);
  if (!due || !mistakes) {
    return (
      <EmptyState title="Revision load hocchhe na" mood="oops">
        The API isn&apos;t reachable right now.
      </EmptyState>
    );
  }
  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-end gap-4">
          <CardsSticker className="hidden size-16 -rotate-6 sm:block" />
          <SectionTitle as="h1" kicker="Spaced repetition, no AI calls" title="Revision" />
        </div>
        <div className="flex flex-wrap gap-2">
          <StickerBadge tone="mango" tilt={-2}>
            {due.due_flashcards} cards due
          </StickerBadge>
          <StickerBadge tone="paper" tilt={1}>
            {due.total_flashcards} cards total
          </StickerBadge>
          <StickerBadge tone="pink" tilt={-1}>
            {due.active_mistakes} active mistakes
          </StickerBadge>
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section aria-labelledby="deck-heading" className="space-y-4">
          <h2 id="deck-heading" className="font-display text-2xl font-bold">
            Flashcards due
          </h2>
          <FlashcardDeck cards={due.flashcards} />
        </section>
        <aside className="space-y-5">
          <section className="rounded-[20px] border-2 border-ink bg-lavender p-5 shadow-brutal">
            <h2 className="font-display text-xl font-bold">Coming up (7 days)</h2>
            {due.upcoming.length ? (
              <ul className="mt-3 space-y-2">
                {due.upcoming.map((d) => (
                  <li key={d.date} className="flex items-center justify-between rounded-xl border-2 border-ink bg-paper px-3 py-2 font-semibold">
                    <span>{formatDate(d.date, { weekday: "short", day: "numeric", month: "short", year: undefined })}</span>
                    <span>{plural(d.count, "card")}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-sm">Nothing scheduled yet.</p>
            )}
          </section>
          <section className="rounded-[20px] border-2 border-ink bg-paper p-5 shadow-brutal paper-grain">
            <h2 className="font-display text-xl font-bold">Weekly recap 🗞️</h2>
            <p className="mt-1 text-sm text-ink-soft">Built from your cached Crunch outputs - nothing regenerated.</p>
            {due.recaps.length ? (
              <ul className="mt-3 space-y-2">
                {due.recaps.map((r) => (
                  <li key={r.id}>
                    <Link href={`/brain-dump/crunch?output=${r.id}`} className="block rounded-xl border-2 border-ink bg-cream px-3 py-2 hover:bg-mango">
                      <span className="block font-semibold">{r.title}</span>
                      <span className="text-xs text-ink-soft">
                        {formatDate(r.created_at)} · {r.bullet_count} points · {r.flashcard_count} cards
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-sm">
                No crunches yet -{" "}
                <Link href="/brain-dump/crunch" className="font-semibold text-punch-deep underline">
                  make your first
                </Link>
                .
              </p>
            )}
          </section>
        </aside>
      </div>

      <section aria-labelledby="vault-heading" className="space-y-4">
        <h2 id="vault-heading" className="font-display text-2xl font-bold">
          Mistake Vault 😭
        </h2>
        {mistakes.length ? (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {mistakes.map((m) => (
              <WrongAnswerCard key={m.id} mistake={m} />
            ))}
          </div>
        ) : (
          <EmptyState title="Vault khali - darun!" mood="happy">
            Wrong answers from quizzes land here automatically with the explanation, so you can retry them later.
          </EmptyState>
        )}
      </section>
    </div>
  );
}
