// Frontend Controller for SkillsDB Sidecar Panel
// 2026 Accessible Design System: 3-tier typography scale, APCA contrast, full CRUD & instant search.

const sidecar = window.sidecar;
const $ = (id) => document.getElementById(id);

let activeTab = 'tasks';
let activeTaskFilter = 'all';
let searchQuery = '';
let currentWorkspace = null;

// Local data caches for instantaneous client-side search filtering
let cachedTasks = [];
let cachedDecisions = [];
let cachedFacts = [];
let cachedHistory = [];
let cachedMilestones = [];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

async function getWorkspaceUri() {
  if (currentWorkspace) return currentWorkspace;
  if (sidecar?.getWorkspaceUris) {
    try {
      const uris = await sidecar.getWorkspaceUris();
      if (uris && uris.length > 0) {
        currentWorkspace = uris[0];
        return currentWorkspace;
      }
    } catch {
      // Fallback
    }
  }
  return null;
}

async function callApi(path, { method = 'GET', body } = {}) {
  const ws = await getWorkspaceUri();
  const sep = path.includes('?') ? '&' : '?';
  const fullPath = ws ? `${path}${sep}workspace=${encodeURIComponent(ws)}` : path;

  const fetcher = sidecar?.fetch
    ? sidecar.fetch.bind(sidecar)
    : (url, opts) => window.fetch(url, {
        ...opts,
        headers: {
          'Content-Type': 'application/json',
          ...(opts?.headers || {})
        }
      });

  const payload = body ? (ws ? { ...body, workspace: ws } : body) : undefined;
  const res = await fetcher(fullPath, {
    method,
    body: payload ? JSON.stringify(payload) : undefined
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}: ${res.statusText}`);
  }
  return data;
}

let toastTimer;
function toast(message, isError = false) {
  const el = $('toast');
  if (!el) return;
  el.textContent = message;
  el.classList.toggle('error', isError);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 3200);
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return isoStr;
  }
}

async function copyText(text, label = 'Content') {
  try {
    await navigator.clipboard.writeText(text);
    toast(`${label} copied to clipboard`);
  } catch {
    toast(`Copied: ${text}`);
  }
}

// ---------------------------------------------------------------------------
// Header & Status Bar
// ---------------------------------------------------------------------------
async function refreshStatus() {
  try {
    const data = await callApi('/api/status');
    const dot = $('gitea-dot');
    const text = $('gitea-text');

    if (data.gitea?.connected) {
      dot.className = 'status-dot online';
      text.textContent = `Gitea (${data.gitea.version})`;
      text.title = `Connected to local Gitea at http://localhost:3000 (${data.gitea.repo || 'SkillsDB'})`;
    } else {
      dot.className = 'status-dot';
      text.textContent = 'Gitea (Offline)';
      text.title = 'Local Gitea server not detected on port 3000';
    }

    if (data.counts) {
      $('badge-tasks').textContent = data.counts.tasks || 0;
      $('badge-decisions').textContent = data.counts.decisions || 0;
      $('badge-facts').textContent = data.counts.facts || 0;
    }

    // Update status bar
    const wsEl = $('footer-workspace');
    if (wsEl && data.workspace) {
      const parts = data.workspace.replace(/\\/g, '/').split('/');
      const shortName = parts[parts.length - 1] || data.workspace;
      wsEl.textContent = `Workspace: ${shortName}`;
      wsEl.title = data.workspace;
    }

    const dbEl = $('footer-db-status');
    if (dbEl) {
      dbEl.textContent = data.hasMemory ? 'Memory: Connected' : 'Memory: Standalone';
    }

    const syncEl = $('footer-sync-time');
    if (syncEl) {
      const now = new Date();
      syncEl.textContent = `Sync: ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
    }
  } catch (err) {
    console.warn('Status refresh failed:', err);
  }
}

// ---------------------------------------------------------------------------
// TAB 1: Tasks
// ---------------------------------------------------------------------------
function renderTasksList() {
  const container = $('tasks-list');
  if (!container) return;

  if (!cachedTasks || cachedTasks.length === 0) {
    container.innerHTML = '<div class="empty-state">No tasks recorded in .agents/memory.db yet.<br>Create one above or let your agent add tasks autonomously.</div>';
    return;
  }

  // Update filter count badges
  const counts = { all: cachedTasks.length, in_progress: 0, pending: 0, completed: 0, blocked: 0 };
  cachedTasks.forEach((t) => {
    if (counts[t.status] !== undefined) counts[t.status]++;
  });

  const cAll = $('count-all');
  const cInp = $('count-in_progress');
  const cPen = $('count-pending');
  const cCom = $('count-completed');
  const cBlo = $('count-blocked');
  if (cAll) cAll.textContent = `(${counts.all})`;
  if (cInp) cInp.textContent = `(${counts.in_progress})`;
  if (cPen) cPen.textContent = `(${counts.pending})`;
  if (cCom) cCom.textContent = `(${counts.completed})`;
  if (cBlo) cBlo.textContent = `(${counts.blocked})`;

  // Filter by tab filter
  let list = cachedTasks.filter((t) => activeTaskFilter === 'all' || t.status === activeTaskFilter);

  // Filter by live search query
  if (searchQuery) {
    list = list.filter((t) => {
      const q = searchQuery.toLowerCase();
      return (t.title && t.title.toLowerCase().includes(q)) ||
             (t.description && t.description.toLowerCase().includes(q)) ||
             (t.priority && t.priority.toLowerCase().includes(q)) ||
             (t.status && t.status.toLowerCase().includes(q));
    });
  }

  if (list.length === 0) {
    container.innerHTML = `<div class="empty-state">No tasks match current filter/search.</div>`;
    return;
  }

  container.innerHTML = list.map((task) => {
    const priorityClass = `pill-${task.priority || 'med'}`;
    const statusClass = `pill-${task.status || 'pending'}`;
    const statusLabel = (task.status || 'pending').replace('_', ' ');
    const isCompleted = task.status === 'completed';

    return `
      <div class="card" data-id="${task.id}">
        <div class="card-header">
          <div class="card-title-group">
            <button class="task-check-btn ${isCompleted ? 'checked' : ''}" onclick="toggleTaskCompletion(${task.id}, ${isCompleted})" title="${isCompleted ? 'Mark pending' : 'Mark completed'}" aria-label="Toggle task completion">
              ${isCompleted ? `
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
              ` : ''}
            </button>
            <div class="card-title ${isCompleted ? 'completed' : ''}" id="task-title-${task.id}" title="Double-click to rename" ondblclick="startEditTaskTitle(${task.id})">${escapeHtml(task.title)}</div>
          </div>
          <div class="card-badges">
            <span class="pill ${priorityClass}">${escapeHtml(task.priority || 'med')}</span>
            <span class="pill ${statusClass}">${escapeHtml(statusLabel)}</span>
          </div>
        </div>
        ${task.description ? `<div class="card-desc">${escapeHtml(task.description)}</div>` : ''}
        <div class="card-footer">
          <span>#${task.id} &bull; ${formatDate(task.updated_at || task.created_at)}</span>
          <div class="card-actions">
            ${!isCompleted ? `
              <button class="btn-subtle" onclick="updateTaskStatus(${task.id}, 'in_progress')" title="Mark In Progress">Active</button>
            ` : `
              <button class="btn-subtle" onclick="updateTaskStatus(${task.id}, 'pending')" title="Reopen Task">Reopen</button>
            `}
            <button class="btn-subtle" onclick="startEditTaskTitle(${task.id})" title="Rename task">Edit</button>
            <button class="btn-subtle" onclick="sendTaskToAgent(${task.id}, '${escapeHtml(task.title).replace(/'/g, "\\'")}')" title="Send task to active agent">Ask Agent</button>
            <button class="btn-subtle" onclick="deleteTask(${task.id})" title="Delete task">&times;</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function loadTasks() {
  const container = $('tasks-list');
  try {
    const { tasks } = await callApi('/api/tasks');
    cachedTasks = tasks || [];
    renderTasksList();
  } catch (err) {
    if (container) container.innerHTML = `<div class="empty-state">Failed to load tasks: ${escapeHtml(err.message)}</div>`;
  }
}

async function addTask() {
  const input = $('new-task-title');
  const title = input.value.trim();
  if (!title) return;

  const priority = $('new-task-priority').value;
  const status = $('new-task-status').value;

  try {
    await callApi('/api/tasks/add', { method: 'POST', body: { title, priority, status } });
    input.value = '';
    toast('Task added to memory.db');
    await loadTasks();
    await refreshStatus();
  } catch (err) {
    toast(`Failed to add task: ${err.message}`, true);
  }
}

window.toggleTaskCompletion = async function (id, wasCompleted) {
  const newStatus = wasCompleted ? 'pending' : 'completed';
  await window.updateTaskStatus(id, newStatus);
};

window.updateTaskStatus = async function (id, status) {
  try {
    await callApi('/api/tasks/update', { method: 'POST', body: { id, status } });
    toast(`Task #${id} marked ${status.replace('_', ' ')}`);
    await loadTasks();
    await refreshStatus();
  } catch (err) {
    toast(`Update failed: ${err.message}`, true);
  }
};

window.startEditTaskTitle = function (id) {
  const titleEl = $(`task-title-${id}`);
  if (!titleEl) return;
  const currentTitle = titleEl.textContent;

  const input = document.createElement('input');
  input.type = 'text';
  input.value = currentTitle;
  input.className = 'input-text';
  input.style.padding = '2px 6px';
  input.style.fontSize = 'var(--fs-body)';

  const saveEdit = async () => {
    const newTitle = input.value.trim();
    if (!newTitle || newTitle === currentTitle) {
      titleEl.textContent = currentTitle;
      return;
    }
    try {
      await callApi('/api/tasks/update', { method: 'POST', body: { id, title: newTitle } });
      toast(`Task #${id} renamed`);
      await loadTasks();
    } catch (err) {
      toast(`Rename failed: ${err.message}`, true);
      titleEl.textContent = currentTitle;
    }
  };

  input.addEventListener('blur', saveEdit);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') input.blur();
    if (e.key === 'Escape') {
      input.removeEventListener('blur', saveEdit);
      titleEl.textContent = currentTitle;
    }
  });

  titleEl.innerHTML = '';
  titleEl.appendChild(input);
  input.focus();
  input.select();
};

