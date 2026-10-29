import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Asymmetric editorial grid: children choose their own col/row spans. */
export function BentoGrid({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-12 lg:gap-6", className)}>{children}</div>
  );
}
