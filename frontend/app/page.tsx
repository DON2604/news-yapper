import { ArrowRight, Info } from "lucide-react";
import Link from "next/link";
import { auth } from "@/auth";
import { BentoGrid } from "@/components/design-system/BentoGrid";
import { CandyLink } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";
import { HeadlineHero } from "@/components/design-system/HeadlineHero";
import { ProgressRing } from "@/components/design-system/ProgressBurst";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { StickyNote } from "@/components/design-system/StickyNote";
import { FlameSticker, Mascot, NotebookSticker, SparkleSticker } from "@/components/design-system/stickers";
import { TopicPill } from "@/components/design-system/TopicPill";
import { EditionProgress } from "@/components/news/EditionProgress";
import { NewsCard } from "@/components/news/NewsCard";
import type { DailyQuiz, Edition, NewsItem, Preferences, Progress, Snapshot } from "@/lib/api-types";
import { CATEGORY_ORDER } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { formatDate, glueSuffixes, greeting, todayLabel } from "@/lib/format";
import { backendOrNull } from "@/lib/server/api";

export default async function HomePage() {
  const session = await auth();
  const userId = session?.user?.id ?? null;
  const [edition, quiz, progress, snapshots, prefs] = await Promise.all([
    backendOrNull<Edition>("/editions/today", { userId }),
    userId ? backendOrNull<DailyQuiz>("/quizzes/daily", { userId }) : Promise.resolve(null),
    userId ? backendOrNull<Progress>("/progress", { userId }) : Promise.resolve(null),
    userId ? backendOrNull<Snapshot[]>("/snapshots", { userId }) : Promise.resolve(null),
    userId ? backendOrNull<Preferences>("/me/preferences", { userId }) : Promise.resolve(null),
  ]);

  if (!edition) {
    return (
      <EmptyState title="API ta ghumochhe 😴" mood="sleepy" className="mx-auto mt-10 max-w-xl">
        The news API isn&apos;t reachable. Start the full stack with <code>npm run dev</code> at the repository root.
      </EmptyState>
    );
  }
  if (edition.items.length === 0) {
    return (
      <EmptyState title="Aajke ekhono kono scene nei" mood="think" className="mx-auto mt-10 max-w-xl">
        No stories yet. Seed the demo edition with <code>npm run db:seed</code> or enable live ingestion.
      </EmptyState>
    );
  }

  const items = edition.items;
  const hero = items.find((i) => i.ai_status === "ready" && !i.sensitive) ?? items[0];
  const rest = items.filter((i) => i.event_id !== hero.event_id);
  const secondary = rest.slice(0, 3);
  const quick = rest.slice(3, 8);
  const more = rest.slice(8);

  return (
    <div className="space-y-10">
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-display text-sm font-bold tracking-[0.18em] text-punch-deep uppercase">{todayLabel()}</p>
          <h1 className="font-display text-4xl font-bold tracking-tight sm:text-5xl">
            {greeting(session?.user?.name)} <span className="marker">{glueSuffixes("Aajke-r cha ready")}</span> ☕
          </h1>
          <p className="mt-2 max-w-xl text-sm font-medium text-ink-soft">
            Banglish stories stay saved in the database. A refresh reads that saved copy.{" "}
            <Link href="/news" className="font-bold text-ink underline">
              Purono din-er scene
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StickerBadge tone="mint" tilt={-1.5}>
            {edition.generated_count} source-checked
          </StickerBadge>
        </div>
      </section>

      {edition.is_demo ? null : (
        <EditionProgress ready={edition.generated_count} total={edition.generated_count + edition.pending_count} />
      )}

      {prefs && !prefs.onboarded_at ? (
        <Link
          href="/onboarding"
          className="flex items-center justify-between gap-3 rounded-2xl border-2 border-ink bg-mint px-4 py-3 font-semibold shadow-brutal-sm brutal-lift"
        >
          <span>Ek minute-e exam profile set kor - quiz ar feed tor exam-er moto hobe.</span>
          <ArrowRight className="size-5 shrink-0" aria-hidden="true" />
        </Link>
      ) : null}

      {edition.is_demo || edition.is_fallback ? (
        <div
          role="note"
          className="flex items-start gap-3 rounded-2xl border-2 border-ink bg-ink px-4 py-3 text-cream shadow-brutal-sm"
        >
          <Info className="mt-0.5 size-5 shrink-0 text-mango" aria-hidden="true" />
          <p className="text-sm sm:text-base">
            {edition.is_demo ? (
              <>
                <strong className="text-mango">DEMO edition:</strong> hand-written evergreen explainers so you can try
                every feature - not today&apos;s news. Each one links to a checked reference page.
              </>
            ) : (
              <>
                Showing the latest edition from <strong>{formatDate(edition.edition_date)}</strong> - today&apos;s is
                still brewing.
              </>
            )}
          </p>
        </div>
      ) : null}

      <BentoGrid>
        <div className="sm:col-span-2 lg:col-span-7 lg:row-span-2">
          <HeadlineHero item={hero} />
        </div>
        <MissionTile className="sm:col-span-2 lg:col-span-5" signedIn={Boolean(userId)} quiz={quiz} progress={progress} />
        <FiveMinuteCha className="sm:col-span-2 lg:col-span-5" items={quick.length ? quick : secondary} />
        {secondary.map((item) => (
          <div key={item.event_id} className="lg:col-span-4">
            <NewsCard item={item} />
          </div>
        ))}
      </BentoGrid>

      <section aria-labelledby="topics-heading" className="space-y-3">
        <h2 id="topics-heading" className="font-display text-2xl font-bold">
          Kon topic-e dub dibi?
        </h2>
        <div className="no-scrollbar -mx-4 flex gap-2.5 overflow-x-auto px-4 pb-2 sm:mx-0 sm:flex-wrap sm:px-0">
          {CATEGORY_ORDER.map((c) => (
            <TopicPill key={c} category={c} href={`/news?category=${c}`} />
          ))}
        </div>
      </section>

      <BentoGrid>
        <BrainDumpTeaser className="sm:col-span-2 lg:col-span-5" signedIn={Boolean(userId)} snapshots={snapshots ?? []} />
        <section className="sm:col-span-2 lg:col-span-7" aria-labelledby="more-heading">
          <div className="mb-3 flex items-end justify-between">
            <h2 id="more-heading" className="font-display text-2xl font-bold">
              Aro scene 👀
            </h2>
            <Link href="/news" className="inline-flex min-h-11 items-center gap-1 font-display font-bold text-punch-deep hover:underline">
              Full feed <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2">
            {(more.length ? more : rest).slice(0, 8).map((item) => (
              <li key={item.event_id}>
                <NewsCard item={item} variant="row" />
              </li>
            ))}
          </ul>
        </section>
      </BentoGrid>
    </div>
  );
}

