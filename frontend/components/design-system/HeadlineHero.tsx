import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { ExamTags } from "@/components/design-system/ExamTag";
import { AiStatusBadge, DemoBadge, StickerBadge } from "@/components/design-system/StickerBadge";
import { ArrowDoodle, Mascot } from "@/components/design-system/stickers";
import { Tape } from "@/components/design-system/Tape";
import type { NewsItem } from "@/lib/api-types";
import { categoryMeta } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { formatDate, glueSuffixes } from "@/lib/format";

/** Dominant daily story. Sensitive stories get a calm, sticker-free treatment. */
export function HeadlineHero({ item, className }: { item: NewsItem; className?: string }) {
  const meta = categoryMeta(item.category);
  const serious = item.sensitive;
  return (
    <article
      className={cn(
        "group relative flex h-full flex-col overflow-hidden rounded-[22px] border-2 border-ink shadow-brutal-lg",
        serious ? "bg-paper" : "bg-mango",
        className,
      )}
    >
      {!serious ? (
        <>
          <div
            aria-hidden="true"
            className="absolute -top-16 -right-16 size-64 rounded-full border-2 border-ink bg-punch/90 sm:size-72"
          />
          <div aria-hidden="true" className="absolute right-24 -bottom-10 size-32 rounded-full border-2 border-ink bg-lavender" />
          <Tape tone="mint" className="top-5 -left-4 -rotate-12" />
        </>
      ) : null}
      <div className="relative flex flex-1 flex-col gap-5 p-6 sm:p-8 lg:p-10">
        <div className="flex flex-wrap items-center gap-2">
          <StickerBadge tone={serious ? "paper" : meta.tone === "mango" ? "paper" : meta.tone} icon={<meta.Sticker />}>
            {meta.short}
          </StickerBadge>
          <StickerBadge tone="ink" tilt={1.5}>
            Aajke-r main scene
          </StickerBadge>
          {item.is_demo ? <DemoBadge /> : null}
          {item.ai_status !== "ready" ? <AiStatusBadge status={item.ai_status} /> : null}
        </div>
        <Link href={`/news/${item.slug}`} className="block max-w-3xl rounded-xl focus-visible:outline-offset-4">
          <h2 className="font-display text-[2rem] leading-[1.05] font-bold tracking-tight sm:text-5xl lg:text-[3.4rem]">
            {glueSuffixes(item.headline)}
          </h2>
        </Link>
        {item.tldr ? (
          <p className="max-w-2xl rounded-2xl border-2 border-ink bg-paper/90 p-4 text-base leading-relaxed shadow-brutal-sm sm:text-lg">
            <span className="mr-1.5 font-display font-bold text-punch-deep">TL;DR</span>
            {item.tldr}
          </p>
        ) : null}
        <div className="mt-auto flex flex-wrap items-end justify-between gap-4">
          <div className="space-y-2">
            <ExamTags exams={item.exam_tags} />
            <p className="text-sm font-medium text-ink-soft">
              {item.primary_source ? `${item.primary_source.name} · ` : ""}
              {formatDate(item.date)} · {item.source_count} source{item.source_count === 1 ? "" : "s"}
            </p>
          </div>
          <Link
            href={`/news/${item.slug}`}
            className="inline-flex min-h-12 items-center gap-2 rounded-2xl border-2 border-ink bg-ink px-5 font-display font-bold text-cream shadow-brutal-sm transition-transform duration-150 hover:-translate-y-0.5 on-dark motion-reduce:transform-none"
          >
            Read the scene <ArrowRight className="size-5" aria-hidden="true" />
          </Link>
        </div>
      </div>
      {!serious ? (
        <div aria-hidden="true" className="pointer-events-none absolute right-4 bottom-24 hidden items-end gap-1 lg:flex">
          <ArrowDoodle className="mb-10 w-20 -scale-x-100 rotate-12" />
          <Mascot className="size-28 -rotate-6" />
        </div>
      ) : null}
    </article>
  );
}
