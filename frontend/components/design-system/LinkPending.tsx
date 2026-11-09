"use client";

import { LoaderCircle } from "lucide-react";
import { useLinkStatus } from "next/link";
import { cn } from "@/lib/cn";

/** Corner spinner for a <Link> while its navigation is pending. Must render inside a Link with `relative`. */
export function LinkPending({ className }: { className?: string }) {
  const { pending } = useLinkStatus();
  return (
    <span
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute -top-2 -right-2 grid size-6 place-items-center rounded-full border-2 border-ink bg-paper text-ink",
        "opacity-0 transition-opacity delay-100 duration-150",
        pending && "opacity-100",
        className,
      )}
    >
      {pending ? <LoaderCircle className="size-3.5 animate-spin motion-reduce:animate-none" /> : null}
    </span>
  );
}
