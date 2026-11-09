import { Check, X } from "lucide-react";
import { Spinner } from "@/components/design-system/CandyButton";
import { cn } from "@/lib/cn";

export type OptionState = "idle" | "correct" | "wrong" | "dimmed";

/** Correctness is conveyed by icon + text label, never by colour alone. */
export function QuizOption({
  letter,
  text,
  state,
  disabled,
  checking = false,
  onSelect,
}: {
  letter: string;
  text: string;
  state: OptionState;
  disabled: boolean;
  checking?: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled}
      aria-busy={checking || undefined}
      aria-pressed={state === "correct" || state === "wrong"}
      className={cn(
        "group flex min-h-14 w-full items-center gap-3 rounded-2xl border-2 border-ink px-4 py-3 text-left text-base font-semibold transition-[transform,box-shadow,background-color] duration-150 sm:text-lg",
        state === "idle" && "bg-paper shadow-brutal-sm hover:-translate-y-0.5 hover:bg-mango hover:shadow-brutal motion-reduce:transform-none",
        state === "correct" && "animate-pop bg-mint shadow-brutal",
        state === "wrong" && "bg-pink shadow-brutal-sm",
        state === "dimmed" && "bg-paper/60 text-ink/60",
        disabled && state === "idle" && "cursor-default hover:translate-y-0 hover:bg-paper hover:shadow-brutal-sm",
      )}
    >
      <span
        className={cn(
          "grid size-9 shrink-0 place-items-center rounded-xl border-2 border-ink font-display font-bold",
          state === "correct" ? "bg-paper" : state === "wrong" ? "bg-paper" : "bg-cream",
        )}
        aria-hidden="true"
      >
        {checking ? (
          <Spinner className="size-5" />
        ) : state === "correct" ? (
          <Check className="size-5" />
        ) : state === "wrong" ? (
          <X className="size-5" />
        ) : (
          letter
        )}
      </span>
      <span className="flex-1">{text}</span>
      {checking ? <span className="shrink-0 text-sm font-bold">Checking...</span> : null}
      {state === "correct" ? <span className="shrink-0 text-sm font-bold">Correct answer</span> : null}
      {state === "wrong" ? <span className="shrink-0 text-sm font-bold">Your answer</span> : null}
    </button>
  );
}
