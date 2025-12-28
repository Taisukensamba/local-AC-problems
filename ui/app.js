const summaryEl = document.getElementById("summary");
const recentEl = document.getElementById("recent");
const userEl = document.getElementById("user");
const syncButton = document.getElementById("sync-run");
const syncStatusEl = document.getElementById("sync-status");
const syncContestsInput = document.getElementById("sync-contests");
const syncAllButton = document.getElementById("sync-all");
const tabButtons = document.querySelectorAll("[data-tab]");
const tabPanels = document.querySelectorAll("[data-tab-panel]");
const tableTabs = document.querySelectorAll(".tabs-secondary .tab-button");
const secondaryTabs = document.querySelector(".tabs-secondary");
const listStatusButtons = document.querySelectorAll("[data-list-status]");
const listGroupsEl = document.getElementById("list-groups");
const listStatusEl = document.getElementById("list-status");
const listLoadMoreButton = document.getElementById("list-load-more");
const listDiffTabsEl = document.getElementById("list-diff-tabs");
const toggleCompleted = document.getElementById("toggle-completed");
const toggleDiff = document.getElementById("toggle-diff");

const tables = [
  { key: "abc", label: "ABC", columns: ["A", "B", "C", "D", "E", "F", "G", "H"] },
  { key: "arc", label: "ARC", columns: ["A", "B", "C", "D", "E", "F"] },
  { key: "agc", label: "AGC", columns: ["A", "B", "C", "D", "E", "F"] },
  { key: "ahc", label: "AHC", columns: ["A"] },
];

const tableState = Object.fromEntries(
  tables.map((entry) => [
    entry.key,
    {
      key: entry.key,
      body: document.getElementById(`${entry.key}-body`),
      sentinel: document.getElementById(`${entry.key}-sentinel`),
      columns: entry.columns,
      offset: 0,
      limit: 20,
      loading: false,
      done: false,
    },
  ])
);

const diffGroups = [
  { key: "unknown", label: "unknown", min: null, max: null },
  { key: "neg", label: "<0", min: null, max: -1 },
  { key: "0", label: "0-399", min: 0, max: 399 },
  { key: "400", label: "400-799", min: 400, max: 799 },
  { key: "800", label: "800-1199", min: 800, max: 1199 },
  { key: "1200", label: "1200-1599", min: 1200, max: 1599 },
  { key: "1600", label: "1600-1999", min: 1600, max: 1999 },
  { key: "2000", label: "2000-2399", min: 2000, max: 2399 },
  { key: "2400", label: "2400-2799", min: 2400, max: 2799 },
  { key: "2800", label: "2800-3199", min: 2800, max: 3199 },
  { key: "3200", label: "3200-3599", min: 3200, max: 3599 },
  { key: "3600", label: "3600-3999", min: 3600, max: 3999 },
  { key: "4000", label: "4000+", min: 4000, max: null },
];

const listState = {
  status: "all",
  diffKey: "all",
  offset: 0,
  limit: 200,
  loading: false,
  done: false,
  groups: new Map(),
};

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) return null;
  return res.json();
}

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return null;
  return res.json();
}

function diffClassFor(diffValue) {
  if (diffValue === null || diffValue === undefined) return "diff-unknown";
  if (diffValue < 0) return "diff-neg";
  if (diffValue < 400) return "diff-0";
  if (diffValue < 800) return "diff-400";
  if (diffValue < 1200) return "diff-800";
  if (diffValue < 1600) return "diff-1200";
  if (diffValue < 2000) return "diff-1600";
  if (diffValue < 2400) return "diff-2000";
  if (diffValue < 2800) return "diff-2400";
  if (diffValue < 3200) return "diff-2800";
  if (diffValue < 3600) return "diff-3200";
  if (diffValue < 4000) return "diff-3600";
  return "diff-4000";
}

