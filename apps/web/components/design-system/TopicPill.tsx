import Link from "next/link";
import type { Category } from "@/lib/api-types";
import { CATEGORY_META } from "@/lib/categories";
import { cn, TONE_BG } from "@/lib/cn";

export function TopicPill({ category, href, active = false }: { category: Category; href: string; active?: boolean }) {
  const meta = CATEGORY_META[category];
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "inline-flex min-h-11 shrink-0 items-center gap-2 rounded-full border-2 border-ink px-3.5 py-1.5 font-display text-sm font-bold",
        "transition-[transform,box-shadow] duration-150 hover:-translate-y-0.5 hover:shadow-brutal-sm motion-reduce:transform-none",
        active ? "bg-ink text-cream shadow-brutal-sm" : TONE_BG[meta.tone],
      )}
    >
      <meta.Sticker className="size-6" />
      {meta.short}
    </Link>
  );
}