function MissionTile({
  signedIn,
  quiz,
  progress,
  className,
}: {
  signedIn: boolean;
  quiz: DailyQuiz | null;
  progress: Progress | null;
  className?: string;
}) {
  const session = quiz?.session;
  const done = Boolean(session?.completed_at);
  const answered = session ? session.answers.length : 0;
  const total = session?.question_count ?? quiz?.target_count ?? 10;
  return (
    <section
      aria-labelledby="mission-heading"
      className={cn("relative overflow-hidden rounded-card border-2 border-ink bg-ink p-6 text-cream shadow-brutal", className)}
    >
      <SparkleSticker className="absolute -top-2 right-3 size-16 rotate-12" />
      <p className="font-display text-xs font-bold tracking-[0.2em] text-mango uppercase">Today&apos;s mission</p>
      <h2 id="mission-heading" className="mt-1 font-display text-3xl font-bold">
        {done ? "Quiz done! Shabash 🎉" : signedIn ? `${total} MCQ, ${Math.max(5, Math.round(total * 0.8))} minute` : "Daily quiz khelbi?"}
      </h2>
      {signedIn ? (
        <div className="mt-4 flex items-center gap-5">
          <ProgressRing value={answered} max={total} label={`${answered} of ${total} questions answered today`} className="text-cream" />
          <div className="space-y-1.5">
            <p className="flex items-center gap-2 font-display text-lg font-bold">
              <FlameSticker className="size-7" />
              {progress && progress.streak_current > 0
                ? `${progress.streak_current}-day streak`
                : "Notun streak aaj shuru"}
            </p>
            <p className="text-sm text-cream/80">
              {progress ? `${progress.xp_total} XP · Level ${progress.level}` : "XP builds as you study."}
              {progress?.due_flashcards ? ` · ${progress.due_flashcards} cards due` : ""}
            </p>
          </div>
        </div>
      ) : (
        <p className="mt-3 max-w-sm text-cream/85">
          Login kore personal daily quiz, Mistake Vault ar Brain Dump unlock kor. Demo login-e kono password lage na.
        </p>
      )}
      <div className="mt-5 flex flex-wrap gap-2">
        {signedIn ? (
          <CandyLink href={done ? "/revision" : "/quiz/daily"} tone={done ? "mint" : "mango"} size="lg">
            {done ? "Review mistakes" : session ? "Continue quiz" : "Start daily quiz"}
            <ArrowRight className="size-5" aria-hidden="true" />
          </CandyLink>
        ) : (
          <CandyLink href="/signin" tone="mango" size="lg">
            Login &amp; start
          </CandyLink>
        )}
      </div>
    </section>
  );
}

