import { Search } from "lucide-react";
import Link from "next/link";
import { auth } from "@/auth";
import { candyClasses } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";
import { SectionTitle } from "@/components/design-system/SectionTitle";
import { NewspaperSticker } from "@/components/design-system/stickers";
import { TopicPill } from "@/components/design-system/TopicPill";
import { NewsCard } from "@/components/news/NewsCard";
import type { Category, NewsPage } from "@/lib/api-types";
import { CATEGORY_ORDER } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { EXAM_LABELS } from "@/lib/format";
import { backendOrNull } from "@/lib/server/api";

export const metadata = { title: "News feed" };

type Params = { q?: string; category?: string; exam?: string; importance?: string; region?: string; kind?: string; cursor?: string };
const FILTER_KEYS = ["q", "category", "exam", "importance", "region", "kind"] as const;

function hrefWith(params: Params, patch: Partial<Params>): string {
  const merged: Record<string, string> = {};
  for (const key of FILTER_KEYS) {
    const value = key in patch ? patch[key] : params[key];
    if (value) merged[key] = value;
  }
  if (patch.cursor) merged.cursor = patch.cursor;
  const qs = new URLSearchParams(merged).toString();
  return qs ? `/news?${qs}` : "/news";
}

const selectCls = "min-h-11 rounded-xl border-2 border-ink bg-paper px-3 font-semibold";

export default async function NewsFeedPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const session = await auth();
  const query = new URLSearchParams();
  for (const key of [...FILTER_KEYS, "cursor"] as const) {
    if (params[key]) query.set(key, params[key] as string);
  }
  query.set("limit", "18");
  const page = await backendOrNull<NewsPage>(`/news?${query}`, { userId: session?.user?.id ?? null });
  const activeCategory = CATEGORY_ORDER.includes(params.category as Category) ? (params.category as Category) : null;

  return (
    <div className="space-y-8">
      <div className="flex items-end gap-4">
        <NewspaperSticker className="hidden size-16 -rotate-6 sm:block" />
        <SectionTitle as="h1" kicker="Shob scene ek jaygay" title="The news feed" />
      </div>

      <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0">
        <Link
          href={hrefWith(params, { category: undefined })}
          aria-current={!activeCategory ? "page" : undefined}
          className={cn(
            "inline-flex min-h-11 shrink-0 items-center rounded-full border-2 border-ink px-4 font-display text-sm font-bold",
            !activeCategory ? "bg-ink text-cream shadow-brutal-sm" : "bg-paper",
          )}
        >
          All topics
        </Link>
        {CATEGORY_ORDER.map((c) => (
          <TopicPill key={c} category={c} href={hrefWith(params, { category: c })} active={activeCategory === c} />
        ))}
      </div>

      <form method="get" action="/news" className="grid gap-3 rounded-[20px] border-2 border-ink bg-cream-deep p-4 sm:grid-cols-2 lg:grid-cols-[2fr_repeat(4,1fr)_auto]">
        {activeCategory ? <input type="hidden" name="category" value={activeCategory} /> : null}
        <label className="relative flex items-center">
          <span className="sr-only">Search</span>
          <Search className="pointer-events-none absolute left-3 size-5 text-ink-soft" aria-hidden="true" />
          <input
            name="q"
            defaultValue={params.q ?? ""}
            placeholder="Search: RBI, ISRO, Article 32..."
            maxLength={80}
            className="min-h-11 w-full rounded-xl border-2 border-ink bg-paper pr-3 pl-10"
          />
        </label>
        <label>
          <span className="sr-only">Exam</span>
          <select name="exam" defaultValue={params.exam ?? ""} className={cn(selectCls, "w-full")}>
            <option value="">All exams</option>
            {Object.entries(EXAM_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Importance</span>
          <select name="importance" defaultValue={params.importance ?? ""} className={cn(selectCls, "w-full")}>
            <option value="">Any importance</option>
            <option value="high">High relevance</option>
            <option value="medium">Medium+</option>
          </select>
        </label>
        <label>
          <span className="sr-only">Region</span>
          <select name="region" defaultValue={params.region ?? ""} className={cn(selectCls, "w-full")}>
            <option value="">India + World</option>
            <option value="india">India</option>
            <option value="world">World</option>
          </select>
        </label>
        <label>
          <span className="sr-only">Type</span>
          <select name="kind" defaultValue={params.kind ?? "all"} className={cn(selectCls, "w-full")}>
            <option value="all">AI + source-only</option>
            <option value="ai">Source-checked AI</option>
            <option value="source">Source headlines</option>
          </select>
        </label>
        <button type="submit" className={candyClasses("punch", "sm")}>
          Filter
        </button>
      </form>

      {!page ? (
        <EmptyState title="Feed load hocchhe na" mood="oops">
          The API isn&apos;t reachable right now.
        </EmptyState>
      ) : page.items.length === 0 ? (
        <EmptyState
          title="Ei filter-e kichu nei"
          mood="think"
          action={
            <Link href="/news" className={candyClasses("mango", "md")}>
              Clear filters
            </Link>
          }
        >
          Try another topic or exam - or come back after the next ingestion run.
        </EmptyState>
      ) : (
        <>
          <p className="text-sm font-semibold text-ink-soft">
            {page.total} stor{page.total === 1 ? "y" : "ies"}
          </p>
          <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {page.items.map((item, i) => (
              <li key={item.event_id} className={cn(i === 0 && !params.cursor && "sm:col-span-2")}>
                <NewsCard item={item} variant={i === 0 && !params.cursor ? "feature" : "card"} />
              </li>
            ))}
          </ul>
          <div className="flex justify-center gap-3">
            {params.cursor ? (
              <Link href={hrefWith(params, {})} className={candyClasses("paper", "md")}>
                Back to first page
              </Link>
            ) : null}
            {page.next_cursor ? (
              <Link href={hrefWith(params, { cursor: page.next_cursor })} className={candyClasses("mango", "md")}>
                Aro dekhao →
              </Link>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}
