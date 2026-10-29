"use client";

import { BookmarkCheck, BookmarkPlus, StickyNote as StickyIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { CandyButton, candyClasses } from "@/components/design-system/CandyButton";
import { NoteComposer } from "@/components/notes/NoteComposer";
import type { Snapshot } from "@/lib/api-types";
import { api } from "@/lib/client-api";

export function ArticleActions({
  slug,
  title,
  snapshotId,
  signedIn,
}: {
  slug: string;
  title: string;
  snapshotId: string | null;
  signedIn: boolean;
}) {
  const [savedId, setSavedId] = useState<string | null>(snapshotId);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [composerOpen, setComposerOpen] = useState(false);

  if (!signedIn) {
    return (
      <Link href={`/signin?callbackUrl=/news/${slug}`} className={candyClasses("mango", "md", "w-full")}>
        Login to pin this to Brain Dump
      </Link>
    );
  }

  async function save() {
    setBusy(true);
    setMessage(null);
    try {
      const snap = await api<Snapshot>("snapshots", { method: "POST", body: { article_slug: slug } });
      setSavedId(snap.id);
      setMessage(snap.created ? "Bro, bookmark kore rakhlam - exam-e kaje lagbe." : "Already in your Brain Dump.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Couldn't save right now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-2.5">
      <CandyButton
        tone={savedId ? "mint" : "mango"}
        className="w-full"
        onClick={save}
        disabled={Boolean(savedId)}
        loading={busy}
        loadingText="Pinning..."
      >
        {savedId ? <BookmarkCheck className="size-5" aria-hidden="true" /> : <BookmarkPlus className="size-5" aria-hidden="true" />}
        {savedId ? "Pinned to Brain Dump" : "Pin to Brain Dump"}
      </CandyButton>
      <CandyButton tone="lavender" className="w-full" onClick={() => setComposerOpen(true)}>
        <StickyIcon className="size-5" aria-hidden="true" /> Add a sticky note
      </CandyButton>
      <p aria-live="polite" className="min-h-5 text-sm font-semibold text-mint-deep">
        {message}
      </p>
      <NoteComposer
        open={composerOpen}
        onClose={() => setComposerOpen(false)}
        initial={{ title: title.slice(0, 120), body: "", color: "lavender", tags: "", snapshot_id: savedId }}
        onSaved={() => setMessage("Sticky saved ✓")}
      />
    </div>
  );
}
