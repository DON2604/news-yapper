import { CandyLink } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";
import { SectionTitle } from "@/components/design-system/SectionTitle";
import { NotebookSticker, PencilSticker } from "@/components/design-system/stickers";
import { BrainDumpBoard } from "@/components/notes/BrainDumpBoard";
import type { Mistake, Note, Snapshot } from "@/lib/api-types";
import { backendOrNull } from "@/lib/server/api";
import { requireUser } from "@/lib/server/session";

export const metadata = { title: "Brain Dump" };

export default async function BrainDumpPage() {
  const user = await requireUser("/brain-dump");
  const [notes, snapshots, mistakes] = await Promise.all([
    backendOrNull<Note[]>("/notes", { userId: user.id }),
    backendOrNull<Snapshot[]>("/snapshots", { userId: user.id }),
    backendOrNull<Mistake[]>("/mistakes", { userId: user.id }),
  ]);
  return (
    <div className="space-y-8">
      <div className="relative flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-end gap-4">
          <NotebookSticker className="hidden size-16 -rotate-6 sm:block" />
          <SectionTitle as="h1" kicker="Tor nijer study desk" title="Brain Dump" />
        </div>
        <div className="flex items-center gap-3">
          <PencilSticker className="hidden size-12 rotate-12 md:block" />
          <CandyLink href="/brain-dump/crunch" tone="mango">
            Crunch it ✨
          </CandyLink>
        </div>
      </div>
      {notes && snapshots && mistakes ? (
        <BrainDumpBoard initialNotes={notes} initialSnapshots={snapshots} mistakes={mistakes} />
      ) : (
        <EmptyState title="Desk load hocchhe na" mood="oops">
          The API isn&apos;t reachable right now. Your notes are safe on the server.
        </EmptyState>
      )}
    </div>
  );
}
