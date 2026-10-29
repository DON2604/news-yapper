import { EmptyState } from "@/components/design-system/EmptyState";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { Mascot } from "@/components/design-system/stickers";
import { PreferencesForm } from "@/components/settings/PreferencesForm";
import type { Me } from "@/lib/api-types";
import { backendOrNull } from "@/lib/server/api";
import { requireUser } from "@/lib/server/session";

export const metadata = { title: "Set up your profile" };

export default async function OnboardingPage() {
  const user = await requireUser("/onboarding");
  const me = await backendOrNull<Me>("/me", { userId: user.id });
  if (!me) {
    return (
      <EmptyState title="Profile load hocchhe na" mood="oops">
        The API isn&apos;t reachable right now.
      </EmptyState>
    );
  }
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-center gap-4">
        <Mascot mood="wow" className="size-20 shrink-0" />
        <div>
          <StickerBadge tone="mint" tilt={-2}>
            1 minute setup
          </StickerBadge>
          <h1 className="mt-2 font-display text-4xl font-bold">Hi {me.display_name}! Kon exam-er prostuti?</h1>
        </div>
      </div>
      <PreferencesForm initial={me.preferences} disclosure={me.crunch_ai} displayName={me.display_name} mode="onboarding" />
    </div>
  );
}
