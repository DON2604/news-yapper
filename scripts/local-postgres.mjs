#!/usr/bin/env node
// Local PostgreSQL for development/tests without Docker, using the binaries
// shipped by the `embedded-postgres` npm package. Production uses Neon.
//
//   node scripts/local-postgres.mjs start|stop|status|reset --yes
//
// The data directory lives OUTSIDE the repository (cloud-synced folders such as
// OneDrive must never hold a live Postgres data directory).
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';
import { loadEnv } from './env.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const env = loadEnv(path.join(root, '.env'));
const port = Number(env.LOCAL_PG_PORT || 54329);
const password = env.LOCAL_PG_PASSWORD || '';
const databases = ['aajke', 'aajke_test'];

function defaultDataDir() {
  if (process.platform === 'win32') {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
    return path.join(base, 'aajke-ki-scene', 'pgdata');
  }
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'aajke-ki-scene', 'pgdata');
  }
  return path.join(os.homedir(), '.local', 'share', 'aajke-ki-scene', 'pgdata');
}

const dataDir = path.resolve(env.LOCAL_PG_DATA_DIR || defaultDataDir());
const logFile = path.join(path.dirname(dataDir), 'postgres.log');

function platformPackage() {
  const arch = process.arch;
  if (process.platform === 'win32') return '@embedded-postgres/windows-x64';
  if (process.platform === 'darwin') return `@embedded-postgres/darwin-${arch === 'arm64' ? 'arm64' : 'x64'}`;
  return `@embedded-postgres/linux-${arch}`;
}

async function binaries() {
  const name = platformPackage();
  try {
    const mod = await import(name);
    hydrateSymlinks(name);
    return mod;
  } catch (err) {
    console.error(`Could not load ${name}. Run "npm install" at the repository root first.\n${err}`);
    process.exit(1);
  }
}

// npm >= 11 does not run dependency install scripts unless approved; the
// platform package needs its symlink hydration step on macOS/Linux.
function hydrateSymlinks(pkgName) {
  const pkgDir = path.join(root, 'node_modules', ...pkgName.split('/'));
  const script = path.join(pkgDir, 'scripts', 'hydrate-symlinks.js');
  const marker = path.join(pkgDir, '.aks-hydrated');
  if (!fs.existsSync(script) || fs.existsSync(marker)) return;
  const res = spawnSync(process.execPath, [script], { cwd: pkgDir, stdio: 'inherit' });
  if (res.status === 0) fs.writeFileSync(marker, new Date().toISOString());
}

function run(bin, args, { quiet = false } = {}) {
  const res = spawnSync(bin, args, { encoding: 'utf8', windowsHide: true });
  if (!quiet && res.stdout) process.stdout.write(res.stdout);
  if (!quiet && res.stderr) process.stderr.write(res.stderr);
  return res;
}

function isInitialised() {
  return fs.existsSync(path.join(dataDir, 'PG_VERSION'));
}

async function ensureInit(bins) {
  if (isInitialised()) return;
  if (!password) {
    console.error('LOCAL_PG_PASSWORD is empty. Run "npm run setup" first.');
    process.exit(1);
  }
  fs.mkdirSync(path.dirname(dataDir), { recursive: true });
  const pwFile = path.join(os.tmpdir(), `aks-pg-pw-${process.pid}`);
  fs.writeFileSync(pwFile, password, { mode: 0o600 });
  console.log(`Initialising local Postgres cluster in ${dataDir} ...`);
  const res = run(bins.initdb, [
    `--pgdata=${dataDir}`,
    '--username=postgres',
    `--pwfile=${pwFile}`,
    '--auth=scram-sha-256',
    '--encoding=UTF8',
    '--locale=C',
  ]);
  fs.rmSync(pwFile, { force: true });
  if (res.status !== 0) {
    console.error('initdb failed');
    process.exit(1);
  }
}

function isRunning(bins) {
  if (!isInitialised()) return false;
  return run(bins.pg_ctl, ['status', '-D', dataDir], { quiet: true }).status === 0;
}

async function ensureDatabases() {
  const client = new pg.Client({ host: '127.0.0.1', port, user: 'postgres', password, database: 'postgres' });
  await client.connect();
  try {
    for (const db of databases) {
      const { rowCount } = await client.query('SELECT 1 FROM pg_database WHERE datname = $1', [db]);
      if (!rowCount) {
        await client.query(`CREATE DATABASE "${db}"`);
        console.log(`Created database ${db}`);
      }
    }
  } finally {
    await client.end();
  }
}

async function start() {
  const bins = await binaries();
  await ensureInit(bins);
  if (isRunning(bins)) {
    console.log(`Local Postgres already running on 127.0.0.1:${port}`);
  } else {
    // The server inherits pg_ctl's handles: with pipes attached the caller would
    // block forever, and sharing our console would stop Postgres when the
    // terminal closes. Detach with no stdio and wait for pg_ctl -w to exit.
    const code = await new Promise((resolve) => {
      const child = spawn(
        bins.pg_ctl,
        ['start', '-D', dataDir, '-l', logFile, '-o', `-p ${port} -c listen_addresses=127.0.0.1`, '-w', '-t', '90'],
        { detached: true, stdio: 'ignore', windowsHide: true },
      );
      child.on('exit', resolve);
      child.on('error', () => resolve(1));
    });
    if (code !== 0) {
      console.error(`pg_ctl start failed. See ${logFile}`);
      process.exit(1);
    }
    console.log(`Local Postgres started on 127.0.0.1:${port}`);
  }
  await ensureDatabases();
  console.log(`Databases ready: ${databases.join(', ')} (data: ${dataDir})`);
}

async function stop() {
  const bins = await binaries();
  if (!isRunning(bins)) {
    console.log('Local Postgres is not running.');
    return;
  }
  run(bins.pg_ctl, ['stop', '-D', dataDir, '-m', 'fast', '-w']);
}

async function status() {
  const bins = await binaries();
  console.log(isRunning(bins) ? `running on 127.0.0.1:${port} (data: ${dataDir})` : 'stopped');
}

async function reset() {
  if (!process.argv.includes('--yes')) {
    console.error('This deletes all local data. Re-run with --yes to confirm.');
    process.exit(1);
  }
  await stop();
  fs.rmSync(dataDir, { recursive: true, force: true });
  console.log(`Removed ${dataDir}`);
}

const commands = { start, stop, status, reset };
const cmd = process.argv[2] || 'status';
if (!commands[cmd]) {
  console.error(`Unknown command "${cmd}". Use: ${Object.keys(commands).join(' | ')}`);
  process.exit(1);
}
await commands[cmd]();
