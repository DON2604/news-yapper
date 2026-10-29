import Link from "next/link";
import { CandyLink } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";
import { ProgressRing } from "@/components/design-system/ProgressBurst";
import { SectionTitle } from "@/components/design-system/SectionTitle";
import { FlameSticker, Mascot, TrophySticker } from "@/components/design-system/stickers";
import type { Progress } from "@/lib/api-types";
import { categoryMeta } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { formatDate, percent } from "@/lib/format";
import { backendOrNull } from "@/lib/server/api";
import { requireUser } from "@/lib/server/session";

export const metadata = { title: "Progress" };

const HEAT = ["bg-paper", "bg-mint", "bg-mango", "bg-punch"];

export default async function ProgressPage() {
  const user = await requireUser("/progress");
  const p = await backendOrNull<Progress>("/progress", { userId: user.id });
  if (!p) {
    return (
      <EmptyState title="Progress load hocchhe na" mood="oops">
        The API isn&apos;t reachable right now.
      </EmptyState>
    );
  }
  const levelSpan = Math.max(1, p.next_level_xp - p.level_floor_xp);
  const levelRatio = Math.min(1, (p.xp_total - p.level_floor_xp) / levelSpan);
  const maxActivity = Math.max(1, ...p.activity.map((a) => a.count));

  return (
    <div className="space-y-10">
      <div className="flex items-end gap-4">
        <TrophySticker className="hidden size-16 -rotate-6 sm:block" />
        <SectionTitle as="h1" kicker="Effort counts, not just scores" title="Your progress" />
      </div>

      <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-12">
        <section className="relative overflow-hidden rounded-[24px] border-2 border-ink bg-ink p-6 text-cream shadow-brutal lg:col-span-5">
          <p className="font-display text-xs font-bold tracking-[0.2em] text-mango uppercase">Level</p>
          <p className="font-display text-7xl font-bold">{p.level}</p>
          <p className="font-semibold">{p.xp_total} XP total</p>
          <div className="mt-4 h-5 overflow-hidden rounded-full border-2 border-cream bg-ink-soft" role="progressbar" aria-valuemin={p.level_floor_xp} aria-valuemax={p.next_level_xp} aria-valuenow={p.xp_total} aria-label="Progress to next level">
            <div className="h-full bg-mango" style={{ width: `${Math.max(3, levelRatio * 100)}%` }} />
          </div>
          <p className="mt-2 text-sm text-cream/80">{p.next_level_xp - p.xp_total} XP to level {p.level + 1}</p>
          <Mascot mood="happy" className="absolute -right-4 -bottom-4 size-28 rotate-6" steam={false} />
        </section>

        <section className="rounded-[24px] border-2 border-ink bg-mango p-6 shadow-brutal lg:col-span-4">
          <div className="flex items-center gap-3">
            <FlameSticker className="size-14" />
            <div>
              <p className="font-display text-4xl font-bold">{p.streak_current} day{p.streak_current === 1 ? "" : "s"}</p>
              <p className="font-semibold">Current streak · best {p.streak_best}</p>
            </div>
          </div>
          <p className="mt-4 text-ink/80">
            {p.studied_today
              ? "Aajke-r study done - shabash!"
              : p.streak_current
                ? "Ekta question korlei streak bachbe. No pressure though."
                : "Fresh start any day. Even 5 minutes counts."}
          </p>
        </section>

        <section className="flex items-center gap-5 rounded-[24px] border-2 border-ink bg-lavender p-6 shadow-brutal lg:col-span-3">
          <ProgressRing value={Math.min(p.today_answered, p.daily_goal)} max={p.daily_goal} label={`${p.today_answered} of ${p.daily_goal} questions today`} />
          <div>
            <p className="font-display text-xl font-bold">Today&apos;s goal</p>
            <p className="text-sm">Accuracy overall: {percent(p.accuracy_overall)}</p>
          </div>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-[22px] border-2 border-ink bg-paper p-6 shadow-brutal" aria-labelledby="acc-heading">
          <h2 id="acc-heading" className="font-display text-2xl font-bold">
            Accuracy by topic
          </h2>
          {p.accuracy_by_topic.length ? (
            <ul className="mt-4 space-y-3">
              {p.accuracy_by_topic.map((t) => {
                const meta = categoryMeta(t.topic);
                const weak = p.weak_topics.includes(t.topic);
                return (
                  <li key={t.topic} className="grid grid-cols-[7.5rem_1fr_4.5rem] items-center gap-3">
                    <span className="flex items-center gap-2 font-semibold">
                      <meta.Sticker className="size-6" /> {meta.short}
                    </span>
                    <span className="h-4 overflow-hidden rounded-full border-2 border-ink bg-cream" aria-hidden="true">
                      <span className={cn("block h-full", weak ? "bg-pink" : "bg-mint")} style={{ width: `${Math.max(4, t.accuracy * 100)}%` }} />
                    </span>
                    <span className="text-right font-display font-bold">
                      {percent(t.accuracy)} <span className="text-xs font-semibold text-ink-soft">({t.attempts})</span>
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="mt-3 text-ink-soft">
              No quiz attempts yet. <Link href="/quiz/daily" className="font-semibold text-punch-deep underline">Take today&apos;s quiz</Link>.
            </p>
          )}
          {p.weak_topics.length ? (
            <p className="mt-4 text-sm font-semibold">Weak spots get extra questions in tomorrow&apos;s quiz.</p>
          ) : null}
        </section>

        <section className="rounded-[22px] border-2 border-ink bg-cream-deep p-6 shadow-brutal dot-grid" aria-labelledby="act-heading">
          <h2 id="act-heading" className="font-display text-2xl font-bold">
            Last 14 days
          </h2>
          <ol className="mt-4 grid grid-cols-7 gap-2">
            {p.activity.map((a) => {
              const level = a.count === 0 ? 0 : Math.min(3, Math.ceil((a.count / maxActivity) * 3));
              return (
                <li key={a.date} className={cn("flex aspect-square flex-col items-center justify-center rounded-xl border-2 border-ink text-xs font-bold", HEAT[level])}>
                  <span>{formatDate(a.date, { day: "numeric", month: undefined, year: undefined })}</span>
                  <span className="text-[0.65rem] font-semibold">{a.count || "·"}</span>
                  <span className="sr-only">{`${formatDate(a.date)}: ${a.count} study actions`}</span>
                </li>
              );
            })}
          </ol>
          <p className="mt-3 text-xs text-ink-soft">Counts quiz answers, card reviews, new stickies and saved stories.</p>
        </section>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_2fr]">
        <section className="space-y-3 rounded-[22px] border-2 border-ink bg-mint p-6 shadow-brutal">
          <h2 className="font-display text-2xl font-bold">Due for review</h2>
          <p className="text-lg">
            <strong>{p.due_flashcards}</strong> flashcards · <strong>{p.active_mistakes}</strong> active mistakes ·{" "}
            <strong>{p.resolved_mistakes}</strong> fixed
          </p>
          <CandyLink href="/revision" tone="ink">
            Go revise
          </CandyLink>
          <dl className="grid grid-cols-2 gap-2 pt-2 text-sm">
            {Object.entries(p.totals).map(([k, v]) => (
              <div key={k} className="rounded-xl border-2 border-ink bg-paper px-3 py-2">
                <dt className="text-xs font-semibold text-ink-soft capitalize">{k.replaceAll("_", " ")}</dt>
                <dd className="font-display text-xl font-bold">{v}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="rounded-[22px] border-2 border-ink bg-paper p-6 shadow-brutal" aria-labelledby="missed-heading">
          <h2 id="missed-heading" className="font-display text-2xl font-bold">
            Missed question history
          </h2>
          {p.recent_missed.length ? (
            <ul className="mt-3 divide-y-2 divide-dashed divide-ink/20">
              {p.recent_missed.map((m) => (
                <li key={m.mistake_id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <span className="max-w-xl font-semibold">{m.prompt}</span>
                  <span className="flex items-center gap-2 text-sm">
                    <span className="rounded-md border border-ink bg-cream px-1.5">{categoryMeta(m.topic).short}</span>
                    <span>×{m.error_count}</span>
                    <span className={cn("rounded-md border border-ink px-1.5 font-bold", m.status === "resolved" ? "bg-mint" : "bg-pink")}>
                      {m.status}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-ink-soft">No mistakes yet. Either you&apos;re a genius or you haven&apos;t started 😄</p>
          )}
        </section>
      </div>
    </div>
  );
}