window.deleteTask = async function (id) {
  try {
    await callApi('/api/tasks/delete', { method: 'POST', body: { id } });
    toast(`Task #${id} deleted`);
    await loadTasks();
    await refreshStatus();
  } catch (err) {
    toast(`Delete failed: ${err.message}`, true);
  }
};

async function clearCompletedTasks() {
  const completedCount = cachedTasks.filter((t) => t.status === 'completed').length;
  if (completedCount === 0) {
    toast('No completed tasks to clear');
    return;
  }

  const confirmed = window.confirm(`Remove ${completedCount} completed task(s) from memory database?`);
  if (!confirmed) return;

  try {
    const res = await callApi('/api/tasks/clear-completed', { method: 'POST' });
    toast(`Cleared ${res.count || completedCount} completed task(s)`);
    await loadTasks();
    await refreshStatus();
  } catch (err) {
    toast(`Failed to clear: ${err.message}`, true);
  }
}

window.sendTaskToAgent = async function (id, title) {
  const prompt = `Please prioritize and work on task #${id}: "${title}". Inspect the relevant files and report progress.`;
  if (sidecar?.agent?.sendMessage && sidecar?.conversationId) {
    try {
      await sidecar.agent.sendMessage(prompt);
      toast(`Sent prompt for task #${id} to agent`);
      return;
    } catch (err) {
      console.warn('Failed to send via agent API:', err);
    }
  }

  // Fallback: copy to clipboard
  await copyText(prompt, `Prompt for task #${id}`);
};

