// Backend for SkillsDB UI Extension Sidecar Panel
// Provides live JSON APIs over .agents/memory.db and local Gitea Git infrastructure.

import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join } from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const STARTED_AT = Date.now();

// Resilient Sidecar SDK loader (works inside Antigravity and standalone in Chrome)
process.env.ANTIGRAVITY_LS_ADDRESS ??= '127.0.0.1';
process.env.ANTIGRAVITY_CSRF_TOKEN ??= 'dev';
process.env.ANTIGRAVITY_SIDECAR_WEB_PORT ??= '3333';

let SidecarApp, Response;
try {
  const sdk = await import('sidecar_sdk');
  SidecarApp = sdk.SidecarApp;
  Response = sdk.Response;
} catch {
  const sdkUrl = pathToFileURL(join(homedir(), '.gemini', 'antigravity', 'lib', 'node_modules', 'sidecar_sdk', 'index.mjs')).href;
  const sdk = await import(sdkUrl);
  SidecarApp = sdk.SidecarApp;
  Response = sdk.Response;
}

const app = new SidecarApp();

// ---------------------------------------------------------------------------
// Static file serving (re-read per request for live frontend reloading)
// ---------------------------------------------------------------------------
const readLocal = (name) => readFileSync(join(HERE, name), 'utf8');

app.page('/', () => readLocal('index.html'));
app.page('/app.js', () => readLocal('app.js'));
app.api('/styles.css', () => new Response(readLocal('styles.css'), { contentType: 'text/css' }), 'GET');
app.api('/assets/logo.svg', () => {
  const logoPath = join(HERE, '..', '..', 'assets', 'logo.svg');
  return new Response(existsSync(logoPath) ? readFileSync(logoPath, 'utf8') : '', { contentType: 'image/svg+xml' });
}, 'GET');

// ---------------------------------------------------------------------------
// Workspace & Database Discovery
// ---------------------------------------------------------------------------
function resolveWorkspace(hintUri) {
  if (hintUri) {
    try {
      const p = hintUri.startsWith('file:') ? fileURLToPath(hintUri) : hintUri;
      if (existsSync(p)) return p;
    } catch {
      // Fall through to standard discovery
    }
  }

  // Traverse upward from cwd
  let cur = process.cwd();
  const rootLimit = homedir();
  while (cur && cur !== dirname(cur) && cur !== rootLimit) {
    if (existsSync(join(cur, '.agents', 'memory.db')) || existsSync(join(cur, '.git'))) {
      return cur;
    }
    cur = dirname(cur);
  }

  // Default fallback workspace for current active session
  const defaultScratch = join(homedir(), '.gemini', 'antigravity', 'scratch', 'SkillsDB');
  if (existsSync(defaultScratch)) return defaultScratch;

  return process.cwd();
}

