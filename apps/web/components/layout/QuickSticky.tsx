"use client";

import { Plus } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { NoteComposer } from "@/components/notes/NoteComposer";

// Pages with their own primary actions (or their own "New sticky") skip the floating button.
const HIDDEN_ON = ["/brain-dump", "/quiz", "/settings", "/onboarding", "/admin", "/signin"];

/** Floating "+ Sticky" available from reading pages for signed-in users. */
export function QuickSticky() {
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  if (HIDDEN_ON.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed right-4 bottom-24 z-30 inline-flex min-h-12 items-center gap-1.5 rounded-full border-2 border-ink bg-lavender px-4 font-display font-bold shadow-brutal transition-transform duration-150 hover:-translate-y-0.5 motion-reduce:transform-none lg:right-8 lg:bottom-8"
      >
        <Plus className="size-5" aria-hidden="true" /> Sticky
      </button>
      <NoteComposer
        open={open}
        onClose={() => setOpen(false)}
        onSaved={() => {
          setToast("Sticky saved to Brain Dump ✓");
          router.refresh();
          window.setTimeout(() => setToast(null), 2600);
        }}
      />
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-40 z-50 flex justify-center lg:bottom-24">
        {toast ? (
          <p className="animate-pop rounded-full border-2 border-ink bg-mint px-4 py-2 font-semibold shadow-brutal-sm">{toast}</p>
        ) : null}
      </div>
    </>
  );
}