// ---------------------------------------------------------------------------
// TAB 2: Decisions
// ---------------------------------------------------------------------------
function renderDecisionsList() {
  const container = $('decisions-list');
  if (!container) return;

  if (!cachedDecisions || cachedDecisions.length === 0) {
    container.innerHTML = '<div class="empty-state">No architectural decisions saved yet.<br>Record one above or use "skillsdb mem-save-decision".</div>';
    return;
  }

  let list = cachedDecisions;
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    list = list.filter((d) => {
      return (d.title && d.title.toLowerCase().includes(q)) ||
             (d.content && d.content.toLowerCase().includes(q)) ||
             (d.category && d.category.toLowerCase().includes(q));
    });
  }

  if (list.length === 0) {
    container.innerHTML = `<div class="empty-state">No decisions match current search.</div>`;
    return;
  }

  container.innerHTML = list.map((d) => `
    <div class="card">
      <div class="card-header">
        <div class="card-title">${escapeHtml(d.title)}</div>
        <span class="pill pill-med">${escapeHtml(d.category || 'architecture')}</span>
      </div>
      <div class="card-desc">${escapeHtml(d.content)}</div>
      <div class="card-footer">
        <span>Decision #${d.id} &bull; ${formatDate(d.created_at)}</span>
        <div class="card-actions">
          <button class="btn-subtle" onclick="copyDecision(${d.id})" title="Copy decision to clipboard">Copy</button>
        </div>
      </div>
    </div>
  `).join('');
}

