import { signOut } from "@/auth";
import { EmptyState } from "@/components/design-system/EmptyState";
import { SectionTitle } from "@/components/design-system/SectionTitle";
import { BulbSticker } from "@/components/design-system/stickers";
import { PreferencesForm } from "@/components/settings/PreferencesForm";
import type { Me } from "@/lib/api-types";
import { backendOrNull } from "@/lib/server/api";
import { requireUser } from "@/lib/server/session";

export const metadata = { title: "Settings" };

export default async function SettingsPage() {
  const user = await requireUser("/settings");
  const me = await backendOrNull<Me>("/me", { userId: user.id });
  async function logout() {
    "use server";
    await signOut({ redirectTo: "/" });
  }
  if (!me) {
    return (
      <EmptyState title="Settings load hocchhe na" mood="oops">
        The API isn&apos;t reachable right now.
      </EmptyState>
    );
  }
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-end gap-4">
        <BulbSticker className="hidden size-16 -rotate-6 sm:block" />
        <SectionTitle as="h1" kicker={`Logged in as ${me.display_name}`} title="Settings & privacy" />
      </div>
      <PreferencesForm initial={me.preferences} disclosure={me.crunch_ai} displayName={me.display_name} logoutAction={logout} />
    </div>
  );
}