function FiveMinuteCha({ items, className }: { items: NewsItem[]; className?: string }) {
  return (
    <section
      aria-labelledby="cha-heading"
      className={cn("relative rounded-card border-2 border-ink bg-lavender p-6 shadow-brutal", className)}
    >
      <div className="flex items-center justify-between gap-3">
        <h2 id="cha-heading" className="font-display text-2xl font-bold">
          5-minute cha ☕
        </h2>
        <StickerBadge tone="paper" tilt={3}>
          Quick reads
        </StickerBadge>
      </div>
      <ol className="mt-4 space-y-2.5">
        {items.slice(0, 5).map((item, i) => (
          <li key={item.event_id} className="flex gap-3">
            <span className="grid size-8 shrink-0 place-items-center rounded-full border-2 border-ink bg-paper font-display font-bold">
              {i + 1}
            </span>
            <Link href={`/news/${item.slug}`} className="line-clamp-2 min-h-8 font-semibold leading-snug hover:underline">
              {item.headline}
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

function BrainDumpTeaser({ signedIn, snapshots, className }: { signedIn: boolean; snapshots: Snapshot[]; className?: string }) {
  return (
    <section
      aria-labelledby="dump-heading"
      className={cn("relative overflow-hidden rounded-card border-2 border-ink bg-cream-deep p-6 shadow-brutal dot-grid", className)}
    >
      <div className="relative z-10 flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-xs font-bold tracking-[0.18em] text-lavender-deep uppercase">Your study desk</p>
          <h2 id="dump-heading" className="font-display text-3xl font-bold">
            Brain Dump
          </h2>
        </div>
        <NotebookSticker className="size-14 rotate-6" />
      </div>
      <div className="relative z-10 mt-4 grid grid-cols-2 gap-4">
        <StickyNote
          id="teaser-a"
          title={signedIn ? `${snapshots.length} saved` : "Save karo"}
          body={signedIn ? "Pinned article snapshots, ready for Crunch." : "Pin any story - facts + source stay with you."}
          color="mango"
          className="min-h-32 text-sm"
        />
        <StickyNote
          id="teaser-b"
          title="Crunch it ✨"
          body="Notes + mistakes → compact revision cards."
          color="mint"
          className="min-h-32 text-sm"
        />
      </div>
      <div className="relative z-10 mt-5 flex flex-wrap gap-2">
        <CandyLink href={signedIn ? "/brain-dump" : "/signin"} tone="lavender">
          Open Brain Dump
        </CandyLink>
        <CandyLink href={signedIn ? "/brain-dump/crunch" : "/signin"} tone="paper">
          Crunch it ✨
        </CandyLink>
      </div>
      <Mascot mood="think" className="absolute -right-4 -bottom-6 size-28 rotate-12 opacity-90" steam={false} />
    </section>
  );
}