async function loadDecisions() {
  const container = $('decisions-list');
  try {
    const { decisions } = await callApi('/api/decisions');
    cachedDecisions = decisions || [];
    renderDecisionsList();
  } catch (err) {
    if (container) container.innerHTML = `<div class="empty-state">Failed to load decisions: ${escapeHtml(err.message)}</div>`;
  }
}

async function saveDecision() {
  const title = $('new-decision-title').value.trim();
  const content = $('new-decision-content').value.trim();
  const category = $('new-decision-category').value;

  if (!title || !content) {
    toast('Decision title and content are required', true);
    return;
  }

  try {
    await callApi('/api/decisions/add', {
      method: 'POST',
      body: { title, content, category }
    });
    $('new-decision-title').value = '';
    $('new-decision-content').value = '';
    toggleDecisionForm(false);
    toast('Architectural decision recorded');
    await loadDecisions();
    await refreshStatus();
  } catch (err) {
    toast(`Failed to save decision: ${err.message}`, true);
  }
}

function toggleDecisionForm(expand) {
  const form = $('form-new-decision');
  const arrow = $('arrow-new-decision');
  if (!form || !arrow) return;

  const shouldOpen = expand !== undefined ? expand : form.style.display === 'none';
  form.style.display = shouldOpen ? 'flex' : 'none';
  arrow.textContent = shouldOpen ? 'Collapse' : 'Expand';
  if (shouldOpen) $('new-decision-title')?.focus();
}

window.copyDecision = function (id) {
  const d = cachedDecisions.find((item) => item.id === id);
  if (!d) return;
  const text = `# Architectural Decision: ${d.title}\nCategory: ${d.category}\nDate: ${d.created_at}\n\n${d.content}`;
  copyText(text, `Decision #${id}`);
};

