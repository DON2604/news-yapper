import "@/lib/server/env";
import { auth } from "@/auth";
import { mintApiToken } from "@/lib/server/token";

export const API_BASE_URL = (process.env.API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class BackendError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Init = { method?: string; body?: unknown; userId?: string | null };

/** Server-side call to FastAPI. Attaches a fresh user token when a session exists. */
export async function backend<T>(path: string, init: Init = {}): Promise<T> {
  let userId = init.userId;
  if (userId === undefined) {
    const session = await auth();
    userId = session?.user?.id ?? null;
  }
  const headers: Record<string, string> = { accept: "application/json" };
  if (userId) headers.authorization = `Bearer ${await mintApiToken(userId)}`;
  if (init.body !== undefined) headers["content-type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/v1${path}`, {
      method: init.method ?? "GET",
      headers,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new BackendError(503, "The API is not reachable. Start it with `npm run dev` at the repository root.");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new BackendError(res.status, typeof detail?.detail === "string" ? detail.detail : res.statusText);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

/** Like backend() but returns null instead of throwing - for optional page sections. */
export async function backendOrNull<T>(path: string, init: Init = {}): Promise<T | null> {
  try {
    return await backend<T>(path, init);
  } catch {
    return null;
  }
}

export async function syncUser(payload: {
  auth_provider_id: string;
  email: string | null;
  display_name: string | null;
}): Promise<{ user_id: string; display_name: string; is_admin: boolean; onboarded: boolean }> {
  const token = await mintApiToken("aks-web", "internal");
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/sync`, {
    method: "POST",
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    body: JSON.stringify(payload),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`User sync failed (${res.status})`);
  return res.json();
}
