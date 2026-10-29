import { LoaderCircle } from "lucide-react";
import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { LinkPending } from "@/components/design-system/LinkPending";
import { cn, TONE_BG, type Tone } from "@/lib/cn";

type Size = "sm" | "md" | "lg";

const SIZES: Record<Size, string> = {
  sm: "min-h-11 px-3.5 text-sm gap-1.5",
  md: "min-h-12 px-5 text-base gap-2",
  lg: "min-h-14 px-6 text-lg gap-2.5",
};

const SPINNER: Record<Size, string> = { sm: "size-4", md: "size-5", lg: "size-5" };

const BASE =
  "inline-flex items-center justify-center rounded-2xl border-2 border-ink font-display font-bold " +
  "shadow-brutal-sm transition-[transform,box-shadow] duration-150 select-none " +
  "hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-brutal " +
  "active:translate-x-0.5 active:translate-y-0.5 active:shadow-none " +
  "motion-reduce:transform-none disabled:opacity-55 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:shadow-brutal-sm " +
  "aria-busy:cursor-progress aria-busy:opacity-80";

export function candyClasses(tone: Tone = "punch", size: Size = "md", className?: string): string {
  return cn(BASE, TONE_BG[tone], SIZES[size], tone === "ink" && "on-dark", className);
}

export function Spinner({ className }: { className?: string }) {
  return <LoaderCircle className={cn("shrink-0 animate-spin", className)} aria-hidden="true" />;
}

type CommonProps = { tone?: Tone; size?: Size; className?: string; children: ReactNode };
type LoadingProps = { loading?: boolean; loadingText?: ReactNode };
export type CandyButtonProps = CommonProps & LoadingProps & ButtonHTMLAttributes<HTMLButtonElement>;

export function CandyButton({
  tone = "punch",
  size = "md",
  className,
  children,
  type = "button",
  loading = false,
  loadingText,
  disabled,
  ...rest
}: CandyButtonProps) {
  return (
    <button
      type={type}
      className={candyClasses(tone, size, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <>
          <Spinner className={SPINNER[size]} />
          {loadingText ?? children}
        </>
      ) : (
        children
      )}
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
    <Link href={href} className={candyClasses(tone, size, cn("relative", className))} {...rest}>
      {children}
      <LinkPending />
    </Link>
  );
}