// ---------------------------------------------------------------------------
// TAB 3: Facts
// ---------------------------------------------------------------------------
function renderFactsList() {
  const activeContainer = $('facts-list');
  const historyContainer = $('facts-history');
  if (!activeContainer || !historyContainer) return;

  // Active facts
  let activeList = cachedFacts;
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    activeList = activeList.filter((f) => {
      return (f.key && f.key.toLowerCase().includes(q)) ||
             (f.value && f.value.toLowerCase().includes(q));
    });
  }

  $('facts-count-active').textContent = `${cachedFacts.length} active`;
  $('facts-count-history').textContent = `${cachedHistory.length} archived`;

  if (activeList.length === 0) {
    activeContainer.innerHTML = '<div class="empty-state">No matching active facts recorded.</div>';
  } else {
    activeContainer.innerHTML = activeList.map((f) => `
      <div class="fact-item">
        <span class="fact-key">${escapeHtml(f.key)}</span>
        <div class="fact-val-group">
          <span class="fact-val">${escapeHtml(f.value)}</span>
          <button class="btn-subtle" onclick="copyFactValue('${escapeHtml(f.value).replace(/'/g, "\\'")}')" title="Copy value">Copy</button>
          <button class="btn-subtle" onclick="prepareFactEdit('${escapeHtml(f.key).replace(/'/g, "\\'")}', '${escapeHtml(f.value).replace(/'/g, "\\'")}')" title="Reconcile value">Edit</button>
          <button class="btn-subtle btn-danger" onclick="deprecateFact('${escapeHtml(f.key).replace(/'/g, "\\'")}')" title="Deprecate fact">Deprecate</button>
        </div>
      </div>
    `).join('');
  }

  // Tombstone history
  let histList = cachedHistory;
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    histList = histList.filter((h) => {
      return (h.key && h.key.toLowerCase().includes(q)) ||
             (h.old_value && h.old_value.toLowerCase().includes(q)) ||
             (h.new_value && h.new_value.toLowerCase().includes(q)) ||
             (h.reason && h.reason.toLowerCase().includes(q));
    });
  }

  if (histList.length === 0) {
    historyContainer.innerHTML = '<div class="empty-state">No tombstoned history recorded.</div>';
  } else {
    historyContainer.innerHTML = histList.map((h) => `
      <div class="history-item">
        <strong>${escapeHtml(h.key)}</strong>:
        <span class="history-old">${escapeHtml(h.old_value)}</span> &rarr;
        <span class="history-new">${escapeHtml(h.new_value || '(tombstoned)')}</span>
        ${h.reason ? `<em>(${escapeHtml(h.reason)})</em>` : ''}
        <div style="font-size: var(--fs-meta); margin-top: 2px; color: var(--muted-foreground, #8b949e);">${formatDate(h.created_at)}</div>
      </div>
    `).join('');
  }
}

async function loadFacts() {
  try {
    const { facts, history } = await callApi('/api/facts');
    cachedFacts = facts || [];
    cachedHistory = history || [];
    renderFactsList();
  } catch (err) {
    const activeContainer = $('facts-list');
    if (activeContainer) activeContainer.innerHTML = `<div class="empty-state">Failed to load facts: ${escapeHtml(err.message)}</div>`;
  }
}

function toggleFactForm(expand) {
  const form = $('form-new-fact');
  const arrow = $('arrow-new-fact');
  if (!form || !arrow) return;

  const shouldOpen = expand !== undefined ? expand : form.style.display === 'none';
  form.style.display = shouldOpen ? 'flex' : 'none';
  arrow.textContent = shouldOpen ? 'Collapse' : 'Expand';
  if (shouldOpen) $('new-fact-key')?.focus();
}

async function saveFact() {
  const key = $('new-fact-key').value.trim();
  const value = $('new-fact-value').value.trim();
  const reason = $('new-fact-reason').value.trim();

  if (!key) {
    toast('Fact key cannot be empty', true);
    return;
  }

  try {
    await callApi('/api/facts/save', {
      method: 'POST',
      body: { key, value, reason }
    });
    $('new-fact-key').value = '';
    $('new-fact-value').value = '';
    $('new-fact-reason').value = '';
    toggleFactForm(false);
    toast(`Fact "${key}" saved`);
    await loadFacts();
    await refreshStatus();
  } catch (err) {
    toast(`Failed to save fact: ${err.message}`, true);
  }
}

window.prepareFactEdit = function (key, val) {
  toggleFactForm(true);
  $('new-fact-key').value = key;
  $('new-fact-value').value = val;
  $('new-fact-reason').value = 'Reconciled via UI';
  $('new-fact-value').focus();
};

