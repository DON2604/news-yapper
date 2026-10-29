import { NextResponse } from "next/server";
import type { SiteHealth } from "@/lib/health";
import { API_BASE_URL } from "@/lib/server/api";

export const dynamic = "force-dynamic";

type UpstreamHealth = {
  status?: unknown;
  database?: unknown;
  version?: unknown;
};

const NO_STORE = { "cache-control": "no-store" };

function classify(body: UpstreamHealth | null): SiteHealth {
  const database = body?.database === "ok" || body?.database === "unreachable" ? body.database : "unknown";
  const version = typeof body?.version === "string" ? body.version : null;
  if (body?.status === "ok") return { backend: "up", database, version };
  if (body?.status === "degraded") return { backend: "degraded", database, version };
  return { backend: "down", database, version };
}

/** Same-origin probe of FastAPI GET /health. The browser never calls the API host directly. */
export async function GET() {
  try {
    const upstream = await fetch(`${API_BASE_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    const body = (await upstream.json().catch(() => null)) as UpstreamHealth | null;
    if (!upstream.ok) {
      return NextResponse.json(
        { backend: "down", database: "unknown", version: null } satisfies SiteHealth,
        { status: 503, headers: NO_STORE },
      );
    }
    const health = classify(body);
    return NextResponse.json(health, {
      status: health.backend === "down" ? 503 : 200,
      headers: NO_STORE,
    });
  } catch {
    return NextResponse.json(
      { backend: "down", database: "unknown", version: null } satisfies SiteHealth,
      { status: 503, headers: NO_STORE },
    );
  }
}
