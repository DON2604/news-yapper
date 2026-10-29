import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function SectionTitle({
  kicker,
  title,
  action,
  className,
  as: Tag = "h2",
}: {
  kicker?: string;
  title: ReactNode;
  action?: ReactNode;
  className?: string;
  as?: "h1" | "h2" | "h3";
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-3", className)}>
      <div>
        {kicker ? (
          <p className="font-display text-xs font-bold tracking-[0.18em] text-punch-deep uppercase">{kicker}</p>
        ) : null}
        <Tag
          className={cn(
            "font-display font-bold tracking-tight",
            Tag === "h1" ? "text-4xl sm:text-5xl lg:text-6xl" : Tag === "h2" ? "text-2xl sm:text-3xl" : "text-xl",
          )}
        >
          {title}
        </Tag>
      </div>
      {action}
    </div>
  );
}
