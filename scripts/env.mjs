import fs from 'node:fs';

/** Minimal .env reader (KEY=VALUE, # comments). Does not touch process.env. */
export function readEnvFile(file) {
  const out = {};
  if (!fs.existsSync(file)) return out;
  for (const raw of fs.readFileSync(file, 'utf8').split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

/** process.env wins over the file, mirroring pydantic-settings and Next.js. */
export function loadEnv(file) {
  const fromFile = readEnvFile(file);
  const merged = { ...fromFile };
  for (const key of Object.keys(fromFile)) {
    if (process.env[key] !== undefined && process.env[key] !== '') merged[key] = process.env[key];
  }
  return merged;
}
