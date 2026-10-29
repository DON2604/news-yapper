import type { HTMLAttributes, ReactNode } from "react";
import { cn, TONE_BG, type Tone } from "@/lib/cn";

type As = "div" | "article" | "section" | "aside" | "li";

export function BrutalCard({
  as: Tag = "div",
  tone = "paper",
  interactive = false,
  flat = false,
  className,
  children,
  ...rest
}: {
  as?: As;
  tone?: Tone;
  interactive?: boolean;
  flat?: boolean;
  className?: string;
  children: ReactNode;
} & HTMLAttributes<HTMLElement>) {
  return (
    <Tag
      className={cn(
        "relative rounded-card border-2 border-ink",
        TONE_BG[tone],
        flat ? "shadow-none" : "shadow-brutal",
        interactive && "brutal-lift",
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}