function openProjectDb(workspacePath) {
  const root = resolveWorkspace(workspacePath);
  const dbPath = join(root, '.agents', 'memory.db');
  if (!existsSync(dbPath)) return null;

  try {
    const db = new DatabaseSync(dbPath);
    db.exec('PRAGMA busy_timeout = 3000;');
    return { db, root, dbPath };
  } catch (err) {
    console.error('Failed to open project memory database:', err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// APIs
// ---------------------------------------------------------------------------

// GET /api/status: System health, Gitea status, and workspace context
app.api('/api/status', async (params) => {
  const root = resolveWorkspace(params?.workspace);
  const dbInfo = openProjectDb(root);
  let giteaStatus = { connected: false, version: 'offline', repo: null };

  try {
    const res = await fetch('http://127.0.0.1:3000/api/v1/version', {
      headers: { 'Authorization': 'token 7d867a712de35b13de78261a5ef72276b527c1e0' },
      signal: AbortSignal.timeout(1500)
    });
    if (res.ok) {
      const data = await res.json();
      giteaStatus = { connected: true, version: data.version || '28.1.0', repo: 'MickyFoley/SkillsDB' };
    }
  } catch {
    // Gitea offline or unreachable
  }

  let taskCount = 0;
  let decisionCount = 0;
  let factCount = 0;

  if (dbInfo?.db) {
    try {
      taskCount = dbInfo.db.prepare("SELECT COUNT(*) as c FROM project_tasks WHERE status != 'completed';").get()?.c ?? 0;
      decisionCount = dbInfo.db.prepare('SELECT COUNT(*) as c FROM project_decisions;').get()?.c ?? 0;
      factCount = dbInfo.db.prepare('SELECT COUNT(*) as c FROM project_facts;').get()?.c ?? 0;
    } catch {
      // Table may not exist yet
    }
  }

  return {
    version: '3.6.0',
    uptimeSeconds: Math.round((Date.now() - STARTED_AT) / 1000),
    workspace: root,
    hasMemory: Boolean(dbInfo),
    gitea: giteaStatus,
    counts: { tasks: taskCount, decisions: decisionCount, facts: factCount }
  };
}, 'GET');

// GET /api/tasks: Retrieve task board
app.api('/api/tasks', (params) => {
  const dbInfo = openProjectDb(params?.workspace);
  if (!dbInfo?.db) return { tasks: [] };

  try {
    const stmt = dbInfo.db.prepare(`
      SELECT id, title, description, priority, status, created_at, updated_at
      FROM project_tasks
      ORDER BY
        CASE status
          WHEN 'in_progress' THEN 1
          WHEN 'pending' THEN 2
          WHEN 'blocked' THEN 3
          WHEN 'completed' THEN 4
          ELSE 5
        END,
        CASE priority
          WHEN 'critical' THEN 1
          WHEN 'high' THEN 2
          WHEN 'med' THEN 3
          ELSE 4
        END,
        id ASC;
    `);
    return { tasks: stmt.all() };
  } catch (err) {
    return { tasks: [], error: err.message };
  }
}, 'GET');

// POST /api/tasks/add: Add a new task directly from the UI
app.api('/api/tasks/add', (data) => {
  const dbInfo = openProjectDb(data?.workspace);
  if (!dbInfo?.db) throw new Error('Project memory database not found');

  const title = String(data.title ?? '').trim();
  if (!title) throw new Error('Task title cannot be empty');

  const priority = ['low', 'med', 'high', 'critical'].includes(data.priority) ? data.priority : 'med';
  const status = ['pending', 'in_progress', 'completed', 'blocked'].includes(data.status) ? data.status : 'pending';
  const now = new Date().toISOString();

  const stmt = dbInfo.db.prepare(`
    INSERT INTO project_tasks (title, description, priority, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?);
  `);
  stmt.run(title, data.description ?? '', priority, status, now, now);

  return { success: true, title, priority, status };
});

// POST /api/tasks/update: Change task status or priority
app.api('/api/tasks/update', (data) => {
  const dbInfo = openProjectDb(data?.workspace);
  if (!dbInfo?.db) throw new Error('Project memory database not found');

  const id = parseInt(data.id);
  if (isNaN(id)) throw new Error('Invalid task ID');

  const now = new Date().toISOString();
  const stmt = dbInfo.db.prepare(`
    UPDATE project_tasks
    SET status = COALESCE(?, status),
        priority = COALESCE(?, priority),
        updated_at = ?
    WHERE id = ?;
  `);
  stmt.run(data.status ?? null, data.priority ?? null, now, id);

  return { success: true, id };
});

// POST /api/tasks/delete: Delete task
app.api('/api/tasks/delete', (data) => {
  const dbInfo = openProjectDb(data?.workspace);
  if (!dbInfo?.db) throw new Error('Project memory database not found');

  const id = parseInt(data.id);
  if (isNaN(id)) throw new Error('Invalid task ID');

  dbInfo.db.prepare('DELETE FROM project_tasks WHERE id = ?;').run(id);
  return { success: true, id };
});

// GET /api/decisions: Retrieve architectural decision history
app.api('/api/decisions', (params) => {
  const dbInfo = openProjectDb(params?.workspace);
  if (!dbInfo?.db) return { decisions: [] };

  try {
    const stmt = dbInfo.db.prepare(`
      SELECT id, title, content, category, is_active, created_at
      FROM project_decisions
      WHERE is_active = 1
      ORDER BY id DESC
      LIMIT 40;
    `);
    return { decisions: stmt.all() };
  } catch (err) {
    return { decisions: [], error: err.message };
  }
}, 'GET');

// GET /api/facts: Retrieve active facts and tombstoned history
app.api('/api/facts', (params) => {
  const dbInfo = openProjectDb(params?.workspace);
  if (!dbInfo?.db) return { facts: [], history: [] };

  try {
    const activeStmt = dbInfo.db.prepare(`
      SELECT key, value, updated_at
      FROM project_facts
      WHERE deprecated_at IS NULL
      ORDER BY key ASC;
    `);
    const historyStmt = dbInfo.db.prepare(`
      SELECT id, key, old_value, new_value, reason, created_at
      FROM fact_history
      ORDER BY id DESC
      LIMIT 25;
    `);
    return { facts: activeStmt.all(), history: historyStmt.all() };
  } catch (err) {
    return { facts: [], history: [], error: err.message };
  }
}, 'GET');

// GET /api/milestones: Retrieve session snapshots with Git SHA coupling
app.api('/api/milestones', (params) => {
  const dbInfo = openProjectDb(params?.workspace);
  if (!dbInfo?.db) return { milestones: [] };

  try {
    const stmt = dbInfo.db.prepare(`
      SELECT id, conversation_id, summary, next_steps, files_touched, git_commit_hash, created_at
      FROM session_snapshots
      ORDER BY id DESC
      LIMIT 25;
    `);
    return { milestones: stmt.all() };
  } catch (err) {
    return { milestones: [], error: err.message };
  }
}, 'GET');

// POST /api/git/rollback: Execute safe Git hard reset to selected milestone
app.api('/api/git/rollback', (data) => {
  const root = resolveWorkspace(data?.workspace);
  const hash = String(data?.commitHash ?? '').trim();

  if (!/^[a-f0-9]{7,40}$/i.test(hash)) {
    throw new Error('Invalid commit hash format');
  }

  try {
    const stdout = execFileSync('git', ['reset', '--hard', hash], {
      cwd: root,
      encoding: 'utf8',
      windowsHide: true,
      timeout: 10000
    });
    return { success: true, commitHash: hash, output: stdout.trim() };
  } catch (err) {
    throw new Error(`Git reset failed: ${err.message}`);
  }
});

app.run();
