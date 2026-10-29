"use client";

import { type CSSProperties, useMemo } from "react";
import { cn } from "@/lib/cn";

const COLORS = ["#FFD76A", "#F05A28", "#BFECD4", "#DCCBFF", "#FFD3D3", "#202020"];

/** Earned-moment confetti. Renders nothing for users who prefer reduced motion (CSS kills the animation). */
export function ProgressBurst({ fire, pieces = 22, className }: { fire: boolean; pieces?: number; className?: string }) {
  const bits = useMemo(
    () =>
      Array.from({ length: pieces }, (_, i) => {
        const angle = (i / pieces) * Math.PI * 2;
        const dist = 60 + ((i * 37) % 50);
        return {
          dx: `${Math.cos(angle) * dist}px`,
          dy: `${Math.sin(angle) * dist - 20}px`,
          rot: `${(i * 67) % 360}deg`,
          color: COLORS[i % COLORS.length],
          round: i % 3 === 0,
        };
      }),
    [pieces],
  );
  if (!fire) return null;
  return (
    <div aria-hidden="true" className={cn("pointer-events-none absolute inset-0 overflow-visible", className)}>
      <div className="absolute top-1/2 left-1/2">
        {bits.map((b, i) => (
          <span
            key={i}
            className={cn("absolute block size-2.5 border border-ink animate-burst", b.round ? "rounded-full" : "rounded-[2px]")}
            style={{ background: b.color, "--dx": b.dx, "--dy": b.dy, "--rot": b.rot } as CSSProperties}
          />
        ))}
      </div>
    </div>
  );
}

export function ProgressRing({
  value,
  max,
  size = 88,
  label,
  className,
}: {
  value: number;
  max: number;
  size?: number;
  label: string;
  className?: string;
}) {
  const ratio = max > 0 ? Math.min(1, value / max) : 0;
  const r = size / 2 - 7;
  const circ = 2 * Math.PI * r;
  return (
    <div className={cn("relative inline-grid place-items-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeOpacity={0.18} strokeWidth={9} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#FFD76A"
          strokeWidth={9}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - ratio)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          className="transition-[stroke-dashoffset] duration-500 motion-reduce:transition-none"
        />
      </svg>
      <span className="absolute font-display text-lg font-bold">
        {value}/{max}
      </span>
    </div>
  );
}
