import type { ReactNode } from "react";
import { Mascot, type Mood } from "@/components/design-system/stickers";
import { cn } from "@/lib/cn";

export function EmptyState({
  title,
  children,
  action,
  mood = "sleepy",
  className,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  mood?: Mood;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex flex-col items-center gap-3 rounded-card border-2 border-dashed border-ink/60 bg-paper/70 px-6 py-10 text-center",
        className,
      )}
    >
      <Mascot mood={mood} className="size-24" steam={mood !== "sleepy"} />
      <h3 className="font-display text-xl font-bold">{title}</h3>
      {children ? <div className="max-w-md text-ink-soft">{children}</div> : null}
      {action}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-xl bg-ink/10", className)} />;
}