function diffPercentFor(diffValue) {
  if (typeof diffValue !== "number" || Number.isNaN(diffValue) || diffValue < 0) return 0;
  const start = Math.floor(diffValue / 400) * 400;
  const percent = ((diffValue - start) / 400) * 100;
  return Math.max(0, Math.min(100, Math.round(percent)));
}

function buildDiffRing(diffValue) {
  const diffClass = diffClassFor(diffValue);
  const diffLabel = diffValue === null ? "?" : diffValue;
  const ring = document.createElement("span");
  ring.className = `diff-ring cell-diff ${diffClass}`.trim();
  if (typeof diffValue === "number" && diffValue >= 3200) {
    ring.classList.add("diff-ring-static");
  }
  ring.style.setProperty("--diff-percent", `${diffPercentFor(diffValue)}%`);
  ring.title = diffValue === null ? "Difficulty: ?" : `Difficulty: ${diffValue}`;
  ring.setAttribute("aria-label", diffValue === null ? "Difficulty: ?" : `Difficulty: ${diffLabel}`);
  return ring;
}

function setActiveTab(key) {
  tabButtons.forEach((button) => {
    if (button.closest(".tabs-secondary")) return;
    button.classList.toggle("is-active", button.dataset.tab === key);
  });
  tabPanels.forEach((panel) => {
    const active = panel.dataset.tabPanel === key;
    panel.classList.toggle("is-active", active);
    panel.style.display = active ? "block" : "none";
  });
  if (secondaryTabs) {
    secondaryTabs.style.display = key === "tables" ? "flex" : "none";
  }
}

function setActiveTable(key) {
  tableTabs.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.tab === key);
  });
  tabPanels.forEach((panel) => {
    if (panel.dataset.tabPanel !== "tables") return;
    const active = panel.dataset.tableTab === key;
    panel.classList.toggle("is-active", active);
    panel.style.display = active ? "block" : "none";
  });
}

function renderSummary(items) {
  summaryEl.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "summary-item";
    row.innerHTML = `<span>${item.bin}</span><span>${item.ac_count}/${item.total_count}</span>`;
    summaryEl.appendChild(row);
  });
}

function _diffGroupFor(value) {
  if (value === null || value === undefined) return diffGroups[0];
  if (value < 0) return diffGroups[1];
  for (let i = 2; i < diffGroups.length; i += 1) {
    const g = diffGroups[i];
    if (g.min === null) continue;
    if (g.max === null && value >= g.min) return g;
    if (g.max !== null && value >= g.min && value <= g.max) return g;
  }
  return diffGroups[0];
}

function _ensureListGroups() {
  if (!listGroupsEl) return;
  listGroupsEl.innerHTML = "";
  listState.groups = new Map();
  const groupsToRender =
    listState.diffKey === "all"
      ? diffGroups
      : diffGroups.filter((group) => group.key === listState.diffKey);
  groupsToRender.forEach((group) => {
    const wrap = document.createElement("div");
    wrap.className = "list-group";
    const title = document.createElement("h4");
    title.textContent = group.label;
    const list = document.createElement("div");
    list.className = "list-items";
    wrap.appendChild(title);
    wrap.appendChild(list);
    listGroupsEl.appendChild(wrap);
    listState.groups.set(group.key, list);
  });
}

function _renderListItem(item) {
  const diffValue = typeof item.difficulty === "number" ? item.difficulty : null;
  const wrapper = document.createElement("div");
  wrapper.className = "list-item";
  const left = document.createElement("div");
  left.className = "list-title";
  const link = document.createElement("a");
  link.href = item.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = item.title || item.problem_id;
  const meta = document.createElement("span");
  meta.className = "list-meta-badges";
  const contestBadge = document.createElement("span");
  contestBadge.className = "list-badge";
  contestBadge.textContent = `${item.contest_id} ${item.task_index}`;
  meta.appendChild(contestBadge);
  meta.appendChild(buildDiffRing(diffValue));
  left.appendChild(link);
  left.appendChild(meta);
  const right = document.createElement("span");
  right.className = "list-badge";
  right.textContent = item.is_ac ? "AC" : "-";
  wrapper.appendChild(left);
  wrapper.appendChild(right);
  return wrapper;
}

