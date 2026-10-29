import type { ReactNode } from "react";
import { cn, TONE_BG, type Tone } from "@/lib/cn";

export function StickerBadge({
  tone = "mango",
  tilt = -2,
  icon,
  className,
  children,
}: {
  tone?: Tone;
  tilt?: number;
  icon?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border-2 border-ink px-2.5 py-0.5",
        "font-display text-[0.72rem] font-bold uppercase tracking-wide whitespace-nowrap",
        TONE_BG[tone],
        className,
      )}
      style={{ transform: `rotate(${tilt}deg)` }}
    >
      {icon ? <span className="inline-flex size-4 shrink-0">{icon}</span> : null}
      {children}
    </span>
  );
}

export function DemoBadge({ className }: { className?: string }) {
  return (
    <StickerBadge tone="ink" tilt={2} className={className}>
      Demo · evergreen
    </StickerBadge>
  );
}

const AI_STATUS: Record<string, { label: string; tone: Tone }> = {
  ready: { label: "Source-checked", tone: "mint" },
  pending: { label: "AI summary pending", tone: "paper" },
  in_review: { label: "In editor review", tone: "pink" },
};

export function AiStatusBadge({ status, className }: { status: string; className?: string }) {
  const meta = AI_STATUS[status] ?? AI_STATUS.pending;
  return (
    <StickerBadge tone={meta.tone} tilt={0} className={className}>
      {meta.label}
    </StickerBadge>
  );
}
