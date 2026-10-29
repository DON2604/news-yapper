export type SiteHealth = {
  backend: "up" | "degraded" | "down";
  database: "ok" | "unreachable" | "unknown";
  version: string | null;
};
