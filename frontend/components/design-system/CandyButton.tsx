import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn, TONE_BG, type Tone } from "@/lib/cn";

type Size = "sm" | "md" | "lg";

const SIZES: Record<Size, string> = {
  sm: "min-h-11 px-3.5 text-sm gap-1.5",
  md: "min-h-12 px-5 text-base gap-2",
  lg: "min-h-14 px-6 text-lg gap-2.5",
};

const BASE =
  "inline-flex items-center justify-center rounded-2xl border-2 border-ink font-display font-bold " +
  "shadow-brutal-sm transition-[transform,box-shadow] duration-150 select-none " +
  "hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-brutal " +
  "active:translate-x-0.5 active:translate-y-0.5 active:shadow-none " +
  "motion-reduce:transform-none disabled:opacity-55 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:shadow-brutal-sm";

export function candyClasses(tone: Tone = "punch", size: Size = "md", className?: string): string {
  return cn(BASE, TONE_BG[tone], SIZES[size], tone === "ink" && "on-dark", className);
}

type CommonProps = { tone?: Tone; size?: Size; className?: string; children: ReactNode };

export function CandyButton({
  tone = "punch",
  size = "md",
  className,
  children,
  type = "button",
  ...rest
}: CommonProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type={type} className={candyClasses(tone, size, className)} {...rest}>
      {children}
    </button>
  );
}

export function CandyLink({
  href,
  tone = "punch",
  size = "md",
  className,
  children,
  ...rest
}: CommonProps & { href: string; prefetch?: boolean; "aria-label"?: string }) {
  return (
    <Link href={href} className={candyClasses(tone, size, className)} {...rest}>
      {children}
    </Link>
  );
}
