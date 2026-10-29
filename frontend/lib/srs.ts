// Mirror of backend/api/app/services/srs.py, used only to label the rating buttons.
// The server remains the source of truth for scheduling.

export type Outcome = "again" | "hard" | "good" | "easy";

const EASE_DELTA: Record<Outcome, number> = { again: -0.2, hard: -0.15, good: 0, easy: 0.1 };

export function nextIntervalDays(card: { ease_factor: number; interval_days: number; repetitions: number }, outcome: Outcome): number {
  if (outcome === "again") return 0;
  const ease = Math.min(3, Math.max(1.3, card.ease_factor + EASE_DELTA[outcome]));
  const good = card.repetitions === 0 ? 1 : card.repetitions === 1 ? 6 : Math.max(1, Math.ceil(Math.max(1, card.interval_days) * ease));
  let interval = good;
  if (outcome === "hard") interval = card.repetitions > 0 ? Math.max(1, Math.round(good * 0.5)) : 1;
  if (outcome === "easy") interval = Math.max(good + 1, Math.round(good * 1.3));
  return Math.min(interval, 365);
}

export function intervalLabel(days: number): string {
  if (days === 0) return "10 min";
  if (days === 1) return "1 day";
  if (days < 30) return `${days} days`;
  const months = Math.round(days / 30);
  return `${months} mo`;
}
