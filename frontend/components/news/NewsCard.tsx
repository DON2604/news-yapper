import { BookmarkCheck } from "lucide-react";
import Link from "next/link";
import { ExamTags } from "@/components/design-system/ExamTag";
import { LinkPending } from "@/components/design-system/LinkPending";
import { AiStatusBadge, DemoBadge, StickerBadge } from "@/components/design-system/StickerBadge";
import type { NewsItem } from "@/lib/api-types";
import { categoryMeta } from "@/lib/categories";
import { cn, TONE_BG } from "@/lib/cn";
import { formatDate, glueSuffixes } from "@/lib/format";

/** Feed / bento card. Colour comes from the category; sensitive stories stay calm (paper, no sticker). */
export function NewsCard({
  item,
  variant = "card",
  className,
}: {
  item: NewsItem;
  variant?: "card" | "feature" | "row";
  className?: string;
}) {
  const meta = categoryMeta(item.category);
  const tone = item.sensitive ? "paper" : meta.tone;
  const href = `/news/${item.slug}`;

  if (variant === "row") {
    return (
      <article className={cn("group relative flex gap-3 rounded-2xl border-2 border-ink bg-paper p-3 transition-colors hover:bg-cream-deep", className)}>
        <div className={cn("grid size-12 shrink-0 place-items-center rounded-xl border-2 border-ink", TONE_BG[tone])}>
          {item.sensitive ? <span className="text-xs font-bold">News</span> : <meta.Sticker className="size-8" />}
        </div>
        <div className="min-w-0 flex-1">
          <Link href={href} className="line-clamp-2 font-display text-[1.02rem] leading-snug font-bold group-hover:underline">
            {glueSuffixes(item.headline)}
            <LinkPending />
          </Link>
          <p className="mt-1 text-xs font-medium text-ink-soft">
            {meta.short} · {formatDate(item.date)}
            {item.ai_status !== "ready" ? " · AI summary pending" : ""}
            {item.is_demo ? " · DEMO" : ""}
          </p>
        </div>
      </article>
    );
  }

  return (
    <article
      className={cn(
        "group relative flex h-full flex-col gap-3 rounded-card border-2 border-ink p-5 shadow-brutal brutal-lift",
        TONE_BG[tone],
        variant === "feature" && "sm:p-6",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        {item.sensitive ? (
          <StickerBadge tone="paper" tilt={0}>
            Serious story
          </StickerBadge>
        ) : (
          <StickerBadge tone={tone === "paper" ? "mango" : "paper"} icon={<meta.Sticker />}>
            {meta.short}
          </StickerBadge>
        )}
        {item.is_demo ? <DemoBadge /> : null}
        {item.ai_status !== "ready" ? <AiStatusBadge status={item.ai_status} /> : null}
        {item.correction_status === "corrected" ? (
          <StickerBadge tone="pink" tilt={0}>
            Updated
          </StickerBadge>
        ) : null}
      </div>
      <h3 className={cn("font-display leading-tight font-bold", variant === "feature" ? "text-2xl sm:text-3xl" : "text-xl")}>
        <Link href={href} className="after:absolute after:inset-0 after:rounded-card focus-visible:outline-none">
          {glueSuffixes(item.headline)}
          <LinkPending />
        </Link>
      </h3>
      {item.tldr ? (
        <p className={cn("text-[0.95rem] leading-relaxed text-ink/85", variant === "feature" ? "line-clamp-4" : "line-clamp-3")}>
          {item.tldr}
        </p>
      ) : null}
      <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1">
        <ExamTags exams={item.exam_tags} max={3} />
        <span className="flex items-center gap-1 text-xs font-semibold text-ink-soft">
          {item.saved ? <BookmarkCheck className="size-4 text-mint-deep" aria-label="Saved to Brain Dump" /> : null}
          {formatDate(item.date)}
        </span>
      </div>
    </article>
  );
}
