import { AdminPanel } from "@/components/admin/AdminPanel";
import { EmptyState } from "@/components/design-system/EmptyState";
import { SectionTitle } from "@/components/design-system/SectionTitle";
import { Stamp } from "@/components/design-system/stickers";
import type { Me } from "@/lib/api-types";
import { backendOrNull } from "@/lib/server/api";
import { requireUser } from "@/lib/server/session";

export const metadata = { title: "Admin desk" };

export default async function AdminPage() {
  const user = await requireUser("/admin");
  const me = await backendOrNull<Me>("/me", { userId: user.id });
  if (!me?.is_admin) {
    return (
      <EmptyState title="Admin only 🔒" mood="oops" className="mx-auto mt-10 max-w-xl">
        This desk is for editors. Admin rights are checked on the server for every request.
      </EmptyState>
    );
  }
  const [overview, queue, jobs] = await Promise.all([
    backendOrNull<Record<string, unknown>>("/admin/overview", { userId: user.id }),
    backendOrNull<Record<string, unknown>[]>("/admin/review-queue", { userId: user.id }),
    backendOrNull<Record<string, unknown>[]>("/admin/jobs", { userId: user.id }),
  ]);
  return (
    <div className="space-y-8">
      <div className="relative flex items-end justify-between gap-4">
        <SectionTitle as="h1" kicker="Ingestion · approvals · quota" title="Admin desk" />
        <Stamp label="EDITOR" className="hidden size-24 -rotate-12 sm:block" />
      </div>
      {overview && queue && jobs ? (
        <AdminPanel overview={overview} queue={queue} jobs={jobs} />
      ) : (
        <EmptyState title="Admin data load hocchhe na" mood="oops">
          The API isn&apos;t reachable right now.
        </EmptyState>
      )}
    </div>
  );
}
