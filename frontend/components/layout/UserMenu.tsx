"use client";

import { LogOut, Settings, Shield, Trophy } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";
import { Spinner } from "@/components/design-system/CandyButton";
import { cn } from "@/lib/cn";

function LogoutButton() {
  const { pending } = useFormStatus();
  return (
    <button
      role="menuitem"
      type="submit"
      disabled={pending}
      aria-busy={pending || undefined}
      className={cn("flex min-h-11 w-full items-center gap-2 rounded-xl px-3 text-left font-semibold hover:bg-pink")}
    >
      {pending ? <Spinner className="size-4" /> : <LogOut className="size-4" aria-hidden="true" />}
      {pending ? "Logging out..." : "Log out"}
    </button>
  );
}

export function UserMenu({ name, isAdmin, signOutAction }: { name: string; isAdmin: boolean; signOutAction: () => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);
  const initials = name
    .split(/\s+/)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="grid size-11 place-items-center rounded-full border-2 border-ink bg-lavender font-display font-bold shadow-brutal-sm"
      >
        <span aria-hidden="true">{initials || "?"}</span>
        <span className="sr-only">Account menu for {name}</span>
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-56 animate-pop rounded-2xl border-2 border-ink bg-paper p-2 shadow-brutal"
        >
          <p className="px-3 py-2 text-sm text-ink-soft">
            Logged in as <strong className="text-ink">{name}</strong>
          </p>
          {[
            { href: "/progress", label: "Progress", icon: Trophy },
            { href: "/settings", label: "Settings & privacy", icon: Settings },
            ...(isAdmin ? [{ href: "/admin", label: "Admin desk", icon: Shield }] : []),
          ].map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              role="menuitem"
              href={href}
              onClick={() => setOpen(false)}
              className="flex min-h-11 items-center gap-2 rounded-xl px-3 font-semibold hover:bg-mango"
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </Link>
          ))}
          <form action={signOutAction}>
            <LogoutButton />
          </form>
        </div>
      ) : null}
    </div>
  );
}
