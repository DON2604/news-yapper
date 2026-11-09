"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { cn } from "@/lib/cn";

const REFRESH_MS = 20_000;

/** How much of today's edition already has its Banglish rewrite. Re-reads the page while stories are pending. */
export function EditionProgress({ ready, total, className }: { ready: number; total: number; className?: string }) {
  const router = useRouter();
  const pending = Math.max(0, total - ready);
  const percent = total > 0 ? Math.round((ready / total) * 100) : 0;

  useEffect(() => {
    if (!pending) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, REFRESH_MS);
    return () => window.clearInterval(id);
  }, [pending, router]);

  if (!total) return null;

  return (
    <section
      aria-label="Today's edition progress"
      className={cn("rounded-2xl border-2 border-ink bg-paper px-4 py-3 shadow-brutal-sm", className)}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-display text-base font-bold sm:text-lg">
          {pending ? "AI bhai golpo gulo Banglish-e likhchhe ✍️" : "Aajke-r shob golpo ready ✨"}
        </p>
        <p className="font-display text-sm font-bold text-ink-soft">
          {ready}/{total} ready · {percent}%
        </p>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={ready}
        aria-valuetext={`${ready} of ${total} stories ready`}
        className="mt-2 h-4 overflow-hidden rounded-full border-2 border-ink bg-cream-deep"
      >
        <div
          className={cn(
            "h-full rounded-full bg-mango transition-[width] duration-700 motion-reduce:transition-none",
            pending > 0 && "progress-stripes",
          )}
          style={{ width: `${Math.max(percent, pending ? 4 : 0)}%` }}
        />
      </div>
      {pending ? (
        <p className="mt-2 text-xs font-medium text-ink-soft">
          {pending} ta golpo ekhono source headline-e ache. Ready holei ei page nije theke update hobe.
        </p>
      ) : null}
    </section>
  );
}
