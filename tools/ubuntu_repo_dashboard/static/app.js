const state = {
  selectedJob: null,
  pollTimer: null,
  resultFiles: [],
};

const $ = (id) => document.getElementById(id);

function tokenHeader() {
  const token = $("token").value.trim();
  return token ? { "X-Dashboard-Token": token } : {};
}

async function getJson(url) {
  const res = await fetch(url, { headers: tokenHeader() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...tokenHeader() },
    body: JSON.stringify(body),
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload.error || `${res.status} ${res.statusText}`);
  return payload;
}

function text(value, fallback = "-") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function renderFiles(node, items, emptyText) {
  node.innerHTML = "";
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = emptyText;
    node.appendChild(li);
    return;
  }
  for (const item of items) {
    const li = document.createElement("li");
    li.textContent = item;
    node.appendChild(li);
  }
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = units[0];
  for (let i = 1; i < units.length && value >= 1024; i += 1) {
    value /= 1024;
    unit = units[i];
  }
  return `${value.toFixed(value >= 10 || unit === "B" ? 0 : 1)} ${unit}`;
}

function renderBranches(branches) {
  const list = $("branchList");
  list.innerHTML = "";
  for (const branch of branches || []) {
    const option = document.createElement("option");
    option.value = branch;
    list.appendChild(option);
  }
}

function renderResultFiles(files) {
  state.resultFiles = files || [];
  const host = $("resultFiles");
  host.innerHTML = "";
  if (state.resultFiles.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No result files found in configured result paths.";
    host.appendChild(li);
    return;
  }
  for (const file of state.resultFiles) {
    const li = document.createElement("li");
    li.className = "file-row";
    const meta = document.createElement("div");
    const modified = file.mtime ? new Date(file.mtime * 1000).toLocaleString() : "-";
    meta.innerHTML = `<strong>${file.path}</strong><span>${formatBytes(file.size)} | ${modified}</span>`;
    const button = document.createElement("button");
    button.className = "secondary";
    button.type = "button";
    button.textContent = "Download";
    button.addEventListener("click", () => downloadFile(file));
    li.append(meta, button);
    host.appendChild(li);
  }
}

function renderActions(actions, busy) {
  const host = $("actions");
  host.innerHTML = "";
  for (const [key, action] of Object.entries(actions)) {
    const row = document.createElement("div");
    row.className = "action";
    const copy = document.createElement("div");
    copy.innerHTML = `<strong>${action.label}</strong><span>${action.detail}</span>`;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Run";
    button.disabled = busy;
    button.addEventListener("click", () => runAction(key));
    row.append(copy, button);
    host.appendChild(row);
  }
}

function renderJobs(jobs) {
  const select = $("jobSelect");
  const previous = select.value;
  select.innerHTML = "";
  if (!jobs || jobs.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No jobs";
    select.appendChild(option);
    return;
  }
  for (const job of jobs) {
    const option = document.createElement("option");
    option.value = job.id;
    option.textContent = `${job.id} | ${job.status} | ${job.label}`;
    select.appendChild(option);
  }
  select.value = state.selectedJob || previous || jobs[0].id;
  state.selectedJob = select.value;
}

function renderStatus(payload) {
  const git = payload.git || {};
  $("repoPath").textContent = payload.repo || "Unknown repo";
  $("branch").textContent = text(git.branch);
  $("head").textContent = `HEAD ${text(git.head)}`;
  $("upstream").textContent = text(git.upstream, "No upstream");
  $("delta").textContent = `${text(git.behind, 0)} behind / ${text(git.ahead, 0)} ahead`;
  $("delta").className = Number(git.behind || 0) > 0 ? "warn" : "ok";
  $("worker").textContent = payload.busy ? "Running" : "Idle";
  $("worker").className = payload.busy ? "warn" : "ok";
  $("dirtyCount").textContent = `${(git.dirty || []).length} working tree entries`;
  $("incomingCount").textContent = String((git.incoming || []).length);
  $("dirtyChip").textContent = String((git.dirty || []).length);
  $("tokenState").textContent = payload.token_required ? "token" : "local";
  $("automation").textContent = `Auto fetch ${payload.auto_fetch_interval || 0}s | auto push ${payload.auto_push ? "on" : "off"} | self update ${payload.auto_self_update_interval || 0}s`;
  $("branchInput").value = $("branchInput").value || payload.default_branch || git.branch || "";
  renderBranches(payload.remote_branches || []);
  renderResultFiles(payload.result_files || []);
  renderFiles($("incoming"), git.incoming || [], "No incoming files. Run Fetch + Inspect to refresh.");
  renderFiles($("dirty"), git.dirty || [], "Working tree is clean.");
  renderActions(payload.actions || {}, payload.busy);
  renderJobs(payload.jobs || []);
  const selected = (payload.jobs || []).find((job) => job.id === state.selectedJob) || (payload.jobs || [])[0];
  if (selected) renderLog(selected);
}

function renderLog(job) {
  const started = job.started_at ? new Date(job.started_at * 1000).toLocaleString() : "queued";
  const duration = job.duration ? `${job.duration.toFixed(1)}s` : "";
  const head = `[${job.id}] ${job.label} | ${job.status} | ${started} ${duration}`;
  $("log").textContent = `${head}\n\n${(job.log || []).join("\n")}`;
  $("log").scrollTop = $("log").scrollHeight;
}

async function refreshFiles() {
  try {
    const payload = await getJson("/api/files");
    renderResultFiles(payload.files || []);
  } catch (err) {
    renderFiles($("resultFiles"), [`Could not load result files: ${err.message}`], "");
  }
}

async function downloadFile(file) {
  try {
    const res = await fetch(file.download_url, { headers: tokenHeader() });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    $("log").textContent = `Could not download ${file.path}: ${err.message}`;
  }
}

async function refresh() {
  try {
    const payload = await getJson("/api/status");
    renderStatus(payload);
    if (state.selectedJob) await refreshJob();
  } catch (err) {
    $("repoPath").textContent = `Dashboard error: ${err.message}`;
  }
}

async function refreshJob() {
  if (!state.selectedJob) return;
  try {
    const job = await getJson(`/api/job?id=${encodeURIComponent(state.selectedJob)}`);
    renderLog(job);
  } catch {
    state.selectedJob = null;
  }
}

async function runAction(action) {
  try {
    const branch = $("branchInput").value.trim();
    const payload = await postJson("/api/jobs", { action, branch });
    state.selectedJob = payload.job.id;
    await refresh();
  } catch (err) {
    $("log").textContent = `Could not start job: ${err.message}`;
  }
}

$("refresh").addEventListener("click", refresh);
$("reloadFiles").addEventListener("click", refreshFiles);
$("jobSelect").addEventListener("change", (event) => {
  state.selectedJob = event.target.value;
  refreshJob();
});

refresh();
state.pollTimer = window.setInterval(refresh, 3000);