window.copyFactValue = function (val) {
  copyText(val, 'Fact value');
};

window.deprecateFact = async function (key) {
  const reason = window.prompt(`Deprecate fact "${key}"?\nEnter reason for retirement:`, 'Retired via UI');
  if (reason === null) return;

  try {
    await callApi('/api/facts/deprecate', {
      method: 'POST',
      body: { key, reason: reason.trim() || 'Deprecated via UI' }
    });
    toast(`Fact "${key}" tombstoned`);
    await loadFacts();
    await refreshStatus();
  } catch (err) {
    toast(`Deprecation failed: ${err.message}`, true);
  }
};

// ---------------------------------------------------------------------------
// TAB 4: Milestones & Git Radar
// ---------------------------------------------------------------------------
function renderMilestonesList() {
  const container = $('milestones-list');
  if (!container) return;

  $('badge-milestones').textContent = cachedMilestones ? cachedMilestones.length : 0;

  if (!cachedMilestones || cachedMilestones.length === 0) {
    container.innerHTML = '<div class="empty-state">No session milestone snapshots recorded yet.<br>Save snapshots via "skillsdb mem-save-snapshot".</div>';
    return;
  }

  let list = cachedMilestones;
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    list = list.filter((m) => {
      return (m.summary && m.summary.toLowerCase().includes(q)) ||
             (m.next_steps && m.next_steps.toLowerCase().includes(q)) ||
             (m.git_commit_hash && m.git_commit_hash.toLowerCase().includes(q));
    });
  }

  if (list.length === 0) {
    container.innerHTML = `<div class="empty-state">No milestones match current search.</div>`;
    return;
  }

  container.innerHTML = list.map((m) => {
    const shortSha = m.git_commit_hash ? m.git_commit_hash.substring(0, 7) : null;
    const giteaUrl = shortSha ? `http://localhost:3000/MickyFoley/SkillsDB/commit/${m.git_commit_hash}` : null;

    return `
      <div class="card">
        <div class="card-header">
          <div class="card-title">${escapeHtml(m.summary)}</div>
          ${shortSha ? `
            <a href="${giteaUrl}" target="_blank" class="commit-tag" title="View commit in Gitea">Git: ${shortSha}</a>
          ` : '<span class="pill pill-low">No Git SHA</span>'}
        </div>
        ${m.next_steps ? `<div class="card-desc"><strong>Next steps:</strong> ${escapeHtml(m.next_steps)}</div>` : ''}
        <div class="card-footer">
          <span>Snapshot #${m.id} &bull; ${formatDate(m.created_at)}</span>
          <div class="card-actions">
            ${shortSha ? `
              <button class="btn-subtle" onclick="copyCommitHash('${m.git_commit_hash}')" title="Copy Git SHA">Copy SHA</button>
              <button class="btn-subtle btn-danger" onclick="rollbackMilestone('${m.git_commit_hash}', '${escapeHtml(m.summary).replace(/'/g, "\\'")}')" title="Hard reset workspace to this milestone">Rollback</button>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function loadMilestones() {
  const container = $('milestones-list');
  try {
    const { milestones } = await callApi('/api/milestones');
    cachedMilestones = milestones || [];
    renderMilestonesList();
  } catch (err) {
    if (container) container.innerHTML = `<div class="empty-state">Failed to load milestones: ${escapeHtml(err.message)}</div>`;
  }
}

window.copyCommitHash = function (hash) {
  copyText(hash, 'Commit SHA');
};

window.rollbackMilestone = async function (commitHash, summary) {
  const short = commitHash.substring(0, 7);
  const confirmed = window.confirm(`WARNING: Are you sure you want to roll back the workspace to milestone "${summary}" (${short})?\n\nThis runs "git reset --hard ${short}". All uncommitted working tree changes will be discarded.`);
  if (!confirmed) return;

  try {
    await callApi('/api/git/rollback', {
      method: 'POST',
      body: { commitHash }
    });
    toast(`Workspace rolled back to ${short}!`);
    await refreshActiveTab();
  } catch (err) {
    toast(`Rollback failed: ${err.message}`, true);
  }
};

