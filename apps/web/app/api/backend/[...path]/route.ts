import { type NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { API_BASE_URL } from "@/lib/server/api";
import { mintApiToken } from "@/lib/server/token";

// Only these API areas are reachable from the browser; internal routes (auth/sync) are not.
const ALLOWED = /^(news|editions|quizzes|notes|snapshots|mistakes|revision|flashcards|crunch|me|progress|collections|admin)(\/|$)/;
const FORWARDED_HEADERS = ["content-type", "retry-after", "location", "content-disposition"];

function sameOrigin(req: NextRequest): boolean {
  const origin = req.headers.get("origin");
  if (origin) {
    try {
      return new URL(origin).host === req.headers.get("host");
    } catch {
      return false;
    }
  }
  return req.headers.get("sec-fetch-site") === "same-origin";
}

async function proxy(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const joined = path.map(encodeURIComponent).join("/");
  if (!ALLOWED.test(joined)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  if (req.method !== "GET" && !sameOrigin(req)) {
    return NextResponse.json({ detail: "Cross-site request blocked" }, { status: 403 });
  }

  const session = await auth();
  const headers: Record<string, string> = { accept: "application/json" };
  if (session?.user?.id) headers.authorization = `Bearer ${await mintApiToken(session.user.id)}`;
  const hasBody = !["GET", "HEAD", "DELETE"].includes(req.method);
  if (hasBody) headers["content-type"] = "application/json";

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE_URL}/api/v1/${joined}${req.nextUrl.search}`, {
      method: req.method,
      headers,
      body: hasBody ? await req.text() : undefined,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "API unreachable - is the backend running?" }, { status: 503 });
  }
  const out = new Headers({ "cache-control": "no-store" });
  for (const name of FORWARDED_HEADERS) {
    const value = upstream.headers.get(name);
    if (value) out.set(name, value);
  }
  return new NextResponse(upstream.status === 204 ? null : upstream.body, { status: upstream.status, headers: out });
}

export { proxy as DELETE, proxy as GET, proxy as PATCH, proxy as POST, proxy as PUT };
