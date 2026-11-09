import { AuthError } from "next-auth";
import { redirect } from "next/navigation";
import { auth, demoMode, oauthProviders, signIn } from "@/auth";
import { BackendError, registerAccount } from "@/lib/server/api";
import { SubmitButton } from "@/components/design-system/SubmitButton";
import { StickerBadge } from "@/components/design-system/StickerBadge";
import { ArrowDoodle, Mascot, SparkleSticker } from "@/components/design-system/stickers";
import { Tape } from "@/components/design-system/Tape";

export const metadata = { title: "Login" };

function safeRedirect(value: string | undefined): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; callbackUrl?: string }>;
}) {
  const params = await searchParams;
  const session = await auth();
  const next = safeRedirect(params.callbackUrl);
  if (session?.user) redirect(next);

  async function demoLogin(formData: FormData) {
    "use server";
    try {
      await signIn("demo", { name: String(formData.get("name") ?? ""), redirectTo: next });
    } catch (error) {
      if (error instanceof AuthError) redirect(`/signin?error=${error.type}&callbackUrl=${encodeURIComponent(next)}`);
      throw error;
    }
  }

  async function oauthLogin(formData: FormData) {
    "use server";
    await signIn(String(formData.get("provider")), { redirectTo: next });
  }

  async function passwordLogin(formData: FormData) {
    "use server";
    const email = String(formData.get("email") ?? "");
    const password = String(formData.get("password") ?? "");
    try {
      await signIn("password", { email, password, redirectTo: next });
    } catch (error) {
      if (error instanceof AuthError) redirect(`/signin?error=CredentialsSignin&callbackUrl=${encodeURIComponent(next)}`);
      throw error;
    }
  }

  async function passwordRegister(formData: FormData) {
    "use server";
    const email = String(formData.get("email") ?? "");
    const password = String(formData.get("password") ?? "");
    const displayName = String(formData.get("name") ?? "");
    try {
      await registerAccount({ email, password, display_name: displayName });
    } catch (error) {
      const message = error instanceof BackendError ? error.message : "Could not create the account.";
      redirect(`/signin?error=${encodeURIComponent(message)}&callbackUrl=${encodeURIComponent(next)}`);
    }
    try {
      await signIn("password", { email, password, redirectTo: next });
    } catch (error) {
      if (error instanceof AuthError) redirect(`/signin?error=CredentialsSignin&callbackUrl=${encodeURIComponent(next)}`);
      throw error;
    }
  }

  return (
    <div className="mx-auto grid max-w-5xl items-center gap-10 py-6 lg:grid-cols-2">
      <section className="relative space-y-5">
        <StickerBadge tone="mint" tilt={-3}>
          Free · no spam · no streak shaming
        </StickerBadge>
        <h1 className="font-display text-5xl leading-[1.02] font-bold tracking-tight sm:text-6xl">
          Login kor, <span className="marker">bhai.</span>
        </h1>
        <p className="max-w-md text-lg text-ink-soft">
          Personal daily quiz, Mistake Vault, Brain Dump stickies ar Crunch-ed revision cards - shob tor account-e safe.
        </p>
        <div className="relative hidden h-40 sm:block" aria-hidden="true">
          <Mascot mood="wow" className="absolute left-0 size-36 -rotate-6" />
          <ArrowDoodle className="absolute top-6 left-36 w-28" />
          <SparkleSticker className="absolute top-0 left-72 size-14" />
        </div>
      </section>

      <section className="relative rounded-[22px] border-2 border-ink bg-paper p-6 shadow-brutal-lg sm:p-8">
        <Tape tone="pink" className="-top-3 left-10 -rotate-6" />
        {params.error ? (
          <p role="alert" className="mb-4 rounded-xl border-2 border-ink bg-pink px-3 py-2 text-sm font-semibold">
            {params.error === "CredentialsSignin"
              ? "Email or password didn't match. Password needs at least 8 characters."
              : params.error === "Configuration"
                ? "Login hoyni. API cholchhe to? (npm run dev at the repo root)"
                : params.error}
          </p>
        ) : null}

        <form action={passwordLogin} className="space-y-4">
          <h2 className="font-display text-2xl font-bold">Login</h2>
          <p className="text-sm text-ink-soft">Email ar password. No extra verification step.</p>
          <label className="flex flex-col gap-1 font-semibold">
            Email
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              className="min-h-12 rounded-xl border-2 border-ink bg-cream px-3 text-lg font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 font-semibold">
            Password
            <input
              name="password"
              type="password"
              required
              minLength={8}
              autoComplete="current-password"
              className="min-h-12 rounded-xl border-2 border-ink bg-cream px-3 text-lg font-normal"
            />
          </label>
          <SubmitButton tone="punch" size="lg" className="w-full" loadingText="Login korchhi...">
            Login →
          </SubmitButton>
        </form>

        <form action={passwordRegister} className="mt-6 space-y-4 border-t-2 border-dashed border-ink/30 pt-6">
          <h2 className="font-display text-2xl font-bold">Notun account</h2>
          <label className="flex flex-col gap-1 font-semibold">
            Name
            <input
              name="name"
              required
              minLength={2}
              maxLength={40}
              autoComplete="nickname"
              placeholder="Rimi"
              className="min-h-12 rounded-xl border-2 border-ink bg-cream px-3 text-lg font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 font-semibold">
            Email
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              className="min-h-12 rounded-xl border-2 border-ink bg-cream px-3 text-lg font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 font-semibold">
            Password
            <input
              name="password"
              type="password"
              required
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              className="min-h-12 rounded-xl border-2 border-ink bg-cream px-3 text-lg font-normal"
            />
          </label>
          <SubmitButton tone="mint" size="lg" className="w-full" loadingText="Account banachhi...">
            Create account
          </SubmitButton>
        </form>

        {oauthProviders.length ? (
          <div className="space-y-3">
            {oauthProviders.map((p) => (
              <form key={p.id} action={oauthLogin}>
                <input type="hidden" name="provider" value={p.id} />
                <SubmitButton tone="paper" size="lg" className="w-full">
                  Continue with {p.name}
                </SubmitButton>
              </form>
            ))}
          </div>
        ) : null}

        {demoMode ? (
          <form action={demoLogin} className={oauthProviders.length ? "mt-6 border-t-2 border-dashed border-ink/30 pt-6" : ""}>
            <h2 className="font-display text-2xl font-bold">Demo login</h2>
            <p className="mt-1 text-sm text-ink-soft">
              DEMO_MODE only - no password. Same name = same account on this machine. Use the name{" "}
              <code className="rounded bg-cream-deep px-1">admin</code> to explore the admin desk.
            </p>
            <label className="mt-4 flex flex-col gap-1 font-semibold">
              Tor naam
              <input
                name="name"
                required
                minLength={2}
                maxLength={40}
                autoComplete="nickname"
                placeholder="Rimi"
                className="min-h-12 rounded-xl border-2 border-ink bg-cream px-3 text-lg font-normal"
              />
            </label>
            <SubmitButton tone="punch" size="lg" className="mt-4 w-full" loadingText="Dhukchhi...">
              Start studying →
            </SubmitButton>
          </form>
        ) : null}

      </section>
    </div>
  );
}