function _appendListItems(items) {
  items.forEach((item) => {
    const diffValue = typeof item.difficulty === "number" ? item.difficulty : null;
    const group = _diffGroupFor(diffValue);
    if (listState.diffKey !== "all" && group.key !== listState.diffKey) {
      return;
    }
    const target = listState.groups.get(group.key);
    if (!target) return;
    target.appendChild(_renderListItem(item));
  });
}

async function fetchListPage() {
  if (listState.loading || listState.done) return;
  listState.loading = true;
  if (listStatusEl) listStatusEl.textContent = "loading...";
  const statusParam = listState.status === "all" ? "" : listState.status;
  const baseParams = `limit=${listState.limit}&offset=${listState.offset}`;
  const statusFilter = statusParam ? `&status=${statusParam}` : "";
  const url = `/api/problems?${baseParams}${statusFilter}&exclude_ahc=true`;
  const data = await getJSON(url);
  if (!data) {
    if (listStatusEl) listStatusEl.textContent = "load failed";
    listState.loading = false;
    return;
  }
  if (data.length === 0) {
    listState.done = true;
    if (listStatusEl) listStatusEl.textContent = "end";
    if (listLoadMoreButton) listLoadMoreButton.disabled = true;
  } else {
    _appendListItems(data);
    listState.offset += data.length;
  if (listStatusEl) listStatusEl.textContent = `${listState.offset} loaded`;
  }
  listState.loading = false;
}

function resetList() {
  listState.offset = 0;
  listState.loading = false;
  listState.done = false;
  if (listLoadMoreButton) listLoadMoreButton.disabled = false;
  _ensureListGroups();
  fetchListPage();
}

function renderRecent(items) {
  recentEl.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "recent-item";
    const label = item.result === "AC" ? "AC" : item.result;
    row.innerHTML = `
      <div>
        <div>${item.title || item.problem_id}</div>
        <small>${item.contest_id || ""} · ${label}</small>
      </div>
      <a href="${item.url}" target="_blank" rel="noreferrer">開く</a>
    `;
    recentEl.appendChild(row);
  });
}

function buildContestCell(contestId) {
  const cell = document.createElement("td");
  const link = document.createElement("a");
  link.href = `https://atcoder.jp/contests/${contestId}`;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = contestId.toUpperCase();
  cell.appendChild(link);
  return cell;
}

function buildProblemCell(state, index, prob) {
  const cell = document.createElement("td");
  if (!prob) {
    cell.textContent = "-";
    return cell;
  }
  const diffValue = typeof prob.difficulty === "number" ? prob.difficulty : null;
  const diffLabel = diffValue === null ? "?" : prob.difficulty;
  const diffClass = diffClassFor(diffValue);
  const link = document.createElement("a");
  link.className = `cell ${diffClass} ${prob.is_ac ? "ac" : ""}`.trim();
  if (prob.contest_ac) {
    link.classList.add("contest-ac");
  } else if (prob.contest_submitted && !prob.is_ac) {
    link.classList.add("contest-submitted");
  } else if (prob.non_contest_wa && !prob.is_ac) {
    link.classList.add("non-contest-submitted");
  }
  link.href = prob.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.title = prob.title;
  if (state.key === "ahc") {
    const indexEl = document.createElement("span");
    indexEl.className = "cell-index";
    indexEl.textContent = index;
    link.appendChild(indexEl);
  } else {
    link.classList.add("has-ring");
    link.appendChild(buildDiffRing(diffValue));
    const indexEl = document.createElement("span");
    indexEl.className = "cell-index";
    indexEl.textContent = index;
    link.appendChild(indexEl);
  }
  cell.appendChild(link);
  return cell;
}

