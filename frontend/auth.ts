import "@/lib/server/env";
import NextAuth, { type NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import GitHub from "next-auth/providers/github";
import Google from "next-auth/providers/google";
import { loginWithPassword, syncUser } from "@/lib/server/api";

export const demoMode = (process.env.DEMO_MODE ?? "true").toLowerCase() === "true";

export const oauthProviders: { id: string; name: string }[] = [];
const providers: NextAuthConfig["providers"] = [];
if (process.env.AUTH_GITHUB_ID && process.env.AUTH_GITHUB_SECRET) {
  providers.push(GitHub);
  oauthProviders.push({ id: "github", name: "GitHub" });
}
if (process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET) {
  providers.push(Google);
  oauthProviders.push({ id: "google", name: "Google" });
}
providers.push(
  Credentials({
    id: "password",
    name: "Email",
    credentials: {
      email: { label: "Email", type: "email" },
      password: { label: "Password", type: "password" },
    },
    async authorize(credentials) {
      const email = String(credentials?.email ?? "").trim().toLowerCase();
      const password = String(credentials?.password ?? "");
      if (!email || !password) return null;
      const account = await loginWithPassword(email, password);
      if (!account) return null;
      return { id: account.auth_provider_id, email: account.email, name: account.display_name };
    },
  }),
);
if (demoMode) {
  providers.push(
    Credentials({
      id: "demo",
      name: "Demo login",
      credentials: { name: { label: "Your name", type: "text" } },
      async authorize(credentials) {
        const name = String(credentials?.name ?? "").trim().slice(0, 40);
        if (name.length < 2) return null;
        const handle = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "guest";
        return { id: `demo:${handle}`, name };
      },
    }),
  );
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers,
  session: { strategy: "jwt", maxAge: 60 * 60 * 24 * 14 },
  pages: { signIn: "/signin" },
  trustHost: process.env.AUTH_TRUST_HOST === "true" || process.env.NODE_ENV !== "production",
  callbacks: {
    async jwt({ token, user, account }) {
      if (user && account) {
        const providerId =
          account.provider === "demo" || account.provider === "password"
            ? String(user.id)
            : `${account.provider}:${account.providerAccountId}`;
        const synced = await syncUser({
          auth_provider_id: providerId,
          email: user.email ?? null,
          display_name: user.name ?? null,
        });
        token.uid = synced.user_id;
        token.isAdmin = synced.is_admin;
        token.onboarded = synced.onboarded;
        token.name = synced.display_name;
      }
      return token;
    },
    async session({ session, token }) {
      if (typeof token.uid === "string") {
        session.user.id = token.uid;
        // UI hint only - FastAPI re-checks admin rights in the database on every request.
        session.user.isAdmin = Boolean(token.isAdmin);
        session.user.onboarded = Boolean(token.onboarded);
      }
      return session;
    },
  },
});
