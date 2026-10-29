import { ChevronLeft, ExternalLink, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@/auth";
import { BrutalCard } from "@/components/design-system/BrutalCard";
import { ExamTags } from "@/components/design-system/ExamTag";
import { AiStatusBadge, DemoBadge, StickerBadge } from "@/components/design-system/StickerBadge";
import { StickyNote } from "@/components/design-system/StickyNote";
import { BulbSticker, Stamp } from "@/components/design-system/stickers";
import { ArticleActions } from "@/components/news/ArticleActions";
import { ArticleChat } from "@/components/news/ArticleChat";
import { PracticeQuiz } from "@/components/news/PracticeQuiz";
import type { ArticleDetail, ChatThread } from "@/lib/api-types";
import { categoryMeta } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { formatDate, formatDateTime, glueSuffixes } from "@/lib/format";
import { BackendError, backend, backendOrNull } from "@/lib/server/api";

async function load(slug: string, userId: string | null): Promise<ArticleDetail> {
  try {
    return await backend<ArticleDetail>(`/news/${encodeURIComponent(slug)}`, { userId });
  } catch (err) {
    if (err instanceof BackendError && err.status === 404) notFound();
    throw err;
  }
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  try {
    const article = await backend<ArticleDetail>(`/news/${encodeURIComponent(slug)}`, { userId: null });
    return { title: article.headline, description: article.tldr.slice(0, 160) };
  } catch {
    return { title: "Story" };
  }
}

const METHOD_LABEL: Record<string, string> = {
  automated_evidence_check: "Automated evidence check passed",
  editor_review: "Reviewed by an editor",
  demo_manual: "Hand-written DEMO explainer",
};

export default async function ArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const session = await auth();
  const userId = session?.user?.id ?? null;
  const [article, thread] = await Promise.all([
    load(slug, userId),
    userId ? backendOrNull<ChatThread>(`/news/${encodeURIComponent(slug)}/chat`, { userId }) : Promise.resolve(null),
  ]);
  const meta = categoryMeta(article.category);
  const ready = article.ai_status === "ready";
  const serious = article.sensitive;
  const sourceIndex = new Map(article.sources.map((s, i) => [s.id, i + 1]));

  return (
    <article className="mx-auto max-w-6xl">
      <Link
        href={`/news?category=${article.category}`}
        className="mb-4 inline-flex min-h-11 items-center gap-1 rounded-xl pr-2 font-display font-bold text-ink-soft hover:text-ink"
      >
        <ChevronLeft className="size-5" aria-hidden="true" /> {meta.label}
      </Link>

      <header className={cn("relative mb-8 rounded-[22px] border-2 border-ink p-6 shadow-brutal sm:p-9", serious ? "bg-paper" : "bg-cream-deep paper-grain")}>
        <div className="flex flex-wrap items-center gap-2">
          {serious ? (
            <StickerBadge tone="paper" tilt={0}>
              Serious story · no jokes here
            </StickerBadge>
          ) : (
            <StickerBadge tone={meta.tone === "paper" ? "mango" : meta.tone} icon={<meta.Sticker />}>
              {meta.short}
            </StickerBadge>
          )}
          {article.is_demo ? <DemoBadge /> : null}
          <AiStatusBadge status={article.ai_status} />
          {article.correction_status !== "none" ? (
            <StickerBadge tone="pink" tilt={0}>
              {article.correction_status === "corrected" ? "Source updated" : article.correction_status}
            </StickerBadge>
          ) : null}
        </div>
        <h1 className="mt-4 max-w-4xl font-display text-[2.1rem] leading-[1.08] font-bold tracking-tight sm:text-5xl">
          {glueSuffixes(article.headline)}
        </h1>
        <p className="mt-4 text-sm font-medium text-ink-soft">
          {formatDate(article.date)} · {article.source_count} source{article.source_count === 1 ? "" : "s"} · Last updated{" "}
          {formatDateTime(article.last_updated_at)}
        </p>
        <div className="mt-3">
          <ExamTags exams={article.exam_tags} max={6} />
        </div>
        {ready && !serious ? (
          <Stamp
            label={article.is_demo ? "DEMO" : "CHECKED"}
            className="absolute top-6 right-6 hidden size-24 -rotate-12 opacity-90 md:block"
          />
        ) : null}
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-8">
          {article.correction_note ? (
            <p className="rounded-2xl border-2 border-ink bg-pink p-4 font-semibold">{article.correction_note}</p>
          ) : null}

          {!ready ? (
            <BrutalCard tone="paper" className="p-6">
              <h2 className="font-display text-2xl font-bold">AI summary pending</h2>
              <p className="mt-2 reading text-ink-soft">
                {article.ai_status === "in_review"
                  ? "A draft exists but is waiting for an editor or failed an automated evidence check, so we only show the original source below."
                  : "This story was discovered from the sources below. A Banglish summary appears only after it passes our source checks."}
              </p>
              {article.tldr ? <p className="mt-4 reading border-l-4 border-ink pl-4 italic">{article.tldr}</p> : null}
            </BrutalCard>
          ) : (
            <>
              {article.banglish_summary ? (
                <section aria-labelledby="tldr" className={cn("rounded-[20px] border-2 border-ink p-6 shadow-brutal", serious ? "bg-paper" : "bg-mango")}>
                  <h2 id="tldr" className="font-display text-sm font-bold tracking-[0.18em] uppercase">
                    {serious ? "Summary" : "Banglish TL;DR ☕"}
                  </h2>
                  <p className="mt-2 text-lg leading-relaxed sm:text-xl">{article.banglish_summary}</p>
                </section>
              ) : null}

              <section aria-labelledby="what-happened">
                <h2 id="what-happened" className="flex items-center gap-2 font-display text-2xl font-bold">
                  What happened <ShieldCheck className="size-6 text-mint-deep" aria-hidden="true" />
                </h2>
                <p className="mt-1 text-sm font-semibold text-mint-deep">
                  {METHOD_LABEL[article.verification?.method ?? ""] ?? "Source-checked"} - facts kept separate from the fun lead-in.
                </p>
                <p className="mt-3 reading">{article.neutral_summary}</p>
              </section>

              {article.why_matters ? (
                <section aria-labelledby="why" className="rounded-[20px] border-2 border-ink bg-mint p-6">
                  <h2 id="why" className="flex items-center gap-2 font-display text-2xl font-bold">
                    <BulbSticker className="size-8" /> Why it matters for exams
                  </h2>
                  <p className="mt-2 reading">{article.why_matters}</p>
                </section>
              ) : null}

              {article.key_facts.length ? (
                <section aria-labelledby="facts">
                  <h2 id="facts" className="font-display text-2xl font-bold">
                    Exam facts
                  </h2>
                  <ol className="mt-3 space-y-3">
                    {article.key_facts.map((fact, i) => (
                      <li key={i} className="flex gap-3 rounded-2xl border-2 border-ink bg-paper p-4">
                        <span className="grid size-8 shrink-0 place-items-center rounded-full border-2 border-ink bg-lavender font-display font-bold">
                          {i + 1}
                        </span>
                        <p className="flex-1 leading-relaxed">
                          {fact.claim}{" "}
                          {fact.source_item_ids.map((sid) =>
                            sourceIndex.has(sid) ? (
                              <a
                                key={sid}
                                href={`#source-${sourceIndex.get(sid)}`}
                                className="ml-0.5 align-super text-xs font-bold text-punch-deep hover:underline"
                                aria-label={`Source ${sourceIndex.get(sid)}`}
                              >
                                [{sourceIndex.get(sid)}]
                              </a>
                            ) : null,
                          )}
                        </p>
                      </li>
                    ))}
                  </ol>
                </section>
              ) : null}

              {article.context ? (
                <section aria-labelledby="context">
                  <h2 id="context" className="font-display text-2xl font-bold">
                    Context
                  </h2>
                  <p className="mt-2 reading">{article.context}</p>
                </section>
              ) : null}

              {article.mnemonics.length && !serious ? (
                <section aria-label="Memory hook" className="max-w-md pt-2">
                  <StickyNote
                    id={`mn-${article.slug}`}
                    title="Mone rakhar trick 🧠"
                    body={article.mnemonics.map((m) => `- ${m}`).join("\n")}
                    color="pink"
                  />
                  <p className="mt-2 text-xs text-ink-soft">Memory hooks are study aids, not source facts.</p>
                </section>
              ) : null}

              {article.uncertainties.length ? (
                <section className="rounded-2xl border-2 border-dashed border-ink p-4">
                  <h2 className="font-display text-lg font-bold">Not confirmed by the sources</h2>
                  <ul className="mt-1 list-disc pl-5 text-ink-soft">
                    {article.uncertainties.map((u) => (
                      <li key={u}>{u}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {article.practice_question_count ? (
                <section aria-labelledby="practice" className="space-y-3">
                  <h2 id="practice" className="font-display text-2xl font-bold">
                    Quick practice
                  </h2>
                  <p className="text-sm font-medium text-ink-soft">
                    These questions were saved with the story. Practising reads them back from the database.
                  </p>
                  <PracticeQuiz slug={article.slug} count={article.practice_question_count} signedIn={Boolean(session?.user)} />
                </section>
              ) : null}

              <ArticleChat slug={article.slug} signedIn={Boolean(session?.user)} initial={thread} />
            </>
          )}
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <BrutalCard tone="paper" className="space-y-3 p-5">
            <h2 className="font-display text-lg font-bold">Save for revision</h2>
            <ArticleActions
              slug={article.slug}
              title={article.headline}
              snapshotId={article.snapshot_id}
              signedIn={Boolean(session?.user)}
            />
          </BrutalCard>

          <BrutalCard tone="cream" className="p-5">
            <h2 className="font-display text-lg font-bold">Sources</h2>
            <ol className="mt-3 space-y-3">
              {article.sources.map((s, i) => (
                <li key={s.id} id={`source-${i + 1}`} className="scroll-mt-28 rounded-xl border-2 border-ink bg-paper p-3">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase">
                    <span className="grid size-6 place-items-center rounded-full border-2 border-ink bg-mango">{i + 1}</span>
                    {s.tier === "A" ? "Official source" : "Discovery source"}
                    {s.is_demo ? " · demo reference" : ""}
                  </div>
                  <a
                    href={s.url}
                    target="_blank"
                    rel="noopener noreferrer nofollow"
                    className="mt-1.5 inline-flex items-start gap-1 font-semibold break-words hover:underline"
                  >
                    {s.name} <ExternalLink className="mt-1 size-3.5 shrink-0" aria-hidden="true" />
                    <span className="sr-only">(opens in a new tab)</span>
                  </a>
                  <p className="text-xs text-ink-soft">
                    {s.published_at ? `Published ${formatDateTime(s.published_at)}` : "Publication time not provided by source"}
                  </p>
                </li>
              ))}
            </ol>
          </BrutalCard>

          <BrutalCard tone="paper" flat className="space-y-2 p-5 text-sm">
            <h2 className="font-display text-base font-bold">How this was made</h2>
            {article.verification ? (
              <p>
                {METHOD_LABEL[article.verification.method ?? ""] ?? "Checked"}
                {article.verification.ai_provider
                  ? ` · drafted by ${article.verification.ai_provider} (${article.verification.ai_model}), prompt ${article.verification.prompt_version}`
                  : ""}
              </p>
            ) : (
              <p>Source headline only - no AI text shown yet.</p>
            )}
            <p className="text-ink-soft">
              Relevance {article.relevance_score}/100 - a heuristic for revision priority, not an exam prediction.
            </p>
          </BrutalCard>
        </aside>
      </div>
    </article>
  );
}
