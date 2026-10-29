"use client";

import { Send } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { CandyButton, candyClasses } from "@/components/design-system/CandyButton";
import type { ChatThread } from "@/lib/api-types";
import { ApiError, api } from "@/lib/client-api";
import { cn } from "@/lib/cn";

export function ArticleChat({
  slug,
  signedIn,
  initial,
}: {
  slug: string;
  signedIn: boolean;
  initial: ChatThread | null;
}) {
  const [thread, setThread] = useState<ChatThread | null>(initial);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [waited, setWaited] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const pending = Boolean(thread?.pending);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [thread?.messages.length, pending]);

  useEffect(() => {
    if (!pending) return;
    let tries = 0;
    const timer = window.setInterval(() => {
      tries += 1;
      if (tries > 24) {
        setWaited(true);
        window.clearInterval(timer);
        return;
      }
      api<ChatThread>(`news/${encodeURIComponent(slug)}/chat`)
        .then((next) => {
          setThread(next);
          if (!next.pending) window.clearInterval(timer);
        })
        .catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [pending, slug]);

  if (!signedIn) {
    return (
      <Link href={`/signin?callbackUrl=/news/${slug}`} className={candyClasses("lavender", "md")}>
        Login kore aro jiggesh kor
      </Link>
    );
  }

  const available = thread?.available !== false;
  const serious = Boolean(thread?.serious);

  async function send(event: FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (message.length < 2 || sending || pending) return;
    setSending(true);
    setError(null);
    setWaited(false);
    try {
      const next = await api<ChatThread>(`news/${encodeURIComponent(slug)}/chat`, {
        method: "POST",
        body: { message },
      });
      setThread(next);
      setDraft("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chat ta pathano jacche na.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section aria-labelledby="story-chat" className="rounded-[20px] border-2 border-ink bg-lavender p-5 shadow-brutal">
      <h2 id="story-chat" className="font-display text-2xl font-bold">
        Aro jante chas? ☕
      </h2>
      <p className="mt-1 text-sm font-medium text-ink-soft">
        {serious
          ? "Replies stay calm and respectful, and they stick to this saved story."
          : "Banglish replies come from this saved story. The same question is answered from the database next time."}
      </p>
      {!available ? (
        <p className="mt-3 rounded-2xl border-2 border-ink bg-paper p-3 font-semibold">
          Chat opens after this story has a saved summary.
        </p>
      ) : (
        <>
          <div
            ref={scroller}
            className="mt-4 max-h-80 space-y-3 overflow-y-auto rounded-2xl border-2 border-ink bg-cream p-3"
            aria-live="polite"
          >
            {thread?.messages.length ? (
              thread.messages.map((message) => (
                <p
                  key={message.id}
                  className={cn(
                    "max-w-[95%] rounded-2xl border-2 border-ink px-3 py-2 text-sm leading-relaxed",
                    message.role === "user" ? "ml-auto bg-mango" : "bg-paper",
                  )}
                >
                  <span className="mb-1 block font-display text-xs font-bold tracking-wide uppercase">
                    {message.role === "user" ? "Tui" : message.cached ? "Saved reply" : "Scene"}
                  </span>
                  {message.status === "pending"
                    ? "Bhabchi... saved story-r upor theke bolchi."
                    : message.body}
                </p>
              ))
            ) : (
              <p className="text-sm font-medium text-ink-soft">
                Jiggesh kor: exam-e ki mone rakhbi, ba eta keno matter kore.
              </p>
            )}
          </div>
          {waited && pending ? (
            <p className="mt-2 text-sm font-semibold">
              Reply ta queue-te ache. Worker save korle ekhane chole ashbe — page refresh korleo pabi.
            </p>
          ) : null}
          <form onSubmit={send} className="mt-3 flex flex-col gap-2 sm:flex-row">
            <label className="flex-1">
              <span className="sr-only">Your question</span>
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                maxLength={500}
                placeholder={serious ? "Ki ghotlo, short-e bol" : "Bhai, exam angle ta ektu bol to"}
                className="min-h-11 w-full rounded-xl border-2 border-ink bg-paper px-3"
              />
            </label>
            <CandyButton
              type="submit"
              tone="ink"
              size="sm"
              disabled={pending || draft.trim().length < 2}
              loading={sending}
              loadingText="Pathachhi..."
            >
              <Send className="size-4" aria-hidden="true" />
              Jiggesh kor
            </CandyButton>
          </form>
          {error ? (
            <p role="alert" className="mt-2 text-sm font-semibold text-pink-deep">
              {error}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
