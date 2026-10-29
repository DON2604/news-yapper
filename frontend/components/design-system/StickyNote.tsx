import type { ReactNode } from "react";
import { Tape } from "@/components/design-system/Tape";
import type { NoteColor } from "@/lib/api-types";
import { cn, stableTilt } from "@/lib/cn";

const NOTE_BG: Record<NoteColor, string> = {
  mango: "bg-mango",
  lavender: "bg-lavender",
  mint: "bg-mint",
  pink: "bg-pink",
};
const TAPE: Record<NoteColor, "mango" | "mint" | "pink" | "lavender"> = {
  mango: "mint",
  lavender: "mango",
  mint: "pink",
  pink: "lavender",
};

/** Renders user text as text nodes only; a light "- item" list syntax becomes bullets. */
export function NoteBody({ text, clamp }: { text: string; clamp?: boolean }) {
  const lines = text.split("\n").filter((l) => l.trim().length > 0);
  return (
    <div className={cn("space-y-1 text-[0.95rem] leading-snug break-words", clamp && "line-clamp-6")}>
      {lines.map((line, i) =>
        /^\s*[-*•]\s+/.test(line) ? (
          <p key={i} className="flex gap-1.5">
            <span aria-hidden="true">•</span>
            <span>{line.replace(/^\s*[-*•]\s+/, "")}</span>
          </p>
        ) : (
          <p key={i}>{line}</p>
        ),
      )}
    </div>
  );
}

export function StickyNote({
  id,
  title,
  body,
  color,
  tags = [],
  pinned = false,
  selected = false,
  footer,
  tilt = true,
  className,
}: {
  id: string;
  title: string;
  body: string;
  color: NoteColor;
  tags?: string[];
  pinned?: boolean;
  selected?: boolean;
  footer?: ReactNode;
  tilt?: boolean;
  className?: string;
}) {
  const angle = tilt ? stableTilt(id) : 0;
  return (
    <div
      className={cn(
        "relative flex min-h-44 flex-col gap-2 rounded-[6px] border-2 border-ink p-4 pt-6 shadow-brutal paper-grain",
        NOTE_BG[color],
        selected && "outline-4 outline-offset-2 outline-punch",
        className,
      )}
      style={{ rotate: `${angle}deg` }}
    >
      <Tape tone={TAPE[color]} className="-top-3 left-1/2 -translate-x-1/2 -rotate-3" />
      {pinned ? (
        <span className="absolute top-2 right-2 rounded-full border-2 border-ink bg-punch px-1.5 text-[0.6rem] font-bold uppercase">
          Pinned
        </span>
      ) : null}
      {title ? <h3 className="pr-12 font-display text-lg leading-tight font-bold break-words">{title}</h3> : null}
      <NoteBody text={body} clamp />
      {tags.length ? (
        <ul className="mt-auto flex flex-wrap gap-1 pt-1" aria-label="Tags">
          {tags.map((t) => (
            <li key={t} className="rounded-md border border-ink/40 bg-paper/70 px-1.5 text-xs font-semibold">
              #{t}
            </li>
          ))}
        </ul>
      ) : null}
      {footer}
    </div>
  );
}
