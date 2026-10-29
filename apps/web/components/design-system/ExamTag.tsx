import { cn } from "@/lib/cn";
import { EXAM_LABELS } from "@/lib/format";

const EXAM_TONE: Record<string, string> = {
  SSC: "bg-lavender",
  UPSC: "bg-mango",
  STATE_PSC: "bg-mint",
  BANKING: "bg-pink",
  RAILWAYS: "bg-paper",
  GENERAL: "bg-cream",
};

export function ExamTag({ exam, className }: { exam: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-lg border-[1.5px] border-ink px-2 py-0.5 text-xs font-semibold text-ink",
        EXAM_TONE[exam] ?? "bg-paper",
        className,
      )}
    >
      {EXAM_LABELS[exam] ?? exam}
    </span>
  );
}

export function ExamTags({ exams, max = 4 }: { exams: string[]; max?: number }) {
  if (!exams.length) return null;
  const shown = exams.slice(0, max);
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Relevant exams">
      {shown.map((e) => (
        <li key={e}>
          <ExamTag exam={e} />
        </li>
      ))}
      {exams.length > max ? <li className="text-xs font-semibold text-ink-soft">+{exams.length - max}</li> : null}
    </ul>
  );
}
