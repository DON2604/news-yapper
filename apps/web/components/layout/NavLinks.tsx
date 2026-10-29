"use client";

import { BookOpenCheck, Brain, Home, Newspaper, Sparkles, Trophy } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

const LINKS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/news", label: "News", icon: Newspaper },
  { href: "/quiz/daily", label: "Daily Quiz", icon: Sparkles },
  { href: "/brain-dump", label: "Brain Dump", icon: Brain },
  { href: "/revision", label: "Revision", icon: BookOpenCheck },
  { href: "/progress", label: "Progress", icon: Trophy },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export function DesktopNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="hidden lg:block">
      <ul className="flex items-center gap-1">
        {LINKS.map(({ href, label }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "inline-flex min-h-11 items-center rounded-xl border-2 px-3 font-display text-[0.95rem] font-bold transition-colors",
                  active ? "border-ink bg-mango shadow-brutal-sm" : "border-transparent hover:border-ink hover:bg-paper",
                )}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

const MOBILE = [
  { href: "/", label: "Home", icon: Home },
  { href: "/news", label: "News", icon: Newspaper },
  { href: "/quiz/daily", label: "Quiz", icon: Sparkles, primary: true },
  { href: "/brain-dump", label: "Dump", icon: Brain },
  { href: "/revision", label: "Revise", icon: BookOpenCheck },
];

export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-40 border-t-2 border-ink bg-cream/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
    >
      <ul className="mx-auto grid max-w-lg grid-cols-5 items-end px-2 pt-1.5 pb-2">
        {MOBILE.map(({ href, label, icon: Icon, primary }) => {
          const active = isActive(pathname, href);
          return (
            <li key={href} className="flex justify-center">
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-12 min-w-14 flex-col items-center justify-center gap-0.5 rounded-2xl text-[0.7rem] font-bold",
                  primary
                    ? "-mt-6 size-16 border-2 border-ink bg-punch shadow-brutal-sm"
                    : active
                      ? "bg-mango px-2 ring-2 ring-ink"
                      : "px-2 text-ink-soft",
                )}
              >
                <Icon className={primary ? "size-6" : "size-5"} aria-hidden="true" />
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
