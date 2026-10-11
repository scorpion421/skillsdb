// Frontend Controller for SkillsDB Sidecar Panel

const sidecar = window.sidecar;
const $ = (id) => document.getElementById(id);
let activeTab = 'tasks';
let activeTaskFilter = 'all';
let currentWorkspace = null;

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

// ---------------------------------------------------------------------------
// Status & Header
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
  } catch (err) {
    console.warn('Status refresh failed:', err);
  }
}

// ---------------------------------------------------------------------------
// Tab 1: Tasks
// ---------------------------------------------------------------------------
async function loadTasks() {
  const container = $('tasks-list');
  try {
    const { tasks } = await callApi('/api/tasks');
    if (!tasks || tasks.length === 0) {
      container.innerHTML = '<div class="empty-state">No tasks recorded in .agents/memory.db yet.<br>Create one above or let your agent add tasks autonomously.</div>';
      return;
    }

    const filtered = tasks.filter((t) => activeTaskFilter === 'all' || t.status === activeTaskFilter);
    if (filtered.length === 0) {
      container.innerHTML = `<div class="empty-state">No tasks match filter "${escapeHtml(activeTaskFilter)}".</div>`;
      return;
    }

    container.innerHTML = filtered.map((task) => {
      const priorityClass = `pill-${task.priority || 'med'}`;
      const statusClass = `pill-${task.status || 'pending'}`;
      const statusLabel = (task.status || 'pending').replace('_', ' ');

      return `
        <div class="card" data-id="${task.id}">
          <div class="card-header">
            <div class="card-title">${escapeHtml(task.title)}</div>
            <div class="card-badges">
              <span class="pill ${priorityClass}">${escapeHtml(task.priority || 'med')}</span>
              <span class="pill ${statusClass}">${escapeHtml(statusLabel)}</span>
            </div>
          </div>
          ${task.description ? `<div class="card-desc">${escapeHtml(task.description)}</div>` : ''}
          <div class="card-footer">
            <span>#${task.id} &bull; ${formatDate(task.updated_at || task.created_at)}</span>
            <div class="card-actions">
              ${task.status !== 'completed' ? `
                <button class="btn-subtle" onclick="updateTaskStatus(${task.id}, 'completed')">Done</button>
                <button class="btn-subtle" onclick="updateTaskStatus(${task.id}, 'in_progress')">Active</button>
              ` : `
                <button class="btn-subtle" onclick="updateTaskStatus(${task.id}, 'pending')">Reopen</button>
              `}
              <button class="btn-subtle" onclick="sendTaskToAgent(${task.id}, '${escapeHtml(task.title).replace(/'/g, "\\'")}')" title="Send task prompt to active agent">Ask Agent</button>
              <button class="btn-subtle" onclick="deleteTask(${task.id})" title="Delete task">&times;</button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load tasks: ${escapeHtml(err.message)}</div>`;
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
  try {
    await navigator.clipboard.writeText(prompt);
    toast(`Prompt for task #${id} copied to clipboard`);
  } catch {
    toast(`Prompt: ${prompt}`);
  }
};

// ---------------------------------------------------------------------------
// Tab 2: Decisions
// ---------------------------------------------------------------------------
async function loadDecisions() {
  const container = $('decisions-list');
  try {
    const { decisions } = await callApi('/api/decisions');
    if (!decisions || decisions.length === 0) {
      container.innerHTML = '<div class="empty-state">No architectural decisions saved yet.<br>Save decisions via "skillsdb mem-save-decision".</div>';
      return;
    }

    container.innerHTML = decisions.map((d) => `
      <div class="card">
        <div class="card-header">
          <div class="card-title">${escapeHtml(d.title)}</div>
          <span class="pill pill-med">${escapeHtml(d.category || 'architecture')}</span>
        </div>
        <div class="card-desc">${escapeHtml(d.content)}</div>
        <div class="card-footer">
          <span>Decision #${d.id} &bull; ${formatDate(d.created_at)}</span>
        </div>
      </div>
    `).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load decisions: ${escapeHtml(err.message)}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Tab 3: Facts
// ---------------------------------------------------------------------------
async function loadFacts() {
  const activeContainer = $('facts-list');
  const historyContainer = $('facts-history');

  try {
    const { facts, history } = await callApi('/api/facts');

    if (!facts || facts.length === 0) {
      activeContainer.innerHTML = '<div class="empty-state">No active facts recorded.</div>';
    } else {
      activeContainer.innerHTML = facts.map((f) => `
        <div class="fact-item">
          <span class="fact-key">${escapeHtml(f.key)}</span>
          <span class="fact-val">${escapeHtml(f.value)}</span>
        </div>
      `).join('');
    }

    if (!history || history.length === 0) {
      historyContainer.innerHTML = '<div class="empty-state">No deprecated or reconciled history yet.</div>';
    } else {
      historyContainer.innerHTML = history.map((h) => `
        <div class="history-item">
          <strong>${escapeHtml(h.key)}</strong>:
          <span class="history-old">${escapeHtml(h.old_value)}</span> &rarr;
          <span class="history-new">${escapeHtml(h.new_value || '(tombstoned)')}</span>
          ${h.reason ? `<em>(${escapeHtml(h.reason)})</em>` : ''}
          <div style="font-size: 9px; margin-top: 2px;">${formatDate(h.changed_at)}</div>
        </div>
      `).join('');
    }
  } catch (err) {
    activeContainer.innerHTML = `<div class="empty-state">Failed to load facts: ${escapeHtml(err.message)}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Tab 4: Milestones & Git Radar
// ---------------------------------------------------------------------------
async function loadMilestones() {
  const container = $('milestones-list');
  try {
    const { milestones } = await callApi('/api/milestones');
    $('badge-milestones').textContent = milestones ? milestones.length : 0;

    if (!milestones || milestones.length === 0) {
      container.innerHTML = '<div class="empty-state">No session milestone snapshots recorded yet.<br>Save snapshots via "skillsdb mem-save-snapshot".</div>';
      return;
    }

    container.innerHTML = milestones.map((m) => {
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
            ${shortSha ? `
              <div class="card-actions">
                <button class="btn-subtle btn-rollback" onclick="rollbackMilestone('${m.git_commit_hash}', '${escapeHtml(m.summary).replace(/'/g, "\\'")}')">Rollback</button>
              </div>
            ` : ''}
          </div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div class="empty-state">Failed to load milestones: ${escapeHtml(err.message)}</div>`;
  }
}

window.rollbackMilestone = async function (commitHash, summary) {
  const short = commitHash.substring(0, 7);
  const confirmed = window.confirm(`WARNING: Are you sure you want to roll back the workspace to milestone "${summary}" (${short})?\n\nThis runs "git reset --hard ${short}". All uncommitted working tree changes will be discarded.`);
  if (!confirmed) return;

  try {
    const res = await callApi('/api/git/rollback', {
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
    btn.addEventListener('click', async () => {
      document.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      activeTaskFilter = btn.getAttribute('data-filter');
      await loadTasks();
    });
  });

  // Add Task
  $('btn-add-task')?.addEventListener('click', addTask);
  $('new-task-title')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') addTask();
  });

  // Refresh
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
