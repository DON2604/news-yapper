#!/usr/bin/env node
// Creates/updates .env from .env.example and generates local-only secrets.
// Existing non-empty values are never overwritten.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const envPath = path.join(root, '.env');
const examplePath = path.join(root, '.env.example');

if (!fs.existsSync(envPath)) {
  fs.copyFileSync(examplePath, envPath);
  console.log('Created .env from .env.example');
}

const lines = fs.readFileSync(envPath, 'utf8').split(/\r?\n/);
const current = Object.fromEntries(
  lines
    .filter((l) => l && !l.trim().startsWith('#') && l.includes('='))
    .map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()]),
);

const secret = (bytes = 32) => crypto.randomBytes(bytes).toString('base64url');
const pgPassword = current.LOCAL_PG_PASSWORD || secret(18);
const pgPort = current.LOCAL_PG_PORT || '54329';
const localUrl = (db) => `postgresql://postgres:${pgPassword}@127.0.0.1:${pgPort}/${db}`;

const fills = {
  AUTH_SECRET: secret(),
  API_JWT_SECRET: secret(),
  LOCAL_PG_PASSWORD: pgPassword,
  DATABASE_URL: localUrl('aajke'),
  DIRECT_URL: localUrl('aajke'),
  TEST_DATABASE_URL: localUrl('aajke_test'),
};

const changed = [];
const seen = new Set();
const output = lines.map((line) => {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) return line;
  const key = trimmed.slice(0, trimmed.indexOf('=')).trim();
  seen.add(key);
  const value = trimmed.slice(trimmed.indexOf('=') + 1).trim();
  if (value === '' && fills[key] !== undefined) {
    changed.push(key);
    return `${key}=${fills[key]}`;
  }
  return line;
});
for (const [key, value] of Object.entries(fills)) {
  if (!seen.has(key)) {
    output.push(`${key}=${value}`);
    changed.push(key);
  }
}

fs.writeFileSync(envPath, output.join('\n'));
console.log(changed.length ? `Filled: ${changed.join(', ')}` : '.env already complete; nothing changed.');
console.log('\nNext steps:\n  npm run db:start\n  npm run db:migrate\n  npm run db:seed\n  npm run dev');
