const state = {
  health: null,
  templates: [],
  run: null,
  runId: null,
  pollTimer: null,
  clockTimer: null,
  startedMs: null,
  latestEventId: 0,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const esc = (value = "") => String(value).replace(/[&<>'"]/g, ch => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
}[ch]));

const departmentMeta = {
  research: { short: "R", label: "Strategy" },
  code: { short: "</>", label: "Engineering" },
  ux: { short: "UX", label: "Product Design" },
  notes: { short: "N", label: "Knowledge" },
  slides: { short: "P", label: "Communications" },
};

document.addEventListener("DOMContentLoaded", init);

async function init() {
  bindEvents();
  renderStandbyDepartments();
  try {
    const [health, templates] = await Promise.all([api("/api/health"), api("/api/templates")]);
    state.health = health;
    state.templates = templates.templates || [];
    renderProviders();
    renderTemplates();
    $("#runtimeLabel").textContent = `${health.service} ${health.version} · local control room`;
  } catch (error) {
    toast(`Could not initialise: ${error.message}`);
  }
}

function bindEvents() {
  $("#objective").addEventListener("input", event => {
    $("#charCount").textContent = `${event.target.value.length} / 2400`;
  });
  $("#quality").addEventListener("input", event => {
    const value = event.target.value;
    $("#qualityOutput").textContent = `${value}%`;
    event.target.style.background = `linear-gradient(90deg,var(--teal) ${value}%,#d3d0c8 ${value}%)`;
  });
  $$("#deliverableGrid input").forEach(input => input.addEventListener("change", () => {
    renderStandbyDepartments();
    $("#metricDepartments").textContent = selectedDeliverables().length;
  }));
  $("#launchButton").addEventListener("click", launchMission);
  $("#historyButton").addEventListener("click", openHistory);
  $("#closeHistory").addEventListener("click", closeHistory);
  $("#drawerBackdrop").addEventListener("click", closeHistory);
  $("#closePreview").addEventListener("click", () => $("#previewDialog").close());
}

function renderProviders() {
  const select = $("#provider");
  select.replaceChildren();
  Object.entries(state.health.providers).forEach(([value, item]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = `${item.label}${item.ready ? "" : " · not configured"}`;
    option.disabled = !item.ready;
    select.append(option);
  });
}

function renderTemplates() {
  const root = $("#templateStrip");
  root.replaceChildren();
  state.templates.forEach(template => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "template-chip";
    button.textContent = template.name;
    button.title = template.eyebrow;
    button.addEventListener("click", () => applyTemplate(template));
    root.append(button);
  });
}

function applyTemplate(template) {
  $("#objective").value = template.objective;
  $("#objective").dispatchEvent(new Event("input"));
  $$("#deliverableGrid input").forEach(input => {
    input.checked = template.deliverables.includes(input.value);
  });
  renderStandbyDepartments();
  $("#metricDepartments").textContent = selectedDeliverables().length;
  toast(`${template.name} loaded`);
}

function selectedDeliverables() {
  return $$("#deliverableGrid input:checked").map(input => input.value);
}

function renderStandbyDepartments() {
  if (state.run && !["completed", "failed"].includes(state.run.status)) return;
  const deliverables = selectedDeliverables();
  const root = $("#departmentGrid");
  root.innerHTML = deliverables.map(kind => {
    const meta = departmentMeta[kind];
    return `<article class="employee-card">
      <div class="employee-head"><span class="mini-avatar">${esc(meta.short)}</span><div><small>${esc(meta.label.toUpperCase())}</small><strong>${esc(displayName(kind))}</strong></div></div>
      <p>Will join the mission after the CEO approves the task graph.</p>
      <span class="dependency">DEPENDENCY · assigned during planning</span>
      <div class="employee-progress"><i></i></div>
      <div class="employee-footer"><span>standby</span><span>—</span></div>
    </article>`;
  }).join("");
}

async function launchMission() {
  const objective = $("#objective").value.trim();
  const deliverables = selectedDeliverables();
  if (objective.length < 12) return toast("Write a clearer objective (at least 12 characters).");
  if (!deliverables.length) return toast("Select at least one department.");

  setLaunching(true);
  resetRunUI();
  try {
    const response = await api("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        objective,
        context: $("#context").value.trim(),
        deliverables,
        provider: $("#provider").value,
        quality_threshold: Number($("#quality").value) / 100,
        max_parallel: 4,
      }),
    });
    state.runId = response.run_id;
    state.startedMs = Date.now();
    $("#runPill").textContent = state.runId.toUpperCase();
    startClock();
    await pollRun();
  } catch (error) {
    setLaunching(false);
    toast(error.message);
  }
}

function setLaunching(active) {
  const button = $("#launchButton");
  button.disabled = active;
  button.querySelector("span").textContent = active ? "Workforce deployed…" : "Deploy workforce";
}

