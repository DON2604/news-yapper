import { Skeleton } from "@/components/design-system/EmptyState";

export default function Loading() {
  return (
    <div className="grid gap-5 lg:grid-cols-12" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-80 lg:col-span-7" />
      <div className="grid gap-5 lg:col-span-5">
        <Skeleton className="h-36" />
        <Skeleton className="h-36" />
      </div>
      <Skeleton className="h-40 lg:col-span-4" />
      <Skeleton className="h-40 lg:col-span-4" />
      <Skeleton className="h-40 lg:col-span-4" />
    </div>
  );
}