// ---------------------------------------------------------------------------
// Search & Keyboard Navigation
// ---------------------------------------------------------------------------
function updateSearch(query) {
  searchQuery = query.trim();
  const clearBtn = $('btn-search-clear');
  if (clearBtn) {
    clearBtn.style.display = searchQuery ? 'inline-flex' : 'none';
  }

  if (activeTab === 'tasks') renderTasksList();
  else if (activeTab === 'decisions') renderDecisionsList();
  else if (activeTab === 'facts') renderFactsList();
  else if (activeTab === 'milestones') renderMilestonesList();
}

function clearSearch() {
  const input = $('input-search');
  if (input) {
    input.value = '';
    input.blur();
  }
  updateSearch('');
}

// ---------------------------------------------------------------------------
// Lifecycle & Event Binding
// ---------------------------------------------------------------------------
async function refreshActiveTab() {
  await refreshStatus();
  if (activeTab === 'tasks') await loadTasks();
  else if (activeTab === 'decisions') await loadDecisions();
  else if (activeTab === 'facts') await loadFacts();
  else if (activeTab === 'milestones') await loadMilestones();
}

function bindEvents() {
  // Tabs
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', async () => {
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));
      btn.classList.add('active');
      activeTab = btn.getAttribute('data-tab');
      const pane = $(`pane-${activeTab}`);
      if (pane) pane.classList.add('active');
      await refreshActiveTab();
    });
  });

  // Task Filter
  document.querySelectorAll('.filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      activeTaskFilter = btn.getAttribute('data-filter');
      renderTasksList();
    });
  });

  // Task Actions
  $('btn-add-task')?.addEventListener('click', addTask);
  $('new-task-title')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') addTask();
  });
  $('btn-clear-completed')?.addEventListener('click', clearCompletedTasks);

  // Decision Form
  $('toggle-new-decision')?.addEventListener('click', () => toggleDecisionForm());
  $('btn-save-decision')?.addEventListener('click', saveDecision);
  $('btn-cancel-decision')?.addEventListener('click', () => toggleDecisionForm(false));

  // Fact Form
  $('toggle-new-fact')?.addEventListener('click', () => toggleFactForm());
  $('btn-save-fact')?.addEventListener('click', saveFact);
  $('btn-cancel-fact')?.addEventListener('click', () => toggleFactForm(false));

  // Search input
  const searchInput = $('input-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => updateSearch(e.target.value));
    searchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') clearSearch();
    });
  }
  $('btn-search-clear')?.addEventListener('click', clearSearch);

  // Global Keyboard Shortcuts
  document.addEventListener('keydown', (e) => {
    // Focus search with Ctrl+K or '/' when not typing in an input
    if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName))) {
      e.preventDefault();
      searchInput?.focus();
      searchInput?.select();
    }
    // Refresh with 'r' key when not typing
    if (e.key.toLowerCase() === 'r' && !e.ctrlKey && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      toast('Refreshing memory state...');
      refreshActiveTab();
    }
  });

  // Refresh Button
  $('btn-refresh')?.addEventListener('click', async () => {
    toast('Refreshing memory state...');
    await refreshActiveTab();
  });

  // Sidecar Workspace change listener
  if (sidecar?.onWorkspaceChange) {
    sidecar.onWorkspaceChange((uris) => {
      if (uris && uris.length > 0) {
        currentWorkspace = uris[0];
        refreshActiveTab();
      }
    });
  }
}

// Initial Boot
document.addEventListener('DOMContentLoaded', async () => {
  bindEvents();
  await refreshActiveTab();

  // Background polling every 4.5 seconds for zero-token live updates
  setInterval(() => {
    refreshActiveTab().catch(() => {});
  }, 4500);
});
