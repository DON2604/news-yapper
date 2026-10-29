import { cn } from "@/lib/cn";

/** Washi-tape strip for scrapbook accents. Decorative only. */
export function Tape({ className, tone = "mango" }: { className?: string; tone?: "mango" | "mint" | "pink" | "lavender" }) {
  const fill = { mango: "bg-mango/80", mint: "bg-mint/85", pink: "bg-pink/85", lavender: "bg-lavender/85" }[tone];
  return (
    <span
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute h-6 w-20 border border-ink/25 shadow-sm",
        "[background-image:repeating-linear-gradient(90deg,transparent_0_6px,rgb(255_255_255/0.35)_6px_9px)]",
        fill,
        className,
      )}
    />
  );
}
