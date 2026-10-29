import fs from "node:fs";
import path from "node:path";

// The repository keeps a single .env at its root for the API, the worker and this
// app. Next.js only reads env files from frontend/ (and caches that first read), so
// the root file is merged here. Variables that are already set always win.
function loadRootEnv(): void {
  const candidates = [path.resolve(process.cwd(), "../.env"), path.resolve(process.cwd(), ".env")];
  const file = candidates.find((f) => fs.existsSync(f));
  if (!file) return;
  for (const raw of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq < 1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) process.env[key] = value;
  }
}

loadRootEnv();
