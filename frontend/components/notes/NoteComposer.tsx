"use client";

import { X } from "lucide-react";
import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { CandyButton } from "@/components/design-system/CandyButton";
import type { Note, NoteColor } from "@/lib/api-types";
import { ApiError, api } from "@/lib/client-api";
import { cn } from "@/lib/cn";

const COLORS: { value: NoteColor; label: string; cls: string }[] = [
  { value: "mango", label: "Mango", cls: "bg-mango" },
  { value: "lavender", label: "Lavender", cls: "bg-lavender" },
  { value: "mint", label: "Mint", cls: "bg-mint" },
  { value: "pink", label: "Pink", cls: "bg-pink" },
];

const DRAFT_KEY = "aks:sticky-draft";
const EMPTY: NoteDraft = { title: "", body: "", color: "mango", tags: "" };

export interface NoteDraft {
  title: string;
  body: string;
  color: NoteColor;
  tags: string;
  snapshot_id?: string | null;
}

type Props = {
  open: boolean;
  onClose: () => void;
  onSaved?: (note: Note) => void;
  initial?: Partial<NoteDraft>;
  editing?: Note | null;
};

export function NoteComposer(props: Props) {
  // Mounted only while open, so every opening starts from fresh state.
  return props.open ? <ComposerDialog {...props} /> : null;
}

function initialDraft(editing?: Note | null, initial?: Partial<NoteDraft>): NoteDraft {
  if (editing) {
    return { title: editing.title, body: editing.body, color: editing.color, tags: editing.tags.join(", ") };
  }
  if (initial) return { ...EMPTY, ...initial };
  try {
    const stored = window.localStorage.getItem(DRAFT_KEY);
    return stored ? { ...EMPTY, ...(JSON.parse(stored) as NoteDraft) } : EMPTY;
  } catch {
    return EMPTY;
  }
}

function ComposerDialog({ onClose, onSaved, initial, editing }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [draft, setDraft] = useState<NoteDraft>(() => initialDraft(editing, initial));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  function update(patch: Partial<NoteDraft>) {
    setDraft((d) => {
      const next = { ...d, ...patch };
      if (!editing) window.localStorage.setItem(DRAFT_KEY, JSON.stringify(next));
      return next;
    });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!draft.title.trim() && !draft.body.trim()) {
      setError("Kichu ekta likh - title ba note.");
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      title: draft.title,
      body: draft.body,
      color: draft.color,
      tags: draft.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      ...(draft.snapshot_id ? { snapshot_id: draft.snapshot_id } : {}),
    };
    try {
      const note = editing
        ? await api<Note>(`notes/${editing.id}`, {
            method: "PATCH",
            body: { ...payload, expected_version: editing.revision_version },
          })
        : await api<Note>("notes", {
            method: "POST",
            body: { ...payload, board_x: Math.round(24 + Math.random() * 260), board_y: Math.round(24 + Math.random() * 140) },
          });
      if (!editing) window.localStorage.removeItem(DRAFT_KEY);
      onSaved?.(note);
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError("Login kore nao - tarpor sticky save hobe.");
      else if (err instanceof ApiError && err.status === 409)
        setError("Ei sticky onno device-e edit hoyeche. Refresh kore abar try kor.");
      else setError(err instanceof Error ? `${err.message}. Draft ta browser-e safe ache.` : "Save hoyni - draft safe ache.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      className="m-auto w-[min(92vw,34rem)] rounded-[22px] border-2 border-ink bg-cream p-0 text-ink shadow-brutal-lg backdrop:bg-ink/40 backdrop:backdrop-blur-sm"
    >
      <form onSubmit={submit} className="flex flex-col gap-4 p-5 sm:p-6">
        <div className="flex items-center justify-between">
          <h2 id={titleId} className="font-display text-2xl font-bold">
            {editing ? "Edit sticky" : "Notun sticky ✍️"}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="grid size-11 place-items-center rounded-xl hover:bg-pink"
            aria-label="Close"
          >
            <X className="size-5" aria-hidden="true" />
          </button>
        </div>
        <label className="flex flex-col gap-1 font-semibold">
          <span>
            Title <span className="text-sm font-normal text-ink-soft">(optional)</span>
          </span>
          <input
            value={draft.title}
            onChange={(e) => update({ title: e.target.value })}
            maxLength={200}
            className="min-h-11 rounded-xl border-2 border-ink bg-paper px-3 font-normal"
            placeholder="Article 32 trap"
          />
        </label>
        <label className="flex flex-col gap-1 font-semibold">
          Note
          <textarea
            value={draft.body}
            onChange={(e) => update({ body: e.target.value })}
            maxLength={5000}
            rows={6}
            className="lined-paper rounded-xl border-2 border-ink bg-paper px-3 py-2 leading-7 font-normal"
            placeholder={"Plain text. Start lines with - for bullets.\nTerm: definition lines become flashcards in Crunch."}
          />
        </label>
        <fieldset className="flex flex-col gap-2">
          <legend className="font-semibold">Colour</legend>
          <div className="flex gap-2">
            {COLORS.map((c) => (
              <label key={c.value} className="cursor-pointer">
                <input
                  type="radio"
                  name="note-color"
                  value={c.value}
                  checked={draft.color === c.value}
                  onChange={() => update({ color: c.value })}
                  className="peer sr-only"
                />
                <span
                  className={cn(
                    "grid size-11 place-items-center rounded-xl border-2 border-ink text-sm font-bold",
                    "peer-checked:shadow-brutal-sm peer-checked:ring-4 peer-checked:ring-ink/25",
                    "peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ink",
                    c.cls,
                  )}
                >
                  <span aria-hidden="true">{draft.color === c.value ? "✓" : ""}</span>
                  <span className="sr-only">{c.label}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <label className="flex flex-col gap-1 font-semibold">
          <span>
            Tags <span className="text-sm font-normal text-ink-soft">(comma separated)</span>
          </span>
          <input
            value={draft.tags}
            onChange={(e) => update({ tags: e.target.value })}
            className="min-h-11 rounded-xl border-2 border-ink bg-paper px-3 font-normal"
            placeholder="polity, writs"
          />
        </label>
        {error ? (
          <p role="alert" className="rounded-xl border-2 border-ink bg-pink px-3 py-2 text-sm font-semibold">
            {error}
          </p>
        ) : null}
        <div className="flex justify-end gap-2">
          <CandyButton tone="paper" onClick={onClose}>
            Cancel
          </CandyButton>
          <CandyButton type="submit" tone="punch" loading={saving} loadingText="Saving...">
            {editing ? "Save changes" : "Stick it!"}
          </CandyButton>
        </div>
      </form>
    </dialog>
  );
}