async function pollRun() {
  clearTimeout(state.pollTimer);
  try {
    const run = await api(`/api/runs/${state.runId}`);
    state.run = run;
    renderRun(run);
    if (["completed", "failed"].includes(run.status)) {
      setLaunching(false);
      clearInterval(state.clockTimer);
      if (run.status === "completed") toast("Mission complete — delivery is ready.");
      return;
    }
    state.pollTimer = setTimeout(pollRun, 700);
  } catch (error) {
    setLaunching(false);
    toast(`Status update failed: ${error.message}`);
  }
}

function renderRun(run) {
  const completed = run.tasks.filter(task => task.status === "completed");
  const scores = completed.map(task => task.quality_score).filter(value => typeof value === "number");
  const average = scores.length ? scores.reduce((a,b) => a+b, 0) / scores.length : null;
  $("#statusKicker").textContent = statusKicker(run.status);
  $("#phaseTitle").textContent = run.phase;
  $("#phaseDescription").textContent = phaseDescription(run);
  $("#metricDepartments").textContent = run.tasks.length || selectedDeliverables().length;
  $("#metricQuality").textContent = average == null ? "—" : `${Math.round(average * 100)}%`;
  $("#metricCalls").textContent = run.usage.calls;
  $("#progressBar").style.width = `${run.progress}%`;
  $("#progressNumber").textContent = `${run.progress}%`;
  renderOrganization(run);
  renderLedger(run.events);
  renderArtifacts(run);
}

function renderOrganization(run) {
  const ceo = $("#orgMap .ceo-card");
  const ceoActive = ["planning", "integrating"].includes(run.status);
  ceo.className = `ceo-card ${ceoActive ? "active" : ""}`;
  ceo.querySelector("p").textContent = run.status === "planning" ? "Composing task graph" : run.phase;
  ceo.querySelector(".status-badge").textContent = run.status.toUpperCase();

  $("#departmentGrid").innerHTML = run.tasks.map(task => {
    const meta = departmentMeta[task.deliverable] || {short:"AI",label:task.department};
    const dependencies = task.dependencies.length
      ? `AFTER · ${task.dependencies.map(item => item.replace("task_", "")).join(", ")}`
      : "PARALLEL · no blocker";
    const score = typeof task.quality_score === "number" ? `${Math.round(task.quality_score * 100)}% QA` : "—";
    return `<article class="employee-card ${esc(task.status)}">
      <div class="employee-head"><span class="mini-avatar">${esc(meta.short)}</span><div><small>${esc(task.department.toUpperCase())} · ${esc(task.manager)}</small><strong>${esc(task.agent)}</strong></div></div>
      <p title="${esc(task.title)}">${esc(task.title)} · ${esc(task.brief)}</p>
      <span class="dependency">${esc(dependencies)}</span>
      <div class="employee-progress"><i style="width:${Number(task.progress)||0}%"></i></div>
      <div class="employee-footer"><span>${esc(task.status)}</span><span class="score-chip">${score}</span></div>
    </article>`;
  }).join("");
}

function renderLedger(events) {
  $("#eventCount").textContent = `${events.length} event${events.length === 1 ? "" : "s"}`;
  const root = $("#ledger");
  if (!events.length) return;
  root.innerHTML = events.slice().reverse().map(event => `<article class="ledger-event ${esc(event.kind)}">
    <div class="event-meta"><strong>${esc(event.actor)}</strong><time>${formatTime(event.at)}</time></div>
    <p>${esc(event.message)}</p>
  </article>`).join("");
}

function renderArtifacts(run) {
  const root = $("#artifactGrid");
  if (!run.artifacts.length) {
    root.innerHTML = '<div class="vault-empty"><span>Artifacts will arrive here after independent QA.</span></div>';
    return;
  }
  root.innerHTML = run.artifacts.map(artifact => {
    const score = typeof artifact.quality_score === "number" ? `${Math.round(artifact.quality_score*100)}% quality` : "Integrated output";
    const url = `/api/runs/${encodeURIComponent(run.id)}/artifacts/${encodeURIComponent(artifact.id)}`;
    return `<article class="artifact-card">
      <span class="artifact-type">${esc(extension(artifact.filename))}</span>
      <div><strong>${esc(artifact.title)}</strong><small>${esc(artifact.filename)} · ${esc(score)}</small></div>
      <div class="artifact-actions"><button type="button" data-preview="${esc(artifact.id)}" title="Preview">↗</button><a href="${url}" title="Download">↓</a></div>
    </article>`;
  }).join("");
  root.querySelectorAll("[data-preview]").forEach(button => button.addEventListener("click", () => previewArtifact(button.dataset.preview)));
  const bundle = $("#bundleButton");
  if (run.bundle_artifact_id) {
    bundle.classList.remove("disabled");
    bundle.setAttribute("aria-disabled", "false");
    bundle.href = `/api/runs/${encodeURIComponent(run.id)}/bundle`;
  }
}