function applyContestFilters(target) {
  const hideCompleted = toggleCompleted ? toggleCompleted.checked : false;
  target.querySelectorAll("tr").forEach((row) => {
    const completed = row.dataset.complete === "true";
    row.classList.toggle("row-hidden", hideCompleted && completed);
  });
}

function renderContestRows(state, items) {
  items.forEach((contest) => {
    const row = document.createElement("tr");
    const allSolved = contest.problems.length > 0 && contest.problems.every((p) => p.is_ac);
    row.dataset.complete = allSolved ? "true" : "false";
    row.appendChild(buildContestCell(contest.contest_id));
    const byIndex = Object.fromEntries(
      contest.problems.map((p) => [p.task_index, p])
    );
    state.columns.forEach((index) => {
      row.appendChild(buildProblemCell(state, index, byIndex[index]));
    });
    state.body.appendChild(row);
  });
  applyContestFilters(state.body);
}

async function fetchContest(key) {
  const state = tableState[key];
  if (!state || state.loading || state.done) return;
  state.loading = true;
  const data = await getJSON(`/api/contests/${key}?limit=${state.limit}&offset=${state.offset}`);
  if (!data) {
    state.sentinel.textContent = "読み込み失敗";
    state.loading = false;
    return;
  }
  if (data.length === 0) {
    state.done = true;
    state.sentinel.textContent = "end";
  } else {
    renderContestRows(state, data);
    state.offset += data.length;
  }
  state.loading = false;
}

function applyDiffToggle() {
  if (!toggleDiff) return;
  document.body.classList.toggle("hide-diff", !toggleDiff.checked);
}

function initTabs() {
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.tab;
      if (button.closest(".tabs-secondary")) {
        setActiveTab("tables");
        setActiveTable(key);
      } else {
        setActiveTab(key);
        if (key === "list") {
          resetList();
        }
      }
    });
  });
  setActiveTab("tables");
  setActiveTable("abc");
}

function initToggles() {
  if (toggleCompleted) {
    toggleCompleted.addEventListener("change", () => {
      Object.values(tableState).forEach((state) => {
        applyContestFilters(state.body);
      });
    });
  }
  if (toggleDiff) {
    toggleDiff.addEventListener("change", applyDiffToggle);
    applyDiffToggle();
  }
}

function initList() {
  if (listDiffTabsEl) {
    listDiffTabsEl.innerHTML = "";
    const allButton = document.createElement("button");
    allButton.className = "tab-button is-active";
    allButton.dataset.listDiff = "all";
    allButton.textContent = "All diff";
    listDiffTabsEl.appendChild(allButton);
    diffGroups.forEach((group) => {
      const button = document.createElement("button");
      button.className = "tab-button";
      button.dataset.listDiff = group.key;
      button.textContent = group.label;
      listDiffTabsEl.appendChild(button);
    });
  }
  if (listStatusButtons.length) {
    listStatusButtons.forEach((button) => {
      button.addEventListener("click", () => {
        listStatusButtons.forEach((b) =>
          b.classList.toggle("is-active", b === button)
        );
        const statusKey = button.dataset.listStatus || "all";
        listState.status = statusKey;
        resetList();
      });
    });
  }
  if (listDiffTabsEl) {
    listDiffTabsEl.querySelectorAll("[data-list-diff]").forEach((button) => {
      button.addEventListener("click", () => {
        listDiffTabsEl.querySelectorAll("[data-list-diff]").forEach((b) =>
          b.classList.toggle("is-active", b === button)
        );
        listState.diffKey = button.dataset.listDiff || "all";
        resetList();
      });
    });
  }
  if (listLoadMoreButton) {
    listLoadMoreButton.addEventListener("click", fetchListPage);
  }
  _ensureListGroups();
}

