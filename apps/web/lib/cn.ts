export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export type Tone = "mango" | "mint" | "lavender" | "pink" | "punch" | "ink" | "paper" | "cream";

// Full class strings so Tailwind can see them at build time.
export const TONE_BG: Record<Tone, string> = {
  mango: "bg-mango text-ink",
  mint: "bg-mint text-ink",
  lavender: "bg-lavender text-ink",
  pink: "bg-pink text-ink",
  punch: "bg-punch text-ink",
  ink: "bg-ink text-cream",
  paper: "bg-paper text-ink",
  cream: "bg-cream text-ink",
};

export function stableTilt(seed: string, range = 2.5): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return Number((((Math.abs(h) % 1000) / 1000) * 2 * range - range).toFixed(2));
}
