const TZ = "Asia/Kolkata";

export function formatDate(value: string | null | undefined, opts: Intl.DateTimeFormatOptions = {}): string {
  if (!value) return "date not provided";
  const date = new Date(value.length === 10 ? `${value}T00:00:00+05:30` : value);
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: TZ, ...opts }).format(
    date,
  );
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "time not provided";
  return formatDate(value, { hour: "numeric", minute: "2-digit" });
}

export function todayLabel(now = new Date()): string {
  return new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long", timeZone: TZ }).format(now);
}

export function relativeDays(value: string, now = new Date()): string {
  const diff = Math.round((new Date(value).getTime() - now.getTime()) / 86_400_000);
  if (diff <= 0) return "today";
  if (diff === 1) return "tomorrow";
  return `in ${diff} days`;
}

export const EXAM_LABELS: Record<string, string> = {
  SSC: "SSC",
  UPSC: "UPSC",
  STATE_PSC: "State PSC",
  BANKING: "Banking",
  RAILWAYS: "Railways",
  GENERAL: "General",
};

export function greeting(name: string | null | undefined, hour = Number(new Intl.DateTimeFormat("en-IN", { hour: "numeric", hourCycle: "h23", timeZone: TZ }).format(new Date()))): string {
  const who = name ? name.split(" ")[0] : "bondhu";
  if (hour < 12) return `Shuprobhat, ${who}!`;
  if (hour < 17) return `Ki khobor, ${who}?`;
  return `Shubho shondhya, ${who}!`;
}

export function percent(value: number | null | undefined): string {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

export function plural(count: number, word: string, many = `${word}s`): string {
  return `${count} ${count === 1 ? word : many}`;
}

/** Keeps Banglish suffixes glued to their word ("Aajke-r", "pole-er") with a non-breaking hyphen. */
export function glueSuffixes(text: string): string {
  return text.replace(/(\w)-(r|er|e|te|ke|ta|ti|ra|der|o)\b/g, "$1\u2011$2");
}
