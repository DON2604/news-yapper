import type { ComponentType } from "react";
import {
  CoinSticker,
  GlobeSticker,
  LeafSticker,
  MedalSticker,
  RocketSticker,
  ScalesSticker,
  StarSticker,
  type StickerProps,
  TrophySticker,
} from "@/components/design-system/stickers";
import type { Category } from "@/lib/api-types";
import type { Tone } from "@/lib/cn";

export interface CategoryMeta {
  label: string;
  short: string;
  tone: Tone;
  Sticker: ComponentType<StickerProps>;
}

export const CATEGORY_META: Record<Category, CategoryMeta> = {
  polity: { label: "Polity & Governance", short: "Polity", tone: "lavender", Sticker: ScalesSticker },
  economy: { label: "Economy & Banking", short: "Economy", tone: "mango", Sticker: CoinSticker },
  science: { label: "Science & Space", short: "Science", tone: "mint", Sticker: RocketSticker },
  international: { label: "International", short: "World", tone: "pink", Sticker: GlobeSticker },
  environment: { label: "Environment", short: "Environment", tone: "mint", Sticker: LeafSticker },
  awards: { label: "Awards & Honours", short: "Awards", tone: "mango", Sticker: TrophySticker },
  sports: { label: "Sports", short: "Sports", tone: "pink", Sticker: MedalSticker },
  other: { label: "GK & More", short: "GK", tone: "paper", Sticker: StarSticker },
};

export const CATEGORY_ORDER: Category[] = [
  "polity",
  "economy",
  "science",
  "international",
  "environment",
  "awards",
  "sports",
  "other",
];

export function categoryMeta(value: string | null | undefined): CategoryMeta {
  return CATEGORY_META[(value as Category) ?? "other"] ?? CATEGORY_META.other;
}
