import { ExternalLink, Trash2 } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { PinSticker } from "@/components/design-system/stickers";
import type { Snapshot } from "@/lib/api-types";
import { categoryMeta } from "@/lib/categories";
import { cn, stableTilt } from "@/lib/cn";
import { formatDate } from "@/lib/format";

/** A saved article as a pinned polaroid-style card on the study desk. */
export function ArticleSnapshotCard({
  snapshot,
  onRemove,
  selectControl,
  className,
}: {
  snapshot: Snapshot;
  onRemove?: () => void;
  selectControl?: ReactNode;
  className?: string;
}) {
  const meta = categoryMeta(snapshot.category);
  return (
    <article
      className={cn("relative flex flex-col gap-2 rounded-xl border-2 border-ink bg-paper p-4 pt-6 shadow-brutal", className)}
      style={{ rotate: `${stableTilt(snapshot.id, 1.5)}deg` }}
    >
      <PinSticker className="absolute -top-5 left-1/2 size-9 -translate-x-1/2" />
      <div className="flex flex-wrap items-center gap-1.5">
        {selectControl}
        <StickerBadge tone={meta.tone === "paper" ? "mango" : meta.tone} tilt={0} icon={<meta.Sticker />}>
          {meta.short}
        </StickerBadge>
        {snapshot.verified ? (
          <StickerBadge tone="mint" tilt={0}>
            Source-checked
          </StickerBadge>
        ) : (
          <StickerBadge tone="paper" tilt={0}>
            Headline only
          </StickerBadge>
        )}
        {snapshot.is_demo ? (
          <StickerBadge tone="ink" tilt={0}>
            Demo
          </StickerBadge>
        ) : null}
      </div>
      <h3 className="font-display text-lg leading-snug font-bold">
        {snapshot.event_slug && snapshot.article_available ? (
          <Link href={`/news/${snapshot.event_slug}`} className="hover:underline">
            {snapshot.saved_title}
          </Link>
        ) : (
          snapshot.saved_title
        )}
      </h3>
      {snapshot.saved_banglish_summary ? (
        <p className="line-clamp-3 text-sm text-ink/85">{snapshot.saved_banglish_summary}</p>
      ) : null}
      {snapshot.saved_key_facts.length ? (
        <p className="text-xs font-semibold text-ink-soft">{snapshot.saved_key_facts.length} exam facts saved</p>
      ) : null}
      {snapshot.article_updated_since_save ? (
        <p className="rounded-lg border border-ink/40 bg-pink/60 px-2 py-1 text-xs font-semibold">
          The live article changed after you saved this copy.
        </p>
      ) : null}
      <div className="mt-auto flex items-center justify-between gap-2 pt-1 text-xs text-ink-soft">
        <span>
          Saved {formatDate(snapshot.saved_at)}
          {snapshot.source_name ? ` · ${snapshot.source_name}` : ""}
        </span>
        <span className="flex gap-1">
          {snapshot.source_url ? (
            <a
              href={snapshot.source_url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="grid size-9 place-items-center rounded-lg hover:bg-mango"
              aria-label={`Open source for ${snapshot.saved_title} (new tab)`}
            >
              <ExternalLink className="size-4" aria-hidden="true" />
            </a>
          ) : null}
          {onRemove ? (
            <button
              type="button"
              onClick={onRemove}
              className="grid size-9 place-items-center rounded-lg hover:bg-pink"
              aria-label={`Remove saved copy of ${snapshot.saved_title}`}
            >
              <Trash2 className="size-4" aria-hidden="true" />
            </button>
          ) : null}
        </span>
      </div>
    </article>
  );
}
