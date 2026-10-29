#!/usr/bin/env node
// One-command local stack: local Postgres (if configured) -> migrations ->
// demo seed -> API + worker + web with prefixed logs. Ctrl+C stops everything.
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadEnv } from './env.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const env = loadEnv(path.join(root, '.env'));
const isWin = process.platform === 'win32';
const npm = isWin ? 'npm.cmd' : 'npm';

function step(label, cmd, args) {
  console.log(`\n> ${label}`);
  const res = spawnSync(cmd, args, { cwd: root, stdio: 'inherit', shell: isWin });
  if (res.status !== 0) {
    console.error(`Step failed: ${label}`);
    process.exit(res.status ?? 1);
  }
}

if (!env.DATABASE_URL) {
  console.error('DATABASE_URL is empty. Paste your Neon pooled URL into .env (see LOCAL_SETUP.md).');
  process.exit(1);
}

const localPort = env.LOCAL_PG_PORT || '54329';
if (/@(127\.0\.0\.1|localhost):/.test(env.DATABASE_URL) && env.DATABASE_URL.includes(`:${localPort}/`)) {
  step('Starting local Postgres', process.execPath, ['scripts/local-postgres.mjs', 'start']);
}
step('Applying migrations', 'uv', ['--directory', 'backend', 'run', 'alembic', '-c', 'api/alembic.ini', 'upgrade', 'head']);
if ((env.DEMO_MODE ?? 'true').toLowerCase() === 'true') {
  step('Seeding demo content (idempotent)', 'uv', ['--directory', 'backend', 'run', 'python', '-m', 'app.cli', 'seed-demo']);
}

const colors = { api: '\x1b[35m', worker: '\x1b[36m', web: '\x1b[33m' };
const services = [
  ['api', 'uv', ['--directory', 'backend', 'run', 'uvicorn', 'app.main:app', '--reload', '--reload-dir', 'api/app', '--host', '127.0.0.1', '--port', '8000']],
  ['worker', 'uv', ['--directory', 'backend', 'run', 'python', '-m', 'worker', 'run']],
  ['web', npm, ['run', 'dev', '--workspace', 'frontend']],
];

const children = services.map(([name, cmd, args]) => {
  const child = spawn(cmd, args, { cwd: root, shell: isWin, env: process.env });
  const prefix = `${colors[name]}[${name}]\x1b[0m `;
  const pipe = (stream, out) => {
    let buf = '';
    stream.on('data', (chunk) => {
      buf += chunk.toString();
      const lines = buf.split(/\r?\n/);
      buf = lines.pop() ?? '';
      for (const line of lines) out.write(prefix + line + '\n');
    });
  };
  pipe(child.stdout, process.stdout);
  pipe(child.stderr, process.stderr);
  child.on('exit', (code) => console.log(`${prefix}exited with code ${code}`));
  return child;
});

function shutdown() {
  for (const child of children) {
    if (child.exitCode !== null) continue;
    if (isWin) spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
    else child.kill('SIGINT');
  }
  process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
console.log('\nWeb: http://localhost:3000   API: http://localhost:8000/docs   (Ctrl+C to stop)\n');