async function previewArtifact(artifactId) {
  const artifact = state.run.artifacts.find(item => item.id === artifactId);
  if (!artifact) return;
  const url = `/api/runs/${encodeURIComponent(state.run.id)}/artifacts/${encodeURIComponent(artifact.id)}`;
  $("#previewKind").textContent = artifact.kind.toUpperCase();
  $("#previewTitle").textContent = artifact.title;
  $("#previewContent").textContent = "Loading artifact…";
  $("#previewDownload").href = url;
  $("#previewDialog").showModal();
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Artifact could not be loaded");
    $("#previewContent").textContent = await response.text();
  } catch (error) {
    $("#previewContent").textContent = error.message;
  }
}

async function openHistory() {
  $("#historyDrawer").classList.add("open");
  $("#drawerBackdrop").classList.add("open");
  $("#historyDrawer").setAttribute("aria-hidden", "false");
  const root = $("#historyList");
  root.innerHTML = "<p>Loading…</p>";
  try {
    const data = await api("/api/runs");
    if (!data.runs.length) root.innerHTML = "<p>No saved missions yet.</p>";
    else root.innerHTML = data.runs.map(run => `<button class="history-item" data-run="${esc(run.id)}"><strong>${esc(run.objective)}</strong><span>${esc(run.status.toUpperCase())} · ${esc(formatDate(run.created_at))} · ${run.artifact_count} artifacts</span></button>`).join("");
    root.querySelectorAll("[data-run]").forEach(button => button.addEventListener("click", () => loadArchivedRun(button.dataset.run)));
  } catch (error) { root.textContent = error.message; }
}

function closeHistory() {
  $("#historyDrawer").classList.remove("open");
  $("#drawerBackdrop").classList.remove("open");
  $("#historyDrawer").setAttribute("aria-hidden", "true");
}

async function loadArchivedRun(runId) {
  closeHistory();
  clearTimeout(state.pollTimer);
  clearInterval(state.clockTimer);
  state.runId = runId;
  state.run = await api(`/api/runs/${runId}`);
  state.startedMs = new Date(state.run.started_at || state.run.created_at).getTime();
  $("#runPill").textContent = runId.toUpperCase();
  renderRun(state.run);
  if (!["completed","failed"].includes(state.run.status)) {
    setLaunching(true); startClock(); pollRun();
  } else {
    setLaunching(false); updateClock();
  }
}

function startClock() {
  clearInterval(state.clockTimer);
  updateClock();
  state.clockTimer = setInterval(updateClock, 1000);
}

function updateClock() {
  if (!state.startedMs) return;
  const end = state.run?.completed_at ? new Date(state.run.completed_at).getTime() : Date.now();
  const seconds = Math.max(0, Math.floor((end - state.startedMs) / 1000));
  $("#metricTime").textContent = `${String(Math.floor(seconds/60)).padStart(2,"0")}:${String(seconds%60).padStart(2,"0")}`;
}

function resetRunUI() {
  state.run = null;
  state.latestEventId = 0;
  $("#metricQuality").textContent = "—";
  $("#metricCalls").textContent = "0";
  $("#progressBar").style.width = "1%";
  $("#progressNumber").textContent = "1%";
  $("#ledger").innerHTML = '<div class="empty-ledger"><span class="radar"><i></i></span><strong>CEO is waking the team</strong><p>The first delegation event will appear shortly.</p></div>';
  $("#artifactGrid").innerHTML = '<div class="vault-empty"><span>Departments are preparing their workspaces.</span></div>';
  $("#bundleButton").classList.add("disabled");
  $("#bundleButton").href = "#";
}

function phaseDescription(run) {
  if (run.error) return run.error;
  const active = run.tasks.filter(task => ["delegating","running","reviewing","revising"].includes(task.status));
  if (active.length) return active.map(task => `${task.agent}: ${task.status}`).join(" · ");
  if (run.status === "completed") return `${run.artifacts.length} traceable artifacts assembled and ready to download.`;
  return "The orchestrator owns dependencies, retries, quality gates, and termination.";
}

function statusKicker(status) {
  return ({queued:"MISSION QUEUED", planning:"CEO PLANNING", running:"WORKFORCE ACTIVE", integrating:"EXECUTIVE INTEGRATION", completed:"MISSION COMPLETE", failed:"MISSION STOPPED"})[status] || status.toUpperCase();
}

function displayName(kind) {
  return ({research:"Research Lead",code:"Principal Engineer",ux:"Product Designer",notes:"Learning Editor",slides:"Presentation Director"})[kind] || kind;
}
function extension(filename) { return filename.split(".").pop().slice(0,4); }
function formatTime(value) { return new Date(value).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit",second:"2-digit"}); }
function formatDate(value) { return new Date(value).toLocaleString([], {dateStyle:"medium",timeStyle:"short"}); }

async function api(url, options) {
  const response = await fetch(url, options);
  let payload;
  try { payload = await response.json(); } catch { payload = {}; }
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

let toastTimer;
function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 3200);
}
