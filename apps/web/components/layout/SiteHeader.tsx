import { auth, signOut } from "@/auth";
import { CandyLink } from "@/components/design-system/CandyButton";
import { Wordmark } from "@/components/design-system/Wordmark";
import { DesktopNav } from "@/components/layout/NavLinks";
import { UserMenu } from "@/components/layout/UserMenu";

export async function SiteHeader() {
  const session = await auth();
  async function logout() {
    "use server";
    await signOut({ redirectTo: "/" });
  }
  return (
    <header className="sticky top-0 z-40 border-b-2 border-ink bg-cream/92 backdrop-blur supports-[backdrop-filter]:bg-cream/80">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-3 px-4 sm:h-[4.5rem] sm:px-6">
        <Wordmark />
        <DesktopNav />
        <div className="flex items-center gap-2">
          {session?.user ? (
            <UserMenu name={session.user.name ?? "Bondhu"} isAdmin={session.user.isAdmin} signOutAction={logout} />
          ) : (
            <CandyLink href="/signin" tone="ink" size="sm">
              Login
            </CandyLink>
          )}
        </div>
      </div>
    </header>
  );
}
