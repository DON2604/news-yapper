"use client";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public payload: unknown = null,
  ) {
    super(message);
  }
}

/** Browser -> same-origin BFF proxy (/api/backend/*) -> FastAPI. */
export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const res = await fetch(`/api/backend/${path.replace(/^\//, "")}`, {
    method: init.method ?? "GET",
    headers: init.body !== undefined ? { "content-type": "application/json" } : undefined,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    const detail = payload && typeof payload.detail === "string" ? payload.detail : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail, payload);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
