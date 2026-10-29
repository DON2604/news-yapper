import { Mascot } from "@/components/design-system/stickers";

export function SiteFooter() {
  return (
    <footer className="border-t-2 border-ink bg-ink text-cream">
      <div className="mx-auto grid max-w-[1400px] gap-6 px-4 py-10 pb-32 sm:px-6 md:grid-cols-[auto_1fr] lg:pb-10">
        <Mascot mood="happy" className="size-16" steam={false} />
        <div className="space-y-3">
          <p className="font-display text-2xl font-bold">
            Duniya-r shob gossip, <span className="text-mango">exam-er shob preparation.</span>
          </p>
          <p className="max-w-3xl text-sm text-cream/80">
            Every story links to its original sources and shows when it was last updated. Relevance scores are
            heuristics for revision priority - never a prediction of exam questions. Items marked DEMO are evergreen
            sample explainers, not today&apos;s news. AI summaries appear only after automated source checks or editor
            review.
          </p>
        </div>
        <p className="border-t border-cream/20 pt-5 text-sm text-cream/85 md:col-span-2">
          Made with love by <span className="font-display font-bold text-mango">Mrinmay</span> 🥰
        </p>
      </div>
    </footer>
  );
}
