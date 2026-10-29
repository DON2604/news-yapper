"use client";

import { Archive, LayoutGrid, List, Pencil, Pin, PinOff, Plus, Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { type KeyboardEvent, type PointerEvent, useMemo, useRef, useState } from "react";
import { CandyButton, candyClasses } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";
import { StickyNote } from "@/components/design-system/StickyNote";
import { ArrowDoodle, PencilSticker } from "@/components/design-system/stickers";
import { ArticleSnapshotCard } from "@/components/news/ArticleSnapshotCard";
import { NoteComposer } from "@/components/notes/NoteComposer";
import { WrongAnswerCard } from "@/components/quiz/WrongAnswerCard";
import type { Mistake, Note, Snapshot } from "@/lib/api-types";
import { api } from "@/lib/client-api";
import { cn } from "@/lib/cn";
import { formatDate } from "@/lib/format";

type Filter = "all" | "notes" | "snapshots" | "mistakes";
type Kind = "notes" | "snapshots" | "mistakes";
const NOTE_W = 240;
const NOTE_H = 230;
const GRID_GAP = 28;
const SWATCH: Record<Note["color"], string> = {
  mango: "bg-mango",
  lavender: "bg-lavender",
  mint: "bg-mint",
  pink: "bg-pink",
};

function SelectBox({ checked, onToggle, label }: { checked: boolean; onToggle: () => void; label: string }) {
  return (
    <label className="inline-flex min-h-8 cursor-pointer items-center gap-1 rounded-lg border-2 border-ink bg-paper px-1.5 text-xs font-bold">
      <input
        type="checkbox"
        className="size-4 accent-[#F05A28]"
        checked={checked}
        onChange={onToggle}
        aria-label={`Select "${label}" for Crunch`}
      />
      Crunch
    </label>
  );
}

function autoPlace(notes: Note[], cols: number): Note[] {
  let slot = 0;
  return notes.map((n) => {
    if (n.board_x !== 0 || n.board_y !== 0) return n;
    const x = GRID_GAP + (slot % cols) * (NOTE_W + GRID_GAP);
    const y = GRID_GAP + Math.floor(slot / cols) * (NOTE_H + GRID_GAP);
    slot += 1;
    return { ...n, board_x: x, board_y: y };
  });
}

export function BrainDumpBoard({
  initialNotes,
  initialSnapshots,
  mistakes,
}: {
  initialNotes: Note[];
  initialSnapshots: Snapshot[];
  mistakes: Mistake[];
}) {
  const [notes, setNotes] = useState<Note[]>(() => autoPlace(initialNotes, 4));
  const [snapshots, setSnapshots] = useState(initialSnapshots);
  const [view, setView] = useState<"board" | "list">("board");
  const [filter, setFilter] = useState<Filter>("all");
  const [tag, setTag] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<"updated" | "title" | "color">("updated");
  const [selected, setSelected] = useState<Record<Kind, string[]>>({ notes: [], snapshots: [], mistakes: [] });
  const [composer, setComposer] = useState<{ open: boolean; editing: Note | null }>({ open: false, editing: null });
  const [status, setStatus] = useState<string | null>(null);
  const drag = useRef<{ id: string; x: number; y: number; ox: number; oy: number } | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const nudgeTimer = useRef<number | null>(null);

  const tags = useMemo(() => Array.from(new Set(notes.flatMap((n) => n.tags))).sort(), [notes]);
  const visibleNotes = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = notes.filter(
      (n) =>
        (!tag || n.tags.includes(tag)) && (!q || n.title.toLowerCase().includes(q) || n.body.toLowerCase().includes(q)),
    );
    return [...list].sort((a, b) =>
      sort === "title"
        ? a.title.localeCompare(b.title)
        : sort === "color"
          ? a.color.localeCompare(b.color)
          : Number(b.pinned) - Number(a.pinned) || b.updated_at.localeCompare(a.updated_at),
    );
  }, [notes, tag, query, sort]);
  const canvasHeight = Math.max(420, ...notes.map((n) => n.board_y + NOTE_H + GRID_GAP * 2));
  const totalSelected = selected.notes.length + selected.snapshots.length + selected.mistakes.length;
  const show = (k: Kind) => filter === "all" || filter === k;

  function toggle(kind: Kind, id: string) {
    setSelected((s) => ({ ...s, [kind]: s[kind].includes(id) ? s[kind].filter((x) => x !== id) : [...s[kind], id] }));
  }

  const selectBox = (kind: Kind, id: string, label: string) => (
    <SelectBox checked={selected[kind].includes(id)} onToggle={() => toggle(kind, id)} label={label} />
  );

  async function patchNote(id: string, body: Partial<Note>, optimistic = true) {
    const before = notes;
    if (optimistic) setNotes((ns) => ns.map((n) => (n.id === id ? { ...n, ...body } : n)));
    try {
      const saved = await api<Note>(`notes/${id}`, { method: "PATCH", body });
      setNotes((ns) => ns.map((n) => (n.id === id ? { ...saved, board_x: saved.board_x || n.board_x, board_y: saved.board_y || n.board_y } : n)));
    } catch (err) {
      setNotes(before);
      setStatus(err instanceof Error ? `Save hoyni: ${err.message}` : "Save hoyni.");
    }
  }

  async function removeNote(note: Note) {
    if (!window.confirm(`Delete "${note.title || "this sticky"}"?`)) return;
    const before = notes;
    setNotes((ns) => ns.filter((n) => n.id !== note.id));
    try {
      await api(`notes/${note.id}`, { method: "DELETE" });
      setStatus("Sticky deleted.");
    } catch {
      setNotes(before);
      setStatus("Delete hoyni - abar try kor.");
    }
  }

  async function removeSnapshot(snap: Snapshot) {
    if (!window.confirm(`Remove your saved copy of "${snap.saved_title}"?`)) return;
    const before = snapshots;
    setSnapshots((ss) => ss.filter((s) => s.id !== snap.id));
    try {
      await api(`snapshots/${snap.id}`, { method: "DELETE" });
    } catch {
      setSnapshots(before);
      setStatus("Remove hoyni - abar try kor.");
    }
  }

  function onPointerDown(e: PointerEvent<HTMLDivElement>, note: Note) {
    if (e.button !== 0 || (e.target as HTMLElement).closest("button, input, a, label")) return;
    drag.current = { id: note.id, x: e.clientX, y: e.clientY, ox: note.board_x, oy: note.board_y };
    setDraggingId(note.id);
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    const d = drag.current;
    if (!d) return;
    const x = Math.max(0, Math.min(1400, d.ox + e.clientX - d.x));
    const y = Math.max(0, Math.min(4000, d.oy + e.clientY - d.y));
    setNotes((ns) => ns.map((n) => (n.id === d.id ? { ...n, board_x: x, board_y: y } : n)));
  }

  function onPointerUp() {
    const d = drag.current;
    drag.current = null;
    setDraggingId(null);
    if (!d) return;
    const note = notes.find((n) => n.id === d.id);
    if (note && (note.board_x !== d.ox || note.board_y !== d.oy)) {
      void patchNote(note.id, { board_x: Math.round(note.board_x), board_y: Math.round(note.board_y) }, false);
    }
  }

  function onNoteKey(e: KeyboardEvent<HTMLDivElement>, note: Note) {
    const step = e.shiftKey ? 64 : 16;
    const delta: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    if (e.key === "Enter") {
      setComposer({ open: true, editing: note });
      return;
    }
    const move = delta[e.key];
    if (!move) return;
    e.preventDefault();
    const x = Math.max(0, note.board_x + move[0]);
    const y = Math.max(0, note.board_y + move[1]);
    setNotes((ns) => ns.map((n) => (n.id === note.id ? { ...n, board_x: x, board_y: y } : n)));
    if (nudgeTimer.current) window.clearTimeout(nudgeTimer.current);
    nudgeTimer.current = window.setTimeout(() => void patchNote(note.id, { board_x: x, board_y: y }, false), 500);
  }

  const noteActions = (note: Note) => (
    <div className="mt-2 flex flex-wrap items-center gap-1 border-t-2 border-dashed border-ink/25 pt-2">
      {selectBox("notes", note.id, note.title || "sticky")}
      <span className="ml-auto flex gap-0.5">
        <button type="button" onClick={() => setComposer({ open: true, editing: note })} className="grid size-9 place-items-center rounded-lg hover:bg-paper/80" aria-label={`Edit ${note.title || "sticky"}`}>
          <Pencil className="size-4" aria-hidden="true" />
        </button>
        <button type="button" onClick={() => void patchNote(note.id, { pinned: !note.pinned })} className="grid size-9 place-items-center rounded-lg hover:bg-paper/80" aria-label={note.pinned ? "Unpin" : "Pin"}>
          {note.pinned ? <PinOff className="size-4" aria-hidden="true" /> : <Pin className="size-4" aria-hidden="true" />}
        </button>
        <button
          type="button"
          onClick={() => {
            setNotes((ns) => ns.filter((n) => n.id !== note.id));
            void patchNote(note.id, { archived: true }, false);
            setStatus("Archived. (Find it later via the API's archived filter.)");
          }}
          className="grid size-9 place-items-center rounded-lg hover:bg-paper/80"
          aria-label={`Archive ${note.title || "sticky"}`}
        >
          <Archive className="size-4" aria-hidden="true" />
        </button>
        <button type="button" onClick={() => void removeNote(note)} className="grid size-9 place-items-center rounded-lg hover:bg-paper/80" aria-label={`Delete ${note.title || "sticky"}`}>
          <Trash2 className="size-4" aria-hidden="true" />
        </button>
      </span>
    </div>
  );

  const crunchHref = `/brain-dump/crunch?${new URLSearchParams({
    ...(selected.notes.length ? { notes: selected.notes.join(",") } : {}),
    ...(selected.snapshots.length ? { snapshots: selected.snapshots.join(",") } : {}),
    ...(selected.mistakes.length ? { mistakes: selected.mistakes.join(",") } : {}),
  })}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <div role="tablist" aria-label="View" className="inline-flex rounded-2xl border-2 border-ink bg-paper p-1 shadow-brutal-sm">
          {(["board", "list"] as const).map((v) => (
            <button
              key={v}
              role="tab"
              type="button"
              aria-selected={view === v}
              onClick={() => setView(v)}
              className={cn("inline-flex min-h-10 items-center gap-1.5 rounded-xl px-3 font-display font-bold", view === v && "bg-mango")}
            >
              {v === "board" ? <LayoutGrid className="size-4" aria-hidden="true" /> : <List className="size-4" aria-hidden="true" />}
              {v === "board" ? "Desk" : "List"}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Show">
          {(
            [
              ["all", "Everything"],
              ["notes", `Stickies (${notes.length})`],
              ["snapshots", `Saved (${snapshots.length})`],
              ["mistakes", `Mistakes (${mistakes.length})`],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
              className={cn(
                "min-h-10 rounded-full border-2 border-ink px-3 text-sm font-bold",
                filter === value ? "bg-ink text-cream" : "bg-paper hover:bg-cream-deep",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <CandyButton tone="lavender" size="sm" className="ml-auto" onClick={() => setComposer({ open: true, editing: null })}>
          <Plus className="size-4" aria-hidden="true" /> New sticky
        </CandyButton>
      </div>

      {show("notes") ? (
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative flex items-center">
            <span className="sr-only">Search stickies</span>
            <Search className="pointer-events-none absolute left-3 size-4 text-ink-soft" aria-hidden="true" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search stickies"
              className="min-h-10 rounded-xl border-2 border-ink bg-paper pr-3 pl-9 text-sm"
            />
          </label>
          {tags.map((t) => (
            <button
              key={t}
              type="button"
              aria-pressed={tag === t}
              onClick={() => setTag(tag === t ? null : t)}
              className={cn("min-h-10 rounded-lg border-2 border-ink px-2.5 text-sm font-semibold", tag === t ? "bg-mango" : "bg-paper")}
            >
              #{t}
            </button>
          ))}
          {view === "list" ? (
            <label className="ml-auto flex items-center gap-2 text-sm font-semibold">
              Sort
              <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} className="min-h-10 rounded-xl border-2 border-ink bg-paper px-2">
                <option value="updated">Recently updated</option>
                <option value="title">Title</option>
                <option value="color">Colour</option>
              </select>
            </label>
          ) : null}
        </div>
      ) : null}

      <p aria-live="polite" className="min-h-5 text-sm font-semibold text-lavender-deep">
        {status}
      </p>

      {view === "board" ? (
        <div className="space-y-10">
          {show("notes") ? (
            <section aria-labelledby="desk-heading">
              <h2 id="desk-heading" className="sr-only">
                Sticky notes desk
              </h2>
              {visibleNotes.length === 0 ? (
                <EmptyState
                  title={notes.length ? "Kono sticky match korlo na" : "Desk ta ekdom faka!"}
                  mood={notes.length ? "think" : "sleepy"}
                  action={
                    <CandyButton tone="mango" onClick={() => setComposer({ open: true, editing: null })}>
                      Write your first sticky
                    </CandyButton>
                  }
                >
                  Dump facts, tricks and doubts here. Pin articles from any story, and wrong quiz answers land here
                  automatically.
                </EmptyState>
              ) : (
                <>
                  <div className="grid gap-6 sm:grid-cols-2 md:hidden">
                    {visibleNotes.map((note) => (
                      <StickyNote key={note.id} {...note} footer={noteActions(note)} />
                    ))}
                  </div>
                  <div
                    className="relative hidden overflow-x-auto rounded-[24px] border-2 border-ink bg-cream-deep shadow-brutal dot-grid md:block"
                    style={{ height: canvasHeight }}
                    onPointerMove={onPointerMove}
                    onPointerUp={onPointerUp}
                    onPointerCancel={onPointerUp}
                  >
                    <p id="drag-help" className="absolute top-3 right-4 rounded-full border-2 border-ink bg-paper px-3 py-1 text-xs font-semibold">
                      Drag stickies around · or focus one and use arrow keys · Enter to edit
                    </p>
                    <div aria-hidden="true" className="pointer-events-none absolute right-6 bottom-5 flex items-end gap-2">
                      <span className="mb-8 font-display text-sm font-bold text-ink-soft">drag me around!</span>
                      <ArrowDoodle className="mb-4 w-20 -scale-x-100 rotate-12" />
                      <PencilSticker className="size-14 rotate-12" />
                    </div>
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute bottom-6 left-6 -rotate-3 border border-ink/25 bg-mango/80 px-3 py-1 font-display text-sm font-bold shadow-sm"
                    >
                      Brain Dump desk · {notes.length} {notes.length === 1 ? "sticky" : "stickies"}
                    </span>
                    {visibleNotes.map((note) => (
                      <div
                        key={note.id}
                        tabIndex={0}
                        role="group"
                        aria-label={`Sticky: ${note.title || note.body.slice(0, 40)}`}
                        aria-describedby="drag-help"
                        onPointerDown={(e) => onPointerDown(e, note)}
                        onKeyDown={(e) => onNoteKey(e, note)}
                        className="absolute w-60 cursor-grab touch-none rounded-[8px] active:cursor-grabbing"
                        style={{ left: note.board_x, top: note.board_y, zIndex: draggingId === note.id ? 20 : note.pinned ? 10 : 1 }}
                      >
                        <StickyNote {...note} footer={noteActions(note)} selected={selected.notes.includes(note.id)} />
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>
          ) : null}

          {show("snapshots") ? (
            <section aria-labelledby="saved-heading" className="space-y-5">
              <h2 id="saved-heading" className="font-display text-2xl font-bold">
                Pinned articles 📌
              </h2>
              {snapshots.length === 0 ? (
                <p className="rounded-2xl border-2 border-dashed border-ink p-5 text-ink-soft">
                  Nothing pinned yet. Open any story and tap <strong>Pin to Brain Dump</strong> -{" "}
                  <Link href="/news" className="font-semibold text-punch-deep underline">
                    browse the feed
                  </Link>
                  .
                </p>
              ) : (
                <div className="grid gap-7 pt-3 sm:grid-cols-2 lg:grid-cols-3">
                  {snapshots.map((s) => (
                    <ArticleSnapshotCard
                      key={s.id}
                      snapshot={s}
                      onRemove={() => void removeSnapshot(s)}
                      selectControl={selectBox("snapshots", s.id, s.saved_title)}
                    />
                  ))}
                </div>
              )}
            </section>
          ) : null}

          {show("mistakes") ? (
            <section aria-labelledby="mistakes-heading" className="space-y-5">
              <h2 id="mistakes-heading" className="font-display text-2xl font-bold">
                Mistake Vault 😭
              </h2>
              {mistakes.length === 0 ? (
                <p className="rounded-2xl border-2 border-dashed border-ink p-5 text-ink-soft">
                  No active mistakes. Wrong quiz answers show up here automatically.
                </p>
              ) : (
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {mistakes.map((m) => (
                    <WrongAnswerCard key={m.id} mistake={m} compact selectControl={selectBox("mistakes", m.id, m.prompt)} />
                  ))}
                </div>
              )}
            </section>
          ) : null}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-[20px] border-2 border-ink bg-paper shadow-brutal">
          <table className="w-full min-w-[640px] text-left text-sm">
            <caption className="sr-only">Brain Dump items</caption>
            <thead className="border-b-2 border-ink bg-cream-deep font-display">
              <tr>
                <th scope="col" className="p-3">Crunch</th>
                <th scope="col" className="p-3">Item</th>
                <th scope="col" className="p-3">Type</th>
                <th scope="col" className="p-3">Updated</th>
                <th scope="col" className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {show("notes") &&
                visibleNotes.map((n) => (
                  <tr key={n.id} className="border-b border-ink/15 align-top">
                    <td className="p-3">
                      <input type="checkbox" className="size-5 accent-[#F05A28]" checked={selected.notes.includes(n.id)} onChange={() => toggle("notes", n.id)} aria-label={`Select "${n.title || "sticky"}" for Crunch`} />
                    </td>
                    <td className="max-w-md p-3">
                      <p className="font-semibold">{n.title || "Untitled sticky"}</p>
                      <p className="line-clamp-2 text-ink-soft">{n.body}</p>
                      {n.tags.length ? <p className="mt-1 text-xs font-semibold">{n.tags.map((t) => `#${t}`).join(" ")}</p> : null}
                    </td>
                    <td className="p-3">
                      <span className={cn("rounded-md border border-ink px-1.5 py-0.5 text-xs font-bold", SWATCH[n.color])}>Sticky · {n.color}</span>
                    </td>
                    <td className="p-3 whitespace-nowrap">{formatDate(n.updated_at)}</td>
                    <td className="p-3">
                      <div className="flex gap-1">
                        <button type="button" onClick={() => setComposer({ open: true, editing: n })} className="grid size-9 place-items-center rounded-lg hover:bg-mango" aria-label={`Edit ${n.title || "sticky"}`}>
                          <Pencil className="size-4" aria-hidden="true" />
                        </button>
                        <button type="button" onClick={() => void removeNote(n)} className="grid size-9 place-items-center rounded-lg hover:bg-pink" aria-label={`Delete ${n.title || "sticky"}`}>
                          <Trash2 className="size-4" aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              {show("snapshots") &&
                snapshots.map((s) => (
                  <tr key={s.id} className="border-b border-ink/15 align-top">
                    <td className="p-3">
                      <input type="checkbox" className="size-5 accent-[#F05A28]" checked={selected.snapshots.includes(s.id)} onChange={() => toggle("snapshots", s.id)} aria-label={`Select "${s.saved_title}" for Crunch`} />
                    </td>
                    <td className="max-w-md p-3 font-semibold">{s.saved_title}</td>
                    <td className="p-3">Saved article</td>
                    <td className="p-3 whitespace-nowrap">{formatDate(s.saved_at)}</td>
                    <td className="p-3">
                      <button type="button" onClick={() => void removeSnapshot(s)} className="grid size-9 place-items-center rounded-lg hover:bg-pink" aria-label={`Remove ${s.saved_title}`}>
                        <Trash2 className="size-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              {show("mistakes") &&
                mistakes.map((m) => (
                  <tr key={m.id} className="border-b border-ink/15 align-top">
                    <td className="p-3">
                      <input type="checkbox" className="size-5 accent-[#F05A28]" checked={selected.mistakes.includes(m.id)} onChange={() => toggle("mistakes", m.id)} aria-label={`Select mistake "${m.prompt}" for Crunch`} />
                    </td>
                    <td className="max-w-md p-3 font-semibold">{m.prompt}</td>
                    <td className="p-3">Mistake ×{m.error_count}</td>
                    <td className="p-3 whitespace-nowrap">{formatDate(m.last_wrong_at)}</td>
                    <td className="p-3">
                      <Link href="/revision" className="font-semibold text-punch-deep underline">
                        Review
                      </Link>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {totalSelected ? (
        <div className="sticky bottom-24 z-30 flex justify-center lg:bottom-6">
          <div className="flex animate-pop items-center gap-3 rounded-full border-2 border-ink bg-ink px-3 py-2 text-cream shadow-brutal">
            <span className="pl-2 font-semibold">{totalSelected} selected</span>
            <Link href={crunchHref} className={candyClasses("mango", "sm")}>
              Crunch it ✨
            </Link>
            <button type="button" onClick={() => setSelected({ notes: [], snapshots: [], mistakes: [] })} className="min-h-11 rounded-full px-3 text-sm font-semibold underline on-dark">
              Clear
            </button>
          </div>
        </div>
      ) : null}

      <NoteComposer
        open={composer.open}
        editing={composer.editing}
        onClose={() => setComposer({ open: false, editing: null })}
        onSaved={(note) => {
          setNotes((ns) => {
            const exists = ns.some((n) => n.id === note.id);
            return exists ? ns.map((n) => (n.id === note.id ? { ...note } : n)) : autoPlace([note, ...ns], 4);
          });
          setStatus(composer.editing ? "Sticky updated ✓" : "Sticky saved ✓");
        }}
      />
    </div>
  );
}
