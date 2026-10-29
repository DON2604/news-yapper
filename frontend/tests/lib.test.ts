import { describe, expect, it } from "vitest";
import { glueSuffixes, percent, plural } from "@/lib/format";
import { intervalLabel, nextIntervalDays } from "@/lib/srs";

describe("format helpers", () => {
  it("glues Banglish suffixes with a non-breaking hyphen", () => {
    expect(glueSuffixes("Aajke-r cha")).toBe("Aajke\u2011r cha");
    expect(glueSuffixes("south pole-er kache")).toBe("south pole\u2011er kache");
    expect(glueSuffixes("Chandrayaan-3-er")).toBe("Chandrayaan-3\u2011er");
    expect(glueSuffixes("well-known")).toBe("well-known");
  });

  it("pluralises and formats percentages", () => {
    expect(plural(1, "card")).toBe("1 card");
    expect(plural(3, "card")).toBe("3 cards");
    expect(plural(2, "story", "stories")).toBe("2 stories");
    expect(percent(0.756)).toBe("76%");
    expect(percent(null)).toBe("—");
  });
});

describe("SM-2 preview mirrors the server schedule", () => {
  const fresh = { ease_factor: 2.5, interval_days: 0, repetitions: 0 };
  const second = { ease_factor: 2.5, interval_days: 6, repetitions: 2 };

  it("matches backend/api/tests sm2 progression", () => {
    expect(nextIntervalDays(fresh, "good")).toBe(1);
    expect(nextIntervalDays({ ...fresh, interval_days: 1, repetitions: 1 }, "good")).toBe(6);
    expect(nextIntervalDays(second, "good")).toBe(15);
    expect(nextIntervalDays(second, "again")).toBe(0);
    expect(nextIntervalDays(second, "easy")).toBeGreaterThan(15);
    expect(nextIntervalDays({ ease_factor: 3, interval_days: 300, repetitions: 8 }, "easy")).toBe(365);
  });

  it("labels intervals for the rating buttons", () => {
    expect(intervalLabel(0)).toBe("10 min");
    expect(intervalLabel(1)).toBe("1 day");
    expect(intervalLabel(15)).toBe("15 days");
    expect(intervalLabel(90)).toBe("3 mo");
  });
});
