import "@fontsource-variable/inter";
import "@fontsource-variable/space-grotesk";
import "./globals.css";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { auth } from "@/auth";
import { MobileNav } from "@/components/layout/NavLinks";
import { QuickSticky } from "@/components/layout/QuickSticky";
import { SiteFooter } from "@/components/layout/SiteFooter";
import { SiteHeader } from "@/components/layout/SiteHeader";

export const metadata: Metadata = {
  title: { default: "Aajke Ki Scene? ☕", template: "%s · Aajke Ki Scene?" },
  description: "Duniya-r shob gossip, exam-er shob preparation. Banglish current affairs, daily quiz and a Brain Dump for exam aspirants.",
};

export const viewport: Viewport = { themeColor: "#FFF8E9", width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: { children: ReactNode }) {
  const session = await auth();
  return (
    <html lang="en-IN">
      <body className="min-h-dvh bg-cream text-ink">
        <a
          href="#main"
          className="sr-only z-50 rounded-xl border-2 border-ink bg-mango px-4 py-2 font-bold focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
        >
          Skip to content
        </a>
        <SiteHeader />
        <main id="main" className="mx-auto w-full max-w-[1400px] px-4 pt-6 pb-36 sm:px-6 lg:pb-20">
          {children}
        </main>
        <SiteFooter />
        <MobileNav />
        {session?.user ? <QuickSticky /> : null}
      </body>
    </html>
  );
}
