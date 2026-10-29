"use client";

import { CandyButton } from "@/components/design-system/CandyButton";
import { EmptyState } from "@/components/design-system/EmptyState";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <EmptyState
      title="Uff, kichu ekta gondogol holo"
      mood="oops"
      className="mx-auto mt-10 max-w-xl"
      action={
        <CandyButton tone="mango" onClick={reset}>
          Try again
        </CandyButton>
      }
    >
      <p>{error.message || "Something went wrong while loading this page."}</p>
      <p className="mt-2 text-sm">If the API is offline, start everything with <code>npm run dev</code> at the repo root.</p>
    </EmptyState>
  );
}
