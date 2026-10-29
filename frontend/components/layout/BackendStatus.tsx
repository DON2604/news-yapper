"use client";

import { useEffect, useState } from "react";
import { cn, TONE_BG, type Tone } from "@/lib/cn";
import type { SiteHealth } from "@/lib/health";

type BackendState = SiteHealth["backend"] | "checking";

const COPY: Record<BackendState, string> = {
  checking: "Checking backend",
  up: "Backend up",
  degraded: "Backend degraded",
  down: "Backend down",
};

const TONE: Record<BackendState, Tone> = {
  checking: "cream",
  up: "mint",
  degraded: "mango",
  down: "punch",
};

export function BackendStatus() {
  const [state, setState] = useState<BackendState>("checking");
  const [detail, setDetail] = useState("Checking whether the API is reachable");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        const body = (await res.json().catch(() => null)) as Partial<SiteHealth> | null;
        const backend = body?.backend;
        const next: BackendState = backend === "up" || backend === "degraded" || backend === "down" ? backend : "down";
        const database =
          body?.database === "ok" ? "Database ok" : body?.database === "unreachable" ? "Database unreachable" : null;
        if (!cancelled) {
          setState(next);
          setDetail([COPY[next], database].filter(Boolean).join(". "));
        }
      } catch {
        if (!cancelled) {
          setState("down");
          setDetail("Backend down");
        }
      }
    }

    void check();
    const id = window.setInterval(() => void check(), 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <p role="status" aria-live="polite" title={detail} className="inline-flex">
      <span
        className={cn(
          "inline-flex items-center gap-2 rounded-full border-2 border-cream px-3 py-1",
          "font-display text-[0.72rem] font-bold uppercase tracking-wide whitespace-nowrap",
          TONE_BG[TONE[state]],
        )}
      >
        <span
          aria-hidden
          className={cn(
            "size-2.5 rounded-full border-2 border-ink",
            state === "up" && "bg-mint-deep",
            state === "degraded" && "bg-mango-deep",
            state === "down" && "bg-punch-deep",
            state === "checking" && "bg-ink-soft",
          )}
        />
        {COPY[state]}
      </span>
    </p>
  );
}