function initInfiniteScroll() {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const key = entry.target.getAttribute("data-key");
          if (key) fetchContest(key);
        }
      });
    },
    { rootMargin: "200px" }
  );
  tables.forEach((entry) => {
    const sentinel = tableState[entry.key].sentinel;
    sentinel.setAttribute("data-key", entry.key);
    observer.observe(sentinel);
  });
}

function renderSyncStatus(allStatus, syncStatus) {
  if (!syncStatusEl) return;
  if (!allStatus) {
    syncStatusEl.textContent = "sync: unavailable";
    return;
  }
  const running = allStatus.running;
  if (!running) {
    syncStatusEl.textContent = "sync: idle";
    return;
  }
  let msg = "sync: running";
  const progress = (syncStatus && syncStatus.progress) || {};
  const phase = progress.phase;
  const total = progress.total || 0;
  const done = progress.done || 0;
  const current = progress.current || "";
  if (phase) {
    msg += ` | ${phase}`;
    if (total) {
      msg += ` ${done}/${total}`;
    }
    if (current) {
      msg += ` (${current})`;
    }
  }
  syncStatusEl.textContent = msg;
}

async function pollSyncStatus() {
  const [allStatus, syncStatus] = await Promise.all([
    getJSON("/api/sync/all/status"),
    getJSON("/api/sync/status"),
  ]);
  renderSyncStatus(allStatus, syncStatus);
  if (syncButton) {
    syncButton.disabled = allStatus ? !!allStatus.running : false;
  }
}

function initSync() {
  if (!syncButton) return;
  let starting = false;
  syncButton.addEventListener("click", async () => {
    if (starting || syncButton.disabled) return;
    const raw = syncContestsInput ? syncContestsInput.value.trim() : "";
    if (!raw) {
      syncStatusEl.textContent = "sync: enter contest ids";
      return;
    }
    const contestIds = raw.split(/\s+/).filter(Boolean);
    starting = true;
    syncButton.disabled = true;
    syncStatusEl.textContent = "sync: starting...";
    const payload = {
      contest: false,
      tasks: true,
      submissions: true,
      mode: "cookie",
      tasks_incremental: true,
      submissions_incremental: true,
      contest_ids: contestIds,
    };
    const res = await postJSON("/api/sync", payload);
    if (!res) {
      syncStatusEl.textContent = "sync: failed";
      syncButton.disabled = false;
      starting = false;
      return;
    }
    await pollSyncStatus();
    starting = false;
  });
  pollSyncStatus();
  setInterval(pollSyncStatus, 5000);

  if (syncAllButton) {
    syncAllButton.addEventListener("click", async () => {
      if (starting || syncAllButton.disabled) return;
      const ok = window.confirm(
        "全同期は時間がかかります。実行しますか？"
      );
      if (!ok) return;
      starting = true;
      syncAllButton.disabled = true;
      syncStatusEl.textContent = "sync: starting...";
      const res = await postJSON("/api/sync/all", {});
      if (!res) {
        syncStatusEl.textContent = "sync: failed";
        syncAllButton.disabled = false;
        starting = false;
        return;
      }
      await pollSyncStatus();
      starting = false;
    });
  }
}

async function initDashboard() {
  const summary = await getJSON("/api/progress/summary");
  if (summary) renderSummary(summary);
  else summaryEl.innerHTML = '<div class="summary-item">読み込み失敗</div>';

  const recent = await getJSON("/api/progress/recent?limit=8");
  if (recent) renderRecent(recent);
  else recentEl.innerHTML = '<div class="recent-item">読み込み失敗</div>';

  const me = await getJSON("/api/me");
  userEl.textContent = me ? `user: ${me.user_id}` : "user: -";
}

function initTables() {
  tables.forEach((entry) => fetchContest(entry.key));
}

initTabs();
initToggles();
initInfiniteScroll();
initSync();
initDashboard();
initTables();
initList();
