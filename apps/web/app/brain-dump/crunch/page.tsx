import Link from "next/link";
import { CrunchFlow } from "@/components/crunch/CrunchFlow";
import { EmptyState } from "@/components/design-system/EmptyState";
import { SectionTitle } from "@/components/design-system/SectionTitle";
import { CardsSticker } from "@/components/design-system/stickers";
import type { CrunchBrief, CrunchOutput, Me, Mistake, Note, Snapshot } from "@/lib/api-types";
import { formatDate } from "@/lib/format";
import { backendOrNull } from "@/lib/server/api";
import { requireUser } from "@/lib/server/session";

export const metadata = { title: "Crunch It" };

const ids = (value?: string) => (value ? value.split(",").filter((v) => /^[0-9a-f-]{36}$/i.test(v)) : []);

export default async function CrunchPage({
  searchParams,
}: {
  searchParams: Promise<{ notes?: string; snapshots?: string; mistakes?: string; output?: string }>;
}) {
  const params = await searchParams;
  const user = await requireUser("/brain-dump/crunch");
  const outputId = ids(params.output)[0];
  const [notes, snapshots, mistakes, me, history, output] = await Promise.all([
    backendOrNull<Note[]>("/notes", { userId: user.id }),
    backendOrNull<Snapshot[]>("/snapshots", { userId: user.id }),
    backendOrNull<Mistake[]>("/mistakes", { userId: user.id }),
    backendOrNull<Me>("/me", { userId: user.id }),
    backendOrNull<CrunchBrief[]>("/crunch/outputs", { userId: user.id }),
    outputId ? backendOrNull<CrunchOutput>(`/crunch/outputs/${outputId}`, { userId: user.id }) : Promise.resolve(null),
  ]);

  if (!notes || !snapshots || !mistakes || !me) {
    return (
      <EmptyState title="Crunch load hocchhe na" mood="oops">
        The API isn&apos;t reachable right now.
      </EmptyState>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-end gap-4">
        <CardsSticker className="hidden size-16 -rotate-6 sm:block" />
        <SectionTitle
          as="h1"
          kicker="Notes + mistakes + saved stories → revision cards"
          title={
            <>
              Crunch It <span className="marker">✨</span>
            </>
          }
        />
      </div>
      <CrunchFlow
        key={outputId ?? "new"}
        notes={notes}
        snapshots={snapshots}
        mistakes={mistakes}
        consent={me.preferences.crunch_ai_consent}
        initialOutput={output}
        preselected={{ notes: ids(params.notes), snapshots: ids(params.snapshots), mistakes: ids(params.mistakes) }}
      />
      {history && history.length ? (
        <section aria-labelledby="history" className="space-y-3">
          <h2 id="history" className="font-display text-2xl font-bold">
            Previous crunches
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {history.map((h) => (
              <li key={h.id}>
                <Link
                  href={`/brain-dump/crunch?output=${h.id}`}
                  className="block rounded-2xl border-2 border-ink bg-paper p-4 shadow-brutal-sm brutal-lift"
                >
                  <p className="font-display font-bold">{h.title}</p>
                  <p className="text-sm text-ink-soft">
                    {formatDate(h.created_at)} · {h.bullet_count} points · {h.flashcard_count} cards ·{" "}
                    {h.engine === "ai" ? "AI" : "offline"}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
