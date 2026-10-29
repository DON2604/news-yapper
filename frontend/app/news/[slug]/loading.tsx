import { Skeleton } from "@/components/design-system/EmptyState";

export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl space-y-6" aria-busy="true" aria-label="Loading story">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-56" />
      <div className="grid gap-5 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
          <Skeleton className="h-32" />
          <Skeleton className="h-48" />
        </div>
        <Skeleton className="h-72 lg:col-span-4" />
      </div>
    </div>
  );
}
