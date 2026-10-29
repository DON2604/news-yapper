import Link from "next/link";
import { Mascot } from "@/components/design-system/stickers";
import { cn } from "@/lib/cn";

export function Wordmark({ compact = false, className }: { compact?: boolean; className?: string }) {
  return (
    <Link
      href="/"
      className={cn("group inline-flex items-center gap-2 rounded-xl py-1 pr-2", className)}
      aria-label="News-Yapper - home"
    >
      <Mascot className="size-10 shrink-0 transition-transform duration-200 group-hover:-rotate-6 motion-reduce:transition-none sm:size-11" />
      <span className="font-display text-[1.35rem] leading-none font-bold tracking-tight sm:text-2xl">
        <span>News</span>
        <span className="text-punch-deep">-</span>
        <span className="marker px-0.5">Yapper</span>
      </span>
      {!compact ? (
        <span className="hidden rounded-full border-2 border-ink bg-mint px-2 py-0.5 text-[0.65rem] font-bold tracking-wide uppercase xl:inline">
          Banglish news + exam prep
        </span>
      ) : null}
    </Link>
  );
}
