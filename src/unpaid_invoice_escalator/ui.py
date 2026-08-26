from __future__ import annotations


APP_STYLES = """
:root {
  --bg: #f4f7fb;
  --panel: #ffffff;
  --panel-soft: #f8fbff;
  --text: #172033;
  --muted: #6b7a90;
  --line: #e3ebf5;
  --nav-bg: #0d1b34;
  --nav-muted: #9fb1ca;
  --nav-active: #163a78;
  --primary: #2962ff;
  --primary-soft: #e8efff;
  --orange: #ff8a34;
  --purple: #8854ff;
  --green: #22a861;
  --cyan: #1fa8c9;
  --red: #ef5252;
  --warn: #f59e0b;
  --shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: Arial, sans-serif; }
body { min-height: 100vh; }
a { color: inherit; text-decoration: none; }
button, input, select { font: inherit; }
button {
  border: 0;
  border-radius: 12px;
  padding: 11px 16px;
  background: var(--primary);
  color: #fff;
  cursor: pointer;
  transition: transform 0.12s ease, opacity 0.12s ease;
}
button:hover { opacity: 0.96; transform: translateY(-1px); }
.secondary-button { background: #edf3ff; color: #1e3a8a; }
.ghost-button { background: transparent; color: var(--primary); border: 1px solid var(--line); }
.app-shell {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  min-height: 100vh;
}
.sidebar {
  background: var(--nav-bg);
  color: #eef4ff;
  padding: 22px 18px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #2b66ff, #4d8eff);
  font-weight: 700;
}
.brand-copy strong {
  display: block;
  font-size: 15px;
}
.brand-copy span {
  display: block;
  color: var(--nav-muted);
  font-size: 12px;
  margin-top: 3px;
}
.nav-group {
  display: grid;
  gap: 8px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: 12px;
  color: #edf4ff;
  background: transparent;
  border: 1px solid transparent;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
}
.nav-item.active {
  background: var(--nav-active);
  border-color: rgba(255, 255, 255, 0.08);
}
.nav-item-main {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}
.nav-icon {
  width: 22px;
  height: 22px;
  border-radius: 8px;
  display: inline-grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.08);
  color: #dbe8ff;
  font-size: 11px;
  font-weight: 700;
}
.nav-icon svg {
  display: block;
}
.nav-badge {
  min-width: 22px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  display: inline-grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.08);
  color: #dbe8ff;
  font-size: 11px;
  font-weight: 700;
}
.sidebar-footer {
  margin-top: auto;
  padding: 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.sidebar-footer strong {
  display: block;
  margin-bottom: 6px;
}
.sidebar-footer span {
  color: var(--nav-muted);
  font-size: 12px;
  line-height: 1.5;
}
.main {
  padding: 24px;
  display: grid;
  gap: 18px;
}
.topbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 18px;
  align-items: center;
}
.page-copy h1 {
  margin: 0;
  font-size: 30px;
}
.page-copy p {
  margin: 8px 0 0;
  color: var(--muted);
}
.topbar-tools {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.search-box {
  min-width: 320px;
  max-width: 420px;
  width: 100%;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px 14px;
  color: var(--text);
}
.user-pill {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 8px 12px 8px 8px;
  box-shadow: var(--shadow);
}
.user-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: #6f42db;
  color: #fff;
  font-weight: 700;
}
.user-meta {
  font-size: 12px;
}
.user-meta strong {
  display: block;
  font-size: 13px;
}
.cards-6,
.cards-4,
.cards-3,
.cards-2 {
  display: grid;
  gap: 14px;
}
.cards-6 { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.cards-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.cards-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.cards-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.card,
.panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 20px;
  box-shadow: var(--shadow);
}
.card {
  padding: 16px;
}
.metric-card {
  position: relative;
  overflow: hidden;
}
.metric-card::before {
  content: "";
  position: absolute;
  left: 16px;
  right: 16px;
  bottom: 0;
  height: 3px;
  border-radius: 999px;
  background: var(--accent, var(--primary));
}
.metric-label {
  color: var(--accent, var(--primary));
  font-size: 13px;
  font-weight: 700;
}
.metric-value {
  margin-top: 10px;
  font-size: 30px;
  font-weight: 700;
}
.metric-hint {
  margin-top: 8px;
  color: var(--muted);
  font-size: 12px;
}
.metric-trend {
  margin-top: 12px;
  height: 30px;
  display: flex;
  align-items: center;
}
.sparkline {
  width: 100%;
  height: 30px;
}
.sparkline path.line {
  fill: none;
  stroke: var(--accent, var(--primary));
  stroke-width: 2.25;
}
.sparkline path.area {
  fill: transparent;
}
.panel {
  padding: 18px;
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.panel-header h2,
.panel-header h3 {
  margin: 0;
  font-size: 18px;
}
.panel-subtle,
.subtle,
.list-meta,
.empty-state,
.status-line {
  color: var(--muted);
}
.panel-subtle { font-size: 13px; }
.split-layout {
  display: grid;
  grid-template-columns: 1.7fr 1fr;
  gap: 18px;
}
.table-wrap {
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 16px;
  background: #fff;
}
table {
  width: 100%;
  border-collapse: collapse;
  min-width: 780px;
}
th, td {
  padding: 12px 10px;
  text-align: left;
  border-bottom: 1px solid #edf2f7;
  font-size: 13px;
}
th {
  color: var(--muted);
  background: #f8fbff;
  font-weight: 700;
}
tbody tr:hover {
  background: #f8fbff;
}
.clickable-row { cursor: pointer; }
.selected-row { background: #eef4ff; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}
.pill-blue { background: #eaf1ff; color: #2558df; }
.pill-orange { background: #fff3e9; color: #d9701f; }
.pill-purple { background: #f2ebff; color: #7f44f2; }
.pill-green { background: #e9f8f0; color: #1f8f56; }
.pill-red { background: #fdecec; color: #cb3c3c; }
.pill-grey { background: #eef2f7; color: #516276; }
.spotlight {
  display: grid;
  gap: 14px;
}
.stepper {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}
.step {
  text-align: center;
}
.step-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  margin: 0 auto 8px;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  background: #eef2f7;
  color: #637388;
}
.step.active .step-dot {
  background: var(--primary);
  color: #fff;
}
.step.done .step-dot {
  background: #e9f8f0;
  color: #1f8f56;
}
.step span {
  display: block;
  font-size: 11px;
  color: var(--muted);
  line-height: 1.4;
}
.kv-list,
.log-list,
.action-list {
  display: grid;
  gap: 10px;
}
.kv-row,
.log-item,
.action-item {
  display: grid;
  gap: 6px;
  padding: 12px 0;
  border-bottom: 1px solid #edf2f7;
}
.kv-row {
  grid-template-columns: 140px 1fr;
  align-items: start;
}
.kv-row:last-child,
.log-item:last-child,
.action-item:last-child { border-bottom: 0; }
.kv-row label {
  color: var(--muted);
  font-size: 13px;
}
.action-grid,
.form-grid,
.filter-grid,
.stat-chip-grid {
  display: grid;
  gap: 12px;
}
.action-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.filter-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.stat-chip-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.toolbar-panel {
  display: grid;
  gap: 12px;
}
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 14px;
}
.pagination-controls {
  display: inline-flex;
  gap: 8px;
  flex-wrap: wrap;
}
.pagination-chip,
.stat-chip {
  background: var(--panel-soft);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 10px 12px;
}
.stat-chip-count {
  display: block;
  margin-top: 6px;
  font-size: 22px;
  font-weight: 700;
  color: var(--text);
}
.filter-help {
  font-size: 12px;
  color: var(--muted);
}
.field {
  display: grid;
  gap: 6px;
  font-size: 13px;
}
.field input,
.field select,
.field textarea {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fff;
  padding: 11px 12px;
  color: var(--text);
}
.field textarea {
  min-height: 100px;
  resize: vertical;
}
.empty-state {
  padding: 18px;
  border: 1px dashed var(--line);
  border-radius: 16px;
  background: var(--panel-soft);
}
.inline-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.mono {
  font-family: Consolas, monospace;
  font-size: 12px;
}
.note-box {
  background: #fff8df;
  border: 1px solid #f6dda1;
  border-radius: 14px;
  padding: 14px;
  color: #7a5b10;
}
.good-box {
  background: #ebf8f2;
  border: 1px solid #caecd9;
  border-radius: 14px;
  padding: 14px;
  color: #196a42;
}
.status-line {
  min-height: 18px;
  font-size: 13px;
}
@media (max-width: 1400px) {
  .cards-6 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .cards-4 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .action-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filter-grid,
  .stat-chip-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 1100px) {
  .split-layout,
  .cards-3,
  .cards-2,
  .form-grid,
  .filter-grid,
  .stat-chip-grid { grid-template-columns: 1fr; }
  .stepper { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 900px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { display: none; }
  .topbar { grid-template-columns: 1fr; }
  .topbar-tools { justify-content: stretch; }
  .search-box { min-width: 0; }
  .cards-6,
  .cards-4,
  .action-grid { grid-template-columns: 1fr; }
}
"""


APP_SCRIPT = """
<script>
  const fcdUi = {
    escape(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    },
    formatMoney(value) {
      if (value === null || value === undefined || value === "") return "£0.00";
      const amount = Number(value);
      if (Number.isNaN(amount)) return String(value);
      return "£" + amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
    stateTone(status) {
      const normalized = String(status || "").toUpperCase();
      if (["RESOLVED_PAID"].includes(normalized)) return "pill-green";
      if (["DISPUTED", "DISPUTE_REVIEW", "BREATHING_SPACE_PAUSE", "JURISDICTION_UNCERTAIN"].includes(normalized)) return "pill-red";
      if (["FORMAL_NOTICE", "PRE_ACTION_PROTOCOL", "CLIENT_HANDOFF"].includes(normalized)) return "pill-orange";
      if (["FRIENDLY_REMINDER", "OVERDUE_CHASER"].includes(normalized)) return "pill-purple";
      return "pill-blue";
    },
    async request(url, method = "GET", body = null) {
      const init = { method, headers: {} };
      if (body !== null) {
        init.headers["content-type"] = "application/json";
        init.body = JSON.stringify(body);
      }
      const response = await fetch(url, init);
      const contentType = response.headers.get("content-type") || "";
      let payload = null;
      if (contentType.includes("application/json")) {
        payload = await response.json();
      } else {
        payload = await response.text();
      }
      if (!response.ok) {
        const detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : `Request failed: ${response.status}`;
        throw new Error(detail);
      }
      return payload;
    },
    setStatus(id, text) {
      const target = document.getElementById(id);
      if (target) target.textContent = text || "";
    },
    queryParam(name) {
      return new URLSearchParams(window.location.search).get(name);
    },
    updateQueryParam(name, value) {
      const url = new URL(window.location.href);
      if (!value) {
        url.searchParams.delete(name);
      } else {
        url.searchParams.set(name, value);
      }
      window.history.replaceState({}, "", url);
    },
    workflowIndex(status) {
      const states = ["ISSUED", "FRIENDLY_REMINDER", "OVERDUE_CHASER", "FORMAL_NOTICE", "PRE_ACTION_PROTOCOL", "CLIENT_HANDOFF"];
      const idx = states.indexOf(String(status || "").toUpperCase());
      return idx >= 0 ? idx : 0;
    },
    sparklineValues(seed, points = 8) {
      const base = Math.max(3, Number(seed) || 3);
      const values = [];
      for (let index = 0; index < points; index += 1) {
        const wave = ((base + index * 7) % 13) + (index % 3) * 2;
        values.push(10 + wave);
      }
      return values;
    },
    sparklineSvg(seriesOrSeed, color) {
      const values = Array.isArray(seriesOrSeed) && seriesOrSeed.length
        ? seriesOrSeed.map((value) => Number(value) || 0)
        : fcdUi.sparklineValues(seriesOrSeed);
      const width = 120;
      const height = 30;
      const max = Math.max(...values);
      const min = Math.min(...values);
      const spread = Math.max(1, max - min);
      const points = values.map((value, index) => {
        const x = (index / Math.max(1, values.length - 1)) * width;
        const y = height - ((value - min) / spread) * 18 - 4;
        return `${x},${y}`;
      });
      const line = points.join(" ");
      const area = `0,${height} ${line} ${width},${height}`;
      return `
        <svg class="sparkline" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
          <polygon points="${area}" fill="${color}" opacity="0.12"></polygon>
          <polyline points="${line}" fill="none" stroke="${color}" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"></polyline>
        </svg>
      `;
    },
    metricCard(label, value, hint, color, seriesOrSeed) {
      return `
        <div class="card metric-card" style="--accent:${color}">
          <div class="metric-label">${fcdUi.escape(label)}</div>
          <div class="metric-value">${fcdUi.escape(value)}</div>
          <div class="metric-hint">${fcdUi.escape(hint)}</div>
          <div class="metric-trend">${fcdUi.sparklineSvg(seriesOrSeed, color)}</div>
        </div>
      `;
    },
    statusCounts(cases) {
      const counts = {};
      for (const item of cases || []) {
        counts[item.current_state] = (counts[item.current_state] || 0) + 1;
      }
      return counts;
    },
    trendSeries(payload) {
      const metrics = payload?.metrics || {};
      const cases = payload?.cases || [];
      const recent = payload?.recent_activity || [];
      const blockedStates = ["DISPUTED", "DISPUTE_REVIEW", "BREATHING_SPACE_PAUSE", "JURISDICTION_UNCERTAIN"];
      const handoffStates = ["CLIENT_HANDOFF"];
      const resolvedStates = ["RESOLVED_PAID"];
      return {
        active: [cases.length, metrics.overdue || 0, metrics.due_today || 0, recent.length, metrics.blocked_or_paused || 0, cases.length],
        dueToday: [0, metrics.due_today || 0, metrics.due_today || 0, metrics.overdue || 0, metrics.due_today || 0, recent.length],
        blocked: [
          blockedStates.reduce((sum, state) => sum + (fcdUi.statusCounts(cases)[state] || 0), 0),
          metrics.blocked_or_paused || 0,
          recent.filter((item) => String(item.event_type || "").includes("DISPUT")).length,
          metrics.blocked_or_paused || 0,
          blockedStates.reduce((sum, state) => sum + (fcdUi.statusCounts(cases)[state] || 0), 0),
          recent.length
        ],
        outstanding: [
          Number(metrics.total_outstanding_gbp || 0),
          Number(metrics.total_outstanding_gbp || 0) - (metrics.overdue || 0) * 10,
          Number(metrics.total_outstanding_gbp || 0) + (metrics.due_today || 0) * 5,
          Number(metrics.total_outstanding_gbp || 0),
          Number(metrics.total_outstanding_gbp || 0) + recent.length * 3,
          Number(metrics.total_outstanding_gbp || 0)
        ],
        handoff: [
          handoffStates.reduce((sum, state) => sum + (fcdUi.statusCounts(cases)[state] || 0), 0),
          metrics.handoff_ready || 0,
          recent.filter((item) => String(item.event_type || "").includes("PACK")).length,
          metrics.handoff_ready || 0,
          handoffStates.reduce((sum, state) => sum + (fcdUi.statusCounts(cases)[state] || 0), 0),
          recent.length
        ],
        resolved: [
          resolvedStates.reduce((sum, state) => sum + (fcdUi.statusCounts(cases)[state] || 0), 0),
          metrics.resolved || 0,
          recent.filter((item) => String(item.event_type || "").includes("PAID")).length,
          metrics.resolved || 0,
          resolvedStates.reduce((sum, state) => sum + (fcdUi.statusCounts(cases)[state] || 0), 0),
          recent.length
        ]
      };
    }
  };
</script>
"""


def _icon_svg(icon: str) -> str:
    icons = {
        "dashboard": '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><rect x="3" y="4" width="7" height="7" rx="2" fill="currentColor"></rect><rect x="14" y="4" width="7" height="4" rx="2" fill="currentColor"></rect><rect x="14" y="11" width="7" height="9" rx="2" fill="currentColor"></rect><rect x="3" y="14" width="7" height="6" rx="2" fill="currentColor"></rect></svg>',
        "cases": '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><rect x="4" y="5" width="16" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="2"></rect><path d="M8 3v4M16 3v4M4 10h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>',
        "debtors": '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><circle cx="9" cy="9" r="4" fill="none" stroke="currentColor" stroke-width="2"></circle><path d="M3 20c1.5-3.5 4.4-5 8-5s6.5 1.5 8 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path><circle cx="18" cy="8" r="2" fill="currentColor"></circle></svg>',
        "creditors": '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M4 20V8l8-4 8 4v12" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></path><path d="M9 20v-5h6v5M8 10h1M11.5 10h1M15 10h1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>',
        "disputes": '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 3l8 3v6c0 5-3.4 7.7-8 9-4.6-1.3-8-4-8-9V6l8-3z" fill="none" stroke="currentColor" stroke-width="2"></path><path d="M9 9l6 6M15 9l-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>',
        "operations": '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M14 4l6 6-9 9H5v-6l9-9z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></path><path d="M13 5l6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>',
        "compliance": '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3z" fill="none" stroke="currentColor" stroke-width="2"></path><path d="M9 12l2 2 4-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
        "reports": '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M5 19V5h14v14H5z" fill="none" stroke="currentColor" stroke-width="2"></path><path d="M8 15l3-3 2 2 3-4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>',
    }
    return icons[icon]


def _nav_link(href: str, label: str, active_nav: str, nav_key: str, icon: str, badge: str = "") -> str:
    active_class = " active" if active_nav == nav_key else ""
    badge_html = f'<span class="nav-badge">{badge}</span>' if badge else ""
    return (
        f'<a class="nav-item{active_class}" href="{href}">'
        f'<span class="nav-item-main"><span class="nav-icon">{_icon_svg(icon)}</span><span>{label}</span></span>'
        f"{badge_html}</a>"
    )


def _sidebar(active_nav: str) -> str:
    return f"""
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">FCD</div>
        <div class="brand-copy">
          <strong>FCD Commercial Payment Resolution</strong>
          <span>Project P26003</span>
        </div>
      </div>
      <nav class="nav-group">
        {_nav_link('/', 'Dashboard', active_nav, 'dashboard', 'dashboard')}
        {_nav_link('/ui/cases', 'Cases', active_nav, 'cases', 'cases')}
        {_nav_link('/ui/debtors', 'Debtors', active_nav, 'debtors', 'debtors')}
        {_nav_link('/ui/creditors', 'Creditors', active_nav, 'creditors', 'creditors')}
        {_nav_link('/ui/disputes', 'Disputes', active_nav, 'disputes', 'disputes')}
        {_nav_link('/ui/operations', 'Operations', active_nav, 'operations', 'operations')}
        {_nav_link('/ui/compliance', 'Compliance', active_nav, 'compliance', 'compliance')}
        {_nav_link('/ui/reports', 'Reports', active_nav, 'reports', 'reports')}
      </nav>
      <div class="sidebar-footer">
        <strong>Operational focus</strong>
        <span>Firm, factual, and progressive. Live balances, audit trail, evidence readiness, and safe handoff.</span>
      </div>
    </aside>
    """


def _render_shell(
    *,
    title: str,
    subtitle: str,
    active_nav: str,
    content: str,
    page_script: str,
    search_placeholder: str,
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>{APP_STYLES}</style>
</head>
<body>
  <div class="app-shell">
    {_sidebar(active_nav)}
    <main class="main">
      <header class="topbar">
        <div class="page-copy">
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        <div class="topbar-tools">
          <input id="global-search" class="search-box" placeholder="{search_placeholder}" />
          <div class="user-pill">
            <div class="user-avatar">JA</div>
            <div class="user-meta">
              <strong>John Aitchison</strong>
              <span>Operations Manager</span>
            </div>
          </div>
        </div>
      </header>
      {content}
    </main>
  </div>
  {APP_SCRIPT}
  {page_script}
</body>
</html>
"""


def render_dashboard_html() -> str:
    content = """
      <section class="cards-6" id="overview-metrics"></section>

      <section class="split-layout">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Priority queue</h2>
              <div class="panel-subtle">Top live cases and next-step direction from the engine.</div>
            </div>
            <a class="ghost-button" style="padding:11px 16px;" href="/ui/cases">View all cases</a>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Balance</th>
                  <th>Status</th>
                  <th>Jurisdiction</th>
                  <th>Next step</th>
                </tr>
              </thead>
              <tbody id="priority-cases"></tbody>
            </table>
          </div>
        </div>

        <div class="spotlight">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Case spotlight</h2>
                <div class="panel-subtle">Selected case summary with workflow position.</div>
              </div>
            </div>
            <div id="spotlight-summary" class="empty-state">Loading case spotlight...</div>
          </div>
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Recent audit activity</h2>
                <div class="panel-subtle">Latest engine and compliance events across open cases.</div>
              </div>
              <a href="/ui/compliance" style="color: var(--primary); font-weight: 700;">Open compliance</a>
            </div>
            <div id="recent-activity" class="log-list"></div>
          </div>
        </div>
      </section>

      <section class="cards-3">
        <div class="panel">
          <div class="panel-header"><h3>Evidence readiness</h3></div>
          <div id="evidence-readiness" class="kv-list"></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h3>Status mix</h3></div>
          <div id="status-mix" class="stat-chip-grid"></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h3>Go next</h3></div>
          <div class="inline-actions">
            <a class="ghost-button" style="padding:11px 16px;" href="/ui/operations">Create or update case</a>
            <a class="ghost-button" style="padding:11px 16px;" href="/ui/compliance">Review audit trail</a>
            <a class="ghost-button" style="padding:11px 16px;" href="/ui/cases">Open case board</a>
            <a class="ghost-button" style="padding:11px 16px;" href="/ui/disputes">Open disputes board</a>
          </div>
        </div>
      </section>
    """

    script = """
<script>
  function renderMetrics(payload) {
    const metrics = payload.metrics || {};
    const trends = fcdUi.trendSeries(payload);
    const cards = [
      ["Active Cases", metrics.active_cases, "Tracked invoices", "var(--primary)", trends.active],
      ["Due Today", metrics.due_today, "Immediate attention", "var(--orange)", trends.dueToday],
      ["Disputes / Paused", metrics.blocked_or_paused, "Restricted cases", "var(--purple)", trends.blocked],
      ["Outstanding", fcdUi.formatMoney(metrics.total_outstanding_gbp), "Live debtor ledger", "var(--green)", trends.outstanding],
      ["Handoff Ready", metrics.handoff_ready, "Ready for client review", "var(--cyan)", trends.handoff],
      ["Resolved", metrics.resolved, "Closed paid cases", "var(--red)", trends.resolved]
    ];
    document.getElementById("overview-metrics").innerHTML = cards.map(([label, value, hint, color, series]) =>
      fcdUi.metricCard(label, value, hint, color, series)
    ).join("");
  }

  function renderPriorityCases(cases) {
    const rows = cases.slice(0, 6);
    const target = document.getElementById("priority-cases");
    if (!rows.length) {
      target.innerHTML = '<tr><td colspan="5"><div class="empty-state">No cases available yet.</div></td></tr>';
      return;
    }
    target.innerHTML = rows.map((item) => `
      <tr>
        <td><a href="/ui/cases?invoice=${encodeURIComponent(item.invoice_id)}"><strong>${fcdUi.escape(item.invoice_id)}</strong></a></td>
        <td>${fcdUi.escape(item.currency)} ${fcdUi.escape(item.outstanding_balance_gbp)}</td>
        <td><span class="pill ${fcdUi.stateTone(item.current_state)}">${fcdUi.escape(item.current_state)}</span></td>
        <td>${fcdUi.escape(item.jurisdiction)}</td>
        <td>${fcdUi.escape(item.next_step)}</td>
      </tr>
    `).join("");
  }

  function renderSpotlight(item) {
    if (!item) {
      document.getElementById("spotlight-summary").innerHTML = "No case selected.";
      return;
    }
    const activeIndex = fcdUi.workflowIndex(item.current_state);
    const steps = ["Prevent", "Monitor", "Resolve", "Escalate", "Handoff", "Close"];
    document.getElementById("spotlight-summary").innerHTML = `
      <div><strong>${fcdUi.escape(item.invoice_id)}</strong> <span class="pill ${fcdUi.stateTone(item.current_state)}">${fcdUi.escape(item.current_state)}</span></div>
      <div class="stepper">
        ${steps.map((step, idx) => {
          const cls = idx < activeIndex ? "done" : (idx === activeIndex ? "active" : "");
          return `<div class="step ${cls}"><div class="step-dot">${idx + 1}</div><span>${fcdUi.escape(step)}</span></div>`;
        }).join("")}
      </div>
      <div class="kv-list">
        <div class="kv-row"><label>Outstanding</label><div>${fcdUi.escape(item.currency)} ${fcdUi.escape(item.outstanding_balance_gbp)}</div></div>
        <div class="kv-row"><label>Jurisdiction</label><div>${fcdUi.escape(item.jurisdiction)}</div></div>
        <div class="kv-row"><label>Next step</label><div>${fcdUi.escape(item.next_step)}</div></div>
        <div class="kv-row"><label>Latest event</label><div>${fcdUi.escape(item.latest_event_type || "None")} ${item.latest_event_at ? ` | ${fcdUi.escape(item.latest_event_at)}` : ""}</div></div>
      </div>
      <div class="inline-actions">
        <a class="ghost-button" style="padding:11px 16px;" href="/ui/invoices/${encodeURIComponent(item.invoice_id)}">Open workspace</a>
        <a class="ghost-button" style="padding:11px 16px;" href="/ui/compliance?invoice=${encodeURIComponent(item.invoice_id)}">Review compliance</a>
      </div>
    `;
  }

  function renderRecentActivity(entries) {
    const target = document.getElementById("recent-activity");
    if (!entries.length) {
      target.innerHTML = '<div class="empty-state">No recent activity recorded.</div>';
      return;
    }
    target.innerHTML = entries.slice(0, 8).map((entry) => `
      <div class="log-item">
        <strong>${fcdUi.escape(entry.event_type || "Activity")}</strong>
        <span class="list-meta">Case ${fcdUi.escape(entry.invoice_id || "-")} | ${fcdUi.escape(entry.event_at || "Unknown")}</span>
      </div>
    `).join("");
  }

  function renderEvidenceReadiness(cases) {
    const active = cases[0];
    const target = document.getElementById("evidence-readiness");
    if (!active) {
      target.innerHTML = '<div class="empty-state">No evidence context available yet.</div>';
      return;
    }
    target.innerHTML = `
      <div class="kv-row"><label>Selected case</label><div>${fcdUi.escape(active.invoice_id)}</div></div>
      <div class="kv-row"><label>Chain valid</label><div>${fcdUi.escape(String(active.chain_valid))}</div></div>
      <div class="kv-row"><label>Outstanding</label><div>${fcdUi.escape(active.currency)} ${fcdUi.escape(active.outstanding_balance_gbp)}</div></div>
      <div class="kv-row"><label>Next step</label><div>${fcdUi.escape(active.next_step)}</div></div>
    `;
  }

  function renderStatusMix(cases) {
    const counts = {};
    for (const item of cases) {
      counts[item.current_state] = (counts[item.current_state] || 0) + 1;
    }
    const entries = Object.entries(counts);
    document.getElementById("status-mix").innerHTML = entries.length
      ? entries.slice(0, 6).map(([state, count]) => `
          <div class="stat-chip">
            <strong>${fcdUi.escape(state)}</strong>
            <span class="stat-chip-count">${fcdUi.escape(count)}</span>
            <span class="list-meta">${fcdUi.escape((count === 1 ? "case" : "cases"))}</span>
          </div>
        `).join("")
      : '<div class="empty-state">No statuses available.</div>';
  }

  async function loadOverview() {
    const payload = await fcdUi.request("/dashboard");
    const query = (document.getElementById("global-search").value || "").trim().toLowerCase();
    const cases = (payload.cases || []).filter((item) => {
      if (!query) return true;
      return [item.invoice_id, item.current_state, item.jurisdiction, item.debtor_type, item.next_step]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
    renderMetrics(payload);
    renderPriorityCases(cases);
    renderSpotlight(cases[0] || payload.cases?.[0] || null);
    renderRecentActivity(payload.recent_activity || []);
    renderEvidenceReadiness(cases.length ? cases : (payload.cases || []));
    renderStatusMix(cases.length ? cases : (payload.cases || []));
  }

  document.getElementById("global-search").addEventListener("input", loadOverview);
  window.addEventListener("load", loadOverview);
</script>
"""
    return _render_shell(
        title="Engine Dashboard",
        subtitle="Operational overview inspired by your mockup, split into focused pages to keep the experience lighter.",
        active_nav="dashboard",
        content=content,
        page_script=script,
        search_placeholder="Search cases, balances, jurisdictions, states...",
    )


def render_cases_html() -> str:
    content = """
      <section class="panel toolbar-panel">
        <div class="panel-header">
          <div>
            <h2>Case filters</h2>
            <div class="panel-subtle">Trim the workload by status, jurisdiction, and page size.</div>
          </div>
        </div>
        <div class="filter-grid">
          <label class="field">Status
            <select id="status-filter">
              <option value="">All statuses</option>
            </select>
          </label>
          <label class="field">Jurisdiction
            <select id="jurisdiction-filter">
              <option value="">All jurisdictions</option>
            </select>
          </label>
          <label class="field">Page size
            <select id="page-size">
              <option value="5">5 rows</option>
              <option value="10" selected>10 rows</option>
              <option value="20">20 rows</option>
            </select>
          </label>
          <div class="field">
            <span>Queue snapshot</span>
            <div id="case-summary-chips" class="stat-chip-grid"></div>
          </div>
        </div>
        <div class="filter-help">Use the global search above with these filters to keep large case sets manageable.</div>
      </section>

      <section class="split-layout">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Cases overview</h2>
              <div class="panel-subtle">Search, select, and move from triage to workspace.</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Debtor / Invoice</th>
                  <th>Balance</th>
                  <th>Status</th>
                  <th>Jurisdiction</th>
                  <th>Next step</th>
                </tr>
              </thead>
              <tbody id="cases-table"></tbody>
            </table>
          </div>
          <div class="pagination">
            <div id="cases-page-summary" class="pagination-chip">Loading cases...</div>
            <div class="pagination-controls">
              <button id="prev-page" class="secondary-button" type="button">Previous</button>
              <button id="next-page" class="secondary-button" type="button">Next</button>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Selected case</h2>
              <div class="panel-subtle">Live case detail from the engine.</div>
            </div>
          </div>
          <div id="case-detail" class="empty-state">Select a case to view details.</div>
        </div>
      </section>
    """
    script = """
<script>
  const state = { dashboard: null, selectedId: null, page: 1 };

  function filteredCases() {
    const query = (document.getElementById("global-search").value || "").trim().toLowerCase();
    const status = document.getElementById("status-filter").value;
    const jurisdiction = document.getElementById("jurisdiction-filter").value;
    const cases = state.dashboard?.cases || [];
    return cases.filter((item) => {
      if (status && item.current_state !== status) return false;
      if (jurisdiction && item.jurisdiction !== jurisdiction) return false;
      if (!query) return true;
      return [item.invoice_id, item.debtor_type, item.jurisdiction, item.current_state, item.next_step, item.outstanding_balance_gbp]
      .join(" ")
      .toLowerCase()
      .includes(query);
    });
  }

  function pagedCases() {
    const rows = filteredCases();
    const size = Number(document.getElementById("page-size").value || "10");
    const pageCount = Math.max(1, Math.ceil(rows.length / size));
    if (state.page > pageCount) state.page = pageCount;
    const start = (state.page - 1) * size;
    return { rows, visible: rows.slice(start, start + size), pageCount, start, size };
  }

  function syncFilters() {
    const cases = state.dashboard?.cases || [];
    const statuses = [...new Set(cases.map((item) => item.current_state))].sort();
    const jurisdictions = [...new Set(cases.map((item) => item.jurisdiction))].sort();
    const statusSelect = document.getElementById("status-filter");
    const jurisdictionSelect = document.getElementById("jurisdiction-filter");
    if (statusSelect.options.length === 1) {
      statusSelect.innerHTML = '<option value="">All statuses</option>' + statuses.map((value) => `<option value="${fcdUi.escape(value)}">${fcdUi.escape(value)}</option>`).join("");
    }
    if (jurisdictionSelect.options.length === 1) {
      jurisdictionSelect.innerHTML = '<option value="">All jurisdictions</option>' + jurisdictions.map((value) => `<option value="${fcdUi.escape(value)}">${fcdUi.escape(value)}</option>`).join("");
    }
  }

  function renderSummaryChips(rows) {
    const counts = {
      open: rows.filter((item) => item.current_state !== "RESOLVED_PAID").length,
      overdue: rows.filter((item) => item.is_overdue).length,
      blocked: rows.filter((item) => ["DISPUTED", "DISPUTE_REVIEW", "BREATHING_SPACE_PAUSE", "JURISDICTION_UNCERTAIN"].includes(item.current_state)).length
    };
    document.getElementById("case-summary-chips").innerHTML = [
      ["Open", counts.open],
      ["Overdue", counts.overdue],
      ["Blocked", counts.blocked]
    ].map(([label, count]) => `
      <div class="stat-chip">
        <strong>${fcdUi.escape(label)}</strong>
        <span class="stat-chip-count">${fcdUi.escape(count)}</span>
      </div>
    `).join("");
  }

  function renderTable() {
    const { rows, visible, pageCount, start } = pagedCases();
    const target = document.getElementById("cases-table");
    if (!rows.length) {
      target.innerHTML = '<tr><td colspan="6"><div class="empty-state">No cases match the current filter.</div></td></tr>';
      document.getElementById("cases-page-summary").textContent = "0 cases";
      renderSummaryChips([]);
      return;
    }
    target.innerHTML = visible.map((item) => `
      <tr class="clickable-row ${item.invoice_id === state.selectedId ? "selected-row" : ""}" data-invoice-id="${fcdUi.escape(item.invoice_id)}">
        <td><strong>${fcdUi.escape(item.invoice_id)}</strong></td>
        <td>${fcdUi.escape(item.debtor_type)}<br /><span class="list-meta">${fcdUi.escape(item.jurisdiction)} / ${fcdUi.escape(item.due_date)}</span></td>
        <td>${fcdUi.escape(item.currency)} ${fcdUi.escape(item.outstanding_balance_gbp)}</td>
        <td><span class="pill ${fcdUi.stateTone(item.current_state)}">${fcdUi.escape(item.current_state)}</span></td>
        <td>${fcdUi.escape(item.jurisdiction)}</td>
        <td>${fcdUi.escape(item.next_step)}</td>
      </tr>
    `).join("");
    target.querySelectorAll("[data-invoice-id]").forEach((row) => {
      row.addEventListener("click", () => selectCase(row.getAttribute("data-invoice-id")));
    });
    document.getElementById("cases-page-summary").textContent = `${start + 1}-${start + visible.length} of ${rows.length} cases | Page ${state.page} of ${pageCount}`;
    document.getElementById("prev-page").disabled = state.page <= 1;
    document.getElementById("next-page").disabled = state.page >= pageCount;
    renderSummaryChips(rows);
  }

  function renderDetail(item) {
    if (!item) {
      document.getElementById("case-detail").innerHTML = "Select a case to view details.";
      return;
    }
    const tone = fcdUi.stateTone(item.current_state);
    const counts = item._counts || {};
    const latestCommunication = item._latestCommunication || null;
    const ledger = item._ledgerSummary || {};
    const recentCompliance = item._recentCompliance || [];
    const recentAudit = item._recentAudit || [];
    const recentCommunicationEvents = item._recentCommunicationEvents || [];
    document.getElementById("case-detail").innerHTML = `
      <div class="kv-list">
        <div class="kv-row"><label>Case</label><div>${fcdUi.escape(item.invoice_id)}</div></div>
        <div class="kv-row"><label>Principal</label><div>${fcdUi.escape(item.currency)} ${fcdUi.escape(item.principal_amount)}</div></div>
        <div class="kv-row"><label>Outstanding</label><div>${fcdUi.escape(item.currency)} ${fcdUi.escape(item.outstanding_balance_gbp)}</div></div>
        <div class="kv-row"><label>Status</label><div><span class="pill ${tone}">${fcdUi.escape(item.current_state)}</span></div></div>
        <div class="kv-row"><label>Jurisdiction</label><div>${fcdUi.escape(item.jurisdiction)}</div></div>
        <div class="kv-row"><label>Due date</label><div>${fcdUi.escape(item.due_date)}</div></div>
        <div class="kv-row"><label>Chain valid</label><div>${fcdUi.escape(String(item.chain_valid))}</div></div>
        <div class="kv-row"><label>Latest event</label><div>${fcdUi.escape(item.latest_event_type || "None")}</div></div>
        <div class="kv-row"><label>Communications</label><div>${fcdUi.escape(counts.communications || 0)}</div></div>
        <div class="kv-row"><label>Compliance entries</label><div>${fcdUi.escape(counts.compliance || 0)}</div></div>
        <div class="kv-row"><label>Audit entries</label><div>${fcdUi.escape(counts.audit || 0)}</div></div>
        <div class="kv-row"><label>Latest communication</label><div>${fcdUi.escape(latestCommunication ? latestCommunication.subject : "None")}</div></div>
      </div>
      <div style="margin-top:16px;">
        <h3 style="margin:0 0 10px;">Five-ledger snapshot</h3>
        <div class="kv-list">
          <div class="kv-row"><label>Financial balance</label><div>${fcdUi.escape(ledger.outstanding_balance_gbp || ledger.financial_ledger_balance_gbp || item.outstanding_balance_gbp || "0.00")}</div></div>
          <div class="kv-row"><label>Evidence artifacts</label><div>${fcdUi.escape(ledger.evidence_ledger_artifacts_count || 0)}</div></div>
          <div class="kv-row"><label>Event audit entries</label><div>${fcdUi.escape(ledger.event_audit_ledger_events_count || 0)}</div></div>
          <div class="kv-row"><label>Compliance ledger entries</label><div>${fcdUi.escape(ledger.compliance_ledger_events_count || 0)}</div></div>
          <div class="kv-row"><label>FCD billing balance</label><div>${fcdUi.escape(ledger.fcd_billing_ledger_balance_gbp || "0.00")}</div></div>
        </div>
      </div>
      <div style="margin-top:16px;">
        <h3 style="margin:0 0 10px;">Latest case activity</h3>
        <div class="action-list">
          <div class="action-item">
            <strong>Communication flow</strong>
            <span class="list-meta">${fcdUi.escape(latestCommunication ? `${latestCommunication.channel} | ${latestCommunication.latest_state} | ${latestCommunication.recipient}` : "No communication created yet.")}</span>
          </div>
          <div class="action-item">
            <strong>Recent delivery events</strong>
            <span class="list-meta">${fcdUi.escape(recentCommunicationEvents.map((event) => `${event.state} @ ${event.timestamp}`).join(" | ") || "No delivery events recorded.")}</span>
          </div>
          <div class="action-item">
            <strong>Recent compliance</strong>
            <span class="list-meta">${fcdUi.escape(recentCompliance.map((entry) => entry.event_type).join(" | ") || "No compliance entries recorded.")}</span>
          </div>
          <div class="action-item">
            <strong>Recent audit</strong>
            <span class="list-meta">${fcdUi.escape(recentAudit.map((entry) => entry.action).join(" | ") || "No audit entries recorded.")}</span>
          </div>
        </div>
      </div>
      <div class="inline-actions">
        <a class="ghost-button" style="padding:11px 16px;" href="/ui/invoices/${encodeURIComponent(item.invoice_id)}">Open workspace</a>
        <a class="ghost-button" style="padding:11px 16px;" href="/ui/compliance?invoice=${encodeURIComponent(item.invoice_id)}">Open compliance</a>
      </div>
    `;
  }

  async function selectCase(invoiceId) {
    state.selectedId = invoiceId;
    fcdUi.updateQueryParam("invoice", invoiceId);
    renderTable();
    const [detail, communications, compliance, audit, ledgerSummary] = await Promise.all([
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}`),
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/communications`),
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/compliance-ledger`),
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/audit-trail`),
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/five-ledger-summary`)
    ]);
    detail._counts = {
      communications: (communications.communications || []).length,
      compliance: (compliance.entries || []).length,
      audit: (audit.entries || []).length
    };
    detail._latestCommunication = (communications.communications || []).slice(-1)[0] || null;
    detail._recentCommunicationEvents = detail._latestCommunication ? (detail._latestCommunication.events || []).slice(-3).reverse() : [];
    detail._recentCompliance = (compliance.entries || []).slice(-3).reverse();
    detail._recentAudit = (audit.entries || []).slice(-3).reverse();
    detail._ledgerSummary = ledgerSummary || {};
    renderDetail(detail);
  }

  async function loadCases() {
    state.dashboard = await fcdUi.request("/dashboard");
    syncFilters();
    const preferred = fcdUi.queryParam("invoice") || state.dashboard.cases?.[0]?.invoice_id || null;
    renderTable();
    if (preferred) await selectCase(preferred);
  }

  function rerenderFromControls(resetPage = true) {
    if (resetPage) state.page = 1;
    renderTable();
  }

  document.getElementById("global-search").addEventListener("input", () => rerenderFromControls(true));
  document.getElementById("status-filter").addEventListener("change", () => rerenderFromControls(true));
  document.getElementById("jurisdiction-filter").addEventListener("change", () => rerenderFromControls(true));
  document.getElementById("page-size").addEventListener("change", () => rerenderFromControls(true));
  document.getElementById("prev-page").addEventListener("click", () => { if (state.page > 1) { state.page -= 1; renderTable(); } });
  document.getElementById("next-page").addEventListener("click", () => { state.page += 1; renderTable(); });
  window.addEventListener("load", loadCases);
</script>
"""
    return _render_shell(
        title="Cases",
        subtitle="A dedicated case board so the main dashboard stays lighter and easier to scan.",
        active_nav="cases",
        content=content,
        page_script=script,
        search_placeholder="Search case ID, status, jurisdiction, balance...",
    )


def render_debtors_html() -> str:
    content = """
      <section class="cards-3">
        <div class="panel">
          <div class="panel-header"><h2>Debtor segments</h2></div>
          <div id="debtor-segments" class="stat-chip-grid"></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h2>Jurisdiction mix</h2></div>
          <div id="debtor-jurisdictions" class="stat-chip-grid"></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h2>Resolution posture</h2></div>
          <div id="debtor-posture" class="action-list"></div>
        </div>
      </section>

      <section class="split-layout">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Debtor-facing case list</h2>
              <div class="panel-subtle">Cases grouped for portal and outreach review.</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Debtor Type</th>
                  <th>Balance</th>
                  <th>Status</th>
                  <th>Next step</th>
                </tr>
              </thead>
              <tbody id="debtor-case-table"></tbody>
            </table>
          </div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Portal readiness</h2>
              <div class="panel-subtle">Quick view of routes that matter to a debtor response flow.</div>
            </div>
          </div>
          <div id="portal-readiness" class="kv-list"></div>
        </div>
      </section>
    """
    script = """
<script>
  function countBy(items, key) {
    const counts = {};
    for (const item of items) counts[item[key]] = (counts[item[key]] || 0) + 1;
    return counts;
  }

  function renderCountGrid(id, counts) {
    const target = document.getElementById(id);
    const entries = Object.entries(counts);
    target.innerHTML = entries.length
      ? entries.map(([label, count]) => `
          <div class="stat-chip">
            <strong>${fcdUi.escape(label)}</strong>
            <span class="stat-chip-count">${fcdUi.escape(count)}</span>
          </div>
        `).join("")
      : '<div class="empty-state">No data available.</div>';
  }

  async function loadDebtorsPage() {
    const payload = await fcdUi.request("/dashboard");
    const query = (document.getElementById("global-search").value || "").trim().toLowerCase();
    const cases = (payload.cases || []).filter((item) => {
      if (!query) return true;
      return [item.invoice_id, item.debtor_type, item.current_state, item.jurisdiction, item.next_step].join(" ").toLowerCase().includes(query);
    });
    renderCountGrid("debtor-segments", countBy(cases, "debtor_type"));
    renderCountGrid("debtor-jurisdictions", countBy(cases, "jurisdiction"));
    const openCount = cases.filter((item) => item.current_state !== "RESOLVED_PAID").length;
    const pausedCount = cases.filter((item) => ["DISPUTED", "DISPUTE_REVIEW", "BREATHING_SPACE_PAUSE"].includes(item.current_state)).length;
    document.getElementById("debtor-posture").innerHTML = `
      <div class="action-item"><strong>Open cases</strong><span class="list-meta">${fcdUi.escape(openCount)} still require engagement or monitoring.</span></div>
      <div class="action-item"><strong>Paused / disputed</strong><span class="list-meta">${fcdUi.escape(pausedCount)} should stay factual and controlled.</span></div>
      <div class="action-item"><strong>Portal route</strong><span class="list-meta">Use /verify and /portal for independent case validation and neutral debtor options.</span></div>
    `;
    document.getElementById("debtor-case-table").innerHTML = cases.length
      ? cases.map((item) => `
          <tr>
            <td><a href="/ui/invoices/${encodeURIComponent(item.invoice_id)}"><strong>${fcdUi.escape(item.invoice_id)}</strong></a></td>
            <td>${fcdUi.escape(item.debtor_type)}</td>
            <td>${fcdUi.escape(item.currency)} ${fcdUi.escape(item.outstanding_balance_gbp)}</td>
            <td><span class="pill ${fcdUi.stateTone(item.current_state)}">${fcdUi.escape(item.current_state)}</span></td>
            <td>${fcdUi.escape(item.next_step)}</td>
          </tr>
        `).join("")
      : '<tr><td colspan="5"><div class="empty-state">No debtor-facing cases match the filter.</div></td></tr>';
    document.getElementById("portal-readiness").innerHTML = `
      <div class="kv-row"><label>Verification route</label><div>/verify?case=&code=</div></div>
      <div class="kv-row"><label>Portal route</label><div>/portal?case=&code=</div></div>
      <div class="kv-row"><label>Neutral options</label><div>Pay, confirm date, already paid, propose plan, ask question, dispute, correct information.</div></div>
      <div class="kv-row"><label>Current filtered cases</label><div>${fcdUi.escape(cases.length)}</div></div>
    `;
  }

  document.getElementById("global-search").addEventListener("input", loadDebtorsPage);
  window.addEventListener("load", loadDebtorsPage);
</script>
"""
    return _render_shell(
        title="Debtors",
        subtitle="A debtor-oriented view that keeps portal, response, and segmentation work separate from core case triage.",
        active_nav="debtors",
        content=content,
        page_script=script,
        search_placeholder="Search debtor type, jurisdiction, case ID, or status...",
    )


def render_disputes_html() -> str:
    content = """
      <section class="cards-4" id="dispute-metrics"></section>

      <section class="split-layout">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Dispute and pause queue</h2>
              <div class="panel-subtle">Cases that should not progress without review.</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Status</th>
                  <th>Jurisdiction</th>
                  <th>Balance</th>
                  <th>Next step</th>
                </tr>
              </thead>
              <tbody id="dispute-table"></tbody>
            </table>
          </div>
        </div>
        <div class="spotlight">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Resolve restriction</h2>
                <div class="panel-subtle">Use live endpoints to resolve an open dispute or data-accuracy challenge.</div>
              </div>
            </div>
            <div class="form-grid">
              <label class="field">Invoice ID<input id="restriction-invoice-id" /></label>
              <label class="field">Resolution type
                <select id="restriction-type">
                  <option value="dispute">Debtor dispute</option>
                  <option value="accuracy">Data accuracy challenge</option>
                </select>
              </label>
              <label class="field">Creditor user ID<input id="restriction-user-id" value="USER-1" /></label>
              <label class="field" style="grid-column: 1 / -1;">Resolution notes<textarea id="restriction-notes">Reviewed and resolved with supporting evidence.</textarea></label>
            </div>
            <div class="inline-actions" style="margin-top: 14px;">
              <button id="resolve-restriction-button" type="button">Resolve restriction</button>
            </div>
            <div id="restriction-result" class="status-line" style="margin-top: 12px;"></div>
          </div>
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Selected restricted case</h2>
                <div class="panel-subtle">Drill into compliance and audit indicators before any further action.</div>
              </div>
            </div>
            <div id="dispute-detail" class="empty-state">Select a restricted case to inspect details.</div>
          </div>
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Restrictions guide</h2>
                <div class="panel-subtle">How the engine currently expects these cases to be handled.</div>
              </div>
            </div>
            <div id="dispute-guidance" class="action-list"></div>
          </div>
        </div>
      </section>
    """
    script = """
<script>
  const disputeState = { cases: [], selectedId: null };

  async function resolveRestriction() {
    const invoiceId = document.getElementById("restriction-invoice-id").value.trim();
    const mode = document.getElementById("restriction-type").value;
    const payload = {
      creditor_user_id: document.getElementById("restriction-user-id").value,
      resolution_notes: document.getElementById("restriction-notes").value
    };
    if (!invoiceId) {
      document.getElementById("restriction-result").textContent = "Invoice ID is required.";
      return;
    }
    document.getElementById("restriction-result").textContent = "Resolving restriction...";
    try {
      const endpoint = mode === "accuracy"
        ? `/invoices/${encodeURIComponent(invoiceId)}/debtor-actions/data-accuracy-challenge/resolve`
        : `/invoices/${encodeURIComponent(invoiceId)}/debtor-actions/dispute/resolve`;
      const result = await fcdUi.request(endpoint, "POST", payload);
      const detail = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}`);
      document.getElementById("restriction-result").innerHTML = `
        <div class="kv-list">
          <div class="kv-row"><label>Invoice</label><div>${fcdUi.escape(result.invoice_id)}</div></div>
          <div class="kv-row"><label>Resolution</label><div>${fcdUi.escape(result.status)}</div></div>
          <div class="kv-row"><label>Current state</label><div>${fcdUi.escape(detail.current_state)}</div></div>
          <div class="kv-row"><label>Outstanding</label><div>${fcdUi.escape(detail.currency)} ${fcdUi.escape(detail.outstanding_balance_gbp)}</div></div>
          <div class="kv-row"><label>Recovery restricted</label><div>${fcdUi.escape(String(result.recovery_restricted ?? false))}</div></div>
        </div>
      `;
      await loadDisputesPage(invoiceId);
    } catch (error) {
      document.getElementById("restriction-result").textContent = error.message;
    }
  }

  async function renderDisputeDetail(invoiceId) {
    if (!invoiceId) {
      document.getElementById("dispute-detail").innerHTML = "No restricted case selected.";
      return;
    }
    disputeState.selectedId = invoiceId;
    document.getElementById("restriction-invoice-id").value = invoiceId;
    const [detail, compliance, audit] = await Promise.all([
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}`),
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/compliance-ledger`),
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/audit-trail`)
    ]);
    const recentCompliance = (compliance.entries || []).slice(-3).reverse();
    const recentAudit = (audit.entries || []).slice(-3).reverse();
    document.getElementById("dispute-detail").innerHTML = `
      <div class="kv-list">
        <div class="kv-row"><label>Case</label><div>${fcdUi.escape(detail.invoice_id)}</div></div>
        <div class="kv-row"><label>Status</label><div><span class="pill ${fcdUi.stateTone(detail.current_state)}">${fcdUi.escape(detail.current_state)}</span></div></div>
        <div class="kv-row"><label>Outstanding</label><div>${fcdUi.escape(detail.currency)} ${fcdUi.escape(detail.outstanding_balance_gbp)}</div></div>
        <div class="kv-row"><label>Jurisdiction</label><div>${fcdUi.escape(detail.jurisdiction)}</div></div>
        <div class="kv-row"><label>Compliance events</label><div>${fcdUi.escape((compliance.entries || []).length)}</div></div>
        <div class="kv-row"><label>Audit entries</label><div>${fcdUi.escape((audit.entries || []).length)}</div></div>
      </div>
      <div class="action-list">
        <div class="action-item"><strong>Latest compliance</strong><span class="list-meta">${fcdUi.escape(recentCompliance.map((item) => item.event_type).join(", ") || "None")}</span></div>
        <div class="action-item"><strong>Latest audit</strong><span class="list-meta">${fcdUi.escape(recentAudit.map((item) => item.action).join(", ") || "None")}</span></div>
      </div>
      <div class="inline-actions">
        <a class="ghost-button" style="padding:11px 16px;" href="/ui/compliance?invoice=${encodeURIComponent(detail.invoice_id)}">Open compliance</a>
        <a class="ghost-button" style="padding:11px 16px;" href="/ui/invoices/${encodeURIComponent(detail.invoice_id)}">Open workspace</a>
      </div>
    `;
  }

  async function loadDisputesPage(preferredInvoiceId = null) {
    const payload = await fcdUi.request("/dashboard");
    const query = (document.getElementById("global-search").value || "").trim().toLowerCase();
    const cases = (payload.cases || []).filter((item) =>
      ["DISPUTED", "DISPUTE_REVIEW", "BREATHING_SPACE_PAUSE", "JURISDICTION_UNCERTAIN", "CLIENT_HANDOFF"].includes(item.current_state)
    ).filter((item) => {
      if (!query) return true;
      return [item.invoice_id, item.current_state, item.jurisdiction, item.next_step].join(" ").toLowerCase().includes(query);
    });
    disputeState.cases = cases;
    document.getElementById("dispute-metrics").innerHTML = [
      ["Restricted", cases.length, "Cases needing pause or review", "var(--red)"],
      ["Paused", cases.filter((item) => item.current_state === "BREATHING_SPACE_PAUSE").length, "Human or statutory pause", "var(--purple)"],
      ["Disputed", cases.filter((item) => String(item.current_state).includes("DISPUTE")).length, "Balance challenged", "var(--orange)"],
      ["Handoff", cases.filter((item) => item.current_state === "CLIENT_HANDOFF").length, "Client decision needed", "var(--cyan)"]
    ].map(([label, value, hint, color]) => fcdUi.metricCard(label, value, hint, color, [cases.length, value, cases.length, value, cases.length])).join("");
    document.getElementById("dispute-table").innerHTML = cases.length
      ? cases.map((item) => `
          <tr class="clickable-row ${item.invoice_id === disputeState.selectedId ? "selected-row" : ""}" data-dispute-id="${fcdUi.escape(item.invoice_id)}">
            <td><a href="/ui/compliance?invoice=${encodeURIComponent(item.invoice_id)}"><strong>${fcdUi.escape(item.invoice_id)}</strong></a></td>
            <td><span class="pill ${fcdUi.stateTone(item.current_state)}">${fcdUi.escape(item.current_state)}</span></td>
            <td>${fcdUi.escape(item.jurisdiction)}</td>
            <td>${fcdUi.escape(item.currency)} ${fcdUi.escape(item.outstanding_balance_gbp)}</td>
            <td>${fcdUi.escape(item.next_step)}</td>
          </tr>
        `).join("")
      : '<tr><td colspan="5"><div class="empty-state">No dispute or restricted cases match the current filter.</div></td></tr>';
    document.getElementById("dispute-guidance").innerHTML = `
      <div class="action-item"><strong>Accuracy challenges</strong><span class="list-meta">Freeze automated recovery and require creditor correction or evidence before resuming.</span></div>
      <div class="action-item"><strong>Disputes</strong><span class="list-meta">Use carve-outs where appropriate and keep the undisputed balance procedurally separate.</span></div>
      <div class="action-item"><strong>Breathing space / pauses</strong><span class="list-meta">Hold outreach and route to human review until the pause condition is cleared.</span></div>
    `;
    document.querySelectorAll("[data-dispute-id]").forEach((row) => {
      row.addEventListener("click", (event) => {
        event.preventDefault();
        renderDisputeDetail(row.getAttribute("data-dispute-id"));
      });
    });
    const preferred = preferredInvoiceId && cases.some((item) => item.invoice_id === preferredInvoiceId)
      ? preferredInvoiceId
      : (cases[0]?.invoice_id || null);
    await renderDisputeDetail(preferred);
  }

  document.getElementById("global-search").addEventListener("input", loadDisputesPage);
  document.getElementById("resolve-restriction-button").addEventListener("click", resolveRestriction);
  window.addEventListener("load", loadDisputesPage);
</script>
"""
    return _render_shell(
        title="Disputes",
        subtitle="A dedicated restrictions board for disputes, pauses, and client handoff decisions.",
        active_nav="disputes",
        content=content,
        page_script=script,
        search_placeholder="Search restricted cases, disputes, or handoff items...",
    )


def render_creditors_html() -> str:
    content = """
      <section class="cards-4" id="creditor-metrics"></section>

      <section class="cards-2">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Creditor posture</h2>
              <div class="panel-subtle">Commercial summary for managed invoices and likely next operator actions.</div>
            </div>
          </div>
          <div id="creditor-posture" class="action-list"></div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Priority creditor queue</h2>
              <div class="panel-subtle">Cases nearing formal action or handoff.</div>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Status</th>
                  <th>Balance</th>
                  <th>Next step</th>
                </tr>
              </thead>
              <tbody id="creditor-queue"></tbody>
            </table>
          </div>
        </div>
      </section>
    """
    script = """
<script>
  async function loadCreditorsPage() {
    const payload = await fcdUi.request("/dashboard");
    const query = (document.getElementById("global-search").value || "").trim().toLowerCase();
    const cases = (payload.cases || []).filter((item) => {
      if (!query) return true;
      return [item.invoice_id, item.current_state, item.jurisdiction, item.next_step, item.outstanding_balance_gbp]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
    const totalOutstanding = payload.metrics?.total_outstanding_gbp || "0";
    const formal = cases.filter((item) => ["FORMAL_NOTICE", "PRE_ACTION_PROTOCOL", "CLIENT_HANDOFF"].includes(item.current_state));
    document.getElementById("creditor-metrics").innerHTML = [
      ["Managed Cases", cases.length, "Total creditor-side live cases", "var(--primary)", [cases.length, formal.length, cases.length, formal.length, cases.length]],
      ["Outstanding", fcdUi.formatMoney(totalOutstanding), "Aggregate live exposure", "var(--green)", [totalOutstanding, totalOutstanding, Number(totalOutstanding) * 0.96, totalOutstanding, Number(totalOutstanding) * 1.02]],
      ["Formal Stage", formal.length, "Cases in formal or handoff stages", "var(--orange)", [formal.length, payload.metrics?.handoff_ready || 0, formal.length, payload.metrics?.overdue || 0, formal.length]],
      ["Blocked", payload.metrics?.blocked_or_paused || 0, "Cases held by compliance or dispute", "var(--red)", [payload.metrics?.blocked_or_paused || 0, formal.length, payload.metrics?.blocked_or_paused || 0, formal.length, payload.metrics?.blocked_or_paused || 0]]
    ].map(([label, value, hint, color, series]) => fcdUi.metricCard(label, value, hint, color, series)).join("");
    document.getElementById("creditor-posture").innerHTML = `
      <div class="action-item"><strong>Commercial exposure</strong><span class="list-meta">${fcdUi.escape(cases.length)} cases currently represent ${fcdUi.escape(fcdUi.formatMoney(totalOutstanding))} in live tracked balance.</span></div>
      <div class="action-item"><strong>Formal queue</strong><span class="list-meta">${fcdUi.escape(formal.length)} cases are ready for tighter operator control or client handoff review.</span></div>
      <div class="action-item"><strong>Resolution path</strong><span class="list-meta">Use payment plans, settlements, and disputes handling before defaulting to handoff.</span></div>
    `;
    document.getElementById("creditor-queue").innerHTML = formal.length
      ? formal.map((item) => `
          <tr>
            <td><a href="/ui/invoices/${encodeURIComponent(item.invoice_id)}"><strong>${fcdUi.escape(item.invoice_id)}</strong></a></td>
            <td><span class="pill ${fcdUi.stateTone(item.current_state)}">${fcdUi.escape(item.current_state)}</span></td>
            <td>${fcdUi.escape(item.currency)} ${fcdUi.escape(item.outstanding_balance_gbp)}</td>
            <td>${fcdUi.escape(item.next_step)}</td>
          </tr>
        `).join("")
      : '<tr><td colspan="4"><div class="empty-state">No formal-stage cases are currently queued.</div></td></tr>';
  }

  document.getElementById("global-search").addEventListener("input", loadCreditorsPage);
  window.addEventListener("load", loadCreditorsPage);
</script>
"""
    return _render_shell(
        title="Creditors",
        subtitle="A creditor-facing summary page for exposure, formal-stage routing, and managed next steps.",
        active_nav="creditors",
        content=content,
        page_script=script,
        search_placeholder="Search creditor-facing cases, balances, and formal stages...",
    )


def render_reports_html() -> str:
    content = """
      <section class="cards-4" id="reports-metrics"></section>

      <section class="cards-2">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Operational report cards</h2>
              <div class="panel-subtle">High-level performance snapshots from the live engine data.</div>
            </div>
          </div>
          <div id="report-cards" class="action-list"></div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Queue distribution</h2>
              <div class="panel-subtle">Current case mix by status.</div>
            </div>
          </div>
          <div id="report-status-mix" class="stat-chip-grid"></div>
        </div>
      </section>

      <section class="cards-2">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Readiness and controls</h2>
              <div class="panel-subtle">Startup and deployment report output from the live API.</div>
            </div>
          </div>
          <div id="report-readiness" class="kv-list"></div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Retention policy snapshot</h2>
              <div class="panel-subtle">Current storage and retention controls.</div>
            </div>
          </div>
          <div id="report-retention" class="kv-list"></div>
        </div>
      </section>

      <section class="cards-2">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Environment checks</h2>
              <div class="panel-subtle">Warnings, severities, and runbook actions from startup validation.</div>
            </div>
          </div>
          <div id="report-readiness-checks" class="action-list"></div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Policy controls</h2>
              <div class="panel-subtle">Retention variants and managed storage roots in the active policy.</div>
            </div>
          </div>
          <div id="report-retention-controls" class="action-list"></div>
        </div>
      </section>
    """
    script = """
<script>
  async function loadReportsPage() {
    const [payload, readiness, retention] = await Promise.all([
      fcdUi.request("/dashboard"),
      fcdUi.request("/deployment/startup-config-validation/report"),
      fcdUi.request("/data-retention-policy")
    ]);
    const metrics = payload.metrics || {};
    const query = (document.getElementById("global-search").value || "").trim().toLowerCase();
    const cases = (payload.cases || []).filter((item) => {
      if (!query) return true;
      return [item.invoice_id, item.current_state, item.jurisdiction, item.debtor_type, item.next_step]
        .join(" ")
        .toLowerCase()
        .includes(query);
    });
    const statusCounts = fcdUi.statusCounts(cases);
    const recent = payload.recent_activity || [];
    document.getElementById("reports-metrics").innerHTML = [
      ["Active Cases", metrics.active_cases || 0, "Operational workload", "var(--primary)", [metrics.active_cases || 0, metrics.overdue || 0, metrics.active_cases || 0, recent.length, metrics.active_cases || 0]],
      ["Overdue", metrics.overdue || 0, "Past due open cases", "var(--orange)", [metrics.due_today || 0, metrics.overdue || 0, metrics.overdue || 0, recent.length, metrics.overdue || 0]],
      ["Outstanding", fcdUi.formatMoney(metrics.total_outstanding_gbp || 0), "Tracked exposure", "var(--green)", [metrics.total_outstanding_gbp || 0, metrics.total_outstanding_gbp || 0, Number(metrics.total_outstanding_gbp || 0) * 0.98, metrics.total_outstanding_gbp || 0, Number(metrics.total_outstanding_gbp || 0) * 1.01]],
      ["Recent Activity", recent.length, "Latest engine activity count", "var(--purple)", [recent.length, metrics.blocked_or_paused || 0, recent.length, metrics.handoff_ready || 0, recent.length]]
    ].map(([label, value, hint, color, series]) => fcdUi.metricCard(label, value, hint, color, series)).join("");
    document.getElementById("report-cards").innerHTML = `
      <div class="action-item"><strong>Overdue workload</strong><span class="list-meta">${fcdUi.escape(metrics.overdue || 0)} overdue case(s) require current follow-up.</span></div>
      <div class="action-item"><strong>Blocked / paused</strong><span class="list-meta">${fcdUi.escape(metrics.blocked_or_paused || 0)} case(s) are being held by compliance or dispute rules.</span></div>
      <div class="action-item"><strong>Handoff readiness</strong><span class="list-meta">${fcdUi.escape(metrics.handoff_ready || 0)} case(s) are prepared for client review or procedural handoff.</span></div>
    `;
    const entries = Object.entries(statusCounts);
    document.getElementById("report-status-mix").innerHTML = entries.length
      ? entries.map(([label, count]) => `
          <div class="stat-chip">
            <strong>${fcdUi.escape(label)}</strong>
            <span class="stat-chip-count">${fcdUi.escape(count)}</span>
          </div>
        `).join("")
      : '<div class="empty-state">No reportable case data available.</div>';
    document.getElementById("report-readiness").innerHTML = `
      <div class="kv-row"><label>Environment</label><div>${fcdUi.escape(readiness.environment || "")}</div></div>
      <div class="kv-row"><label>Ready</label><div>${fcdUi.escape(String(readiness.ready))}</div></div>
      <div class="kv-row"><label>Total checks</label><div>${fcdUi.escape(readiness.summary?.total_checks || 0)}</div></div>
      <div class="kv-row"><label>Failed checks</label><div>${fcdUi.escape(readiness.summary?.failed_checks || 0)}</div></div>
      <div class="kv-row"><label>Warnings</label><div>${fcdUi.escape(readiness.summary?.warning_count || 0)}</div></div>
      <div class="kv-row"><label>Rate limit</label><div>${fcdUi.escape(readiness.rate_limit_per_minute || "")}</div></div>
      <div class="kv-row"><label>Manifest key</label><div>${fcdUi.escape(readiness.manifest_key_id || "")}</div></div>
    `;
    const failedChecks = (readiness.checks || []).filter((check) => !check.passed);
    const runbookSteps = readiness.runbook?.steps || [];
    document.getElementById("report-readiness-checks").innerHTML = [
      ...failedChecks.map((check) => `
        <div class="action-item">
          <strong>${fcdUi.escape(check.check)}</strong>
          <span class="list-meta">${fcdUi.escape(`${check.severity} | ${check.detail}`)}</span>
        </div>
      `),
      ...runbookSteps.map((step) => `
        <div class="action-item">
          <strong>${fcdUi.escape(`Runbook step ${step.step}: ${step.title}`)}</strong>
          <span class="list-meta">${fcdUi.escape(`${step.completed ? "complete" : "pending"} | ${step.detail}`)}</span>
        </div>
      `)
    ].join("") || '<div class="empty-state">No readiness warnings or runbook steps available.</div>';
    const policy = retention.policy || {};
    document.getElementById("report-retention").innerHTML = `
      <div class="kv-row"><label>Retention days</label><div>${fcdUi.escape(policy.retention_days || "")}</div></div>
      <div class="kv-row"><label>Disposal scope</label><div>${fcdUi.escape(policy.disposal_scope || "")}</div></div>
      <div class="kv-row"><label>Immutable records</label><div>${fcdUi.escape(String(policy.immutable_records_retained))}</div></div>
      <div class="kv-row"><label>Legal hold clearance</label><div>${fcdUi.escape(String(policy.requires_legal_hold_clearance))}</div></div>
    `;
    const variants = Object.entries(policy.retention_variants || {});
    const storageRoots = policy.managed_storage_roots || [];
    document.getElementById("report-retention-controls").innerHTML = [
      ...variants.map(([label, value]) => `
        <div class="action-item">
          <strong>${fcdUi.escape(label)}</strong>
          <span class="list-meta">${fcdUi.escape(String(value))}</span>
        </div>
      `),
      ...storageRoots.map((root) => `
        <div class="action-item">
          <strong>Managed storage root</strong>
          <span class="list-meta">${fcdUi.escape(root)}</span>
        </div>
      `)
    ].join("") || '<div class="empty-state">No retention variants configured.</div>';
  }

  document.getElementById("global-search").addEventListener("input", loadReportsPage);
  window.addEventListener("load", loadReportsPage);
</script>
"""
    return _render_shell(
        title="Reports",
        subtitle="Lightweight operational reporting with live queue summaries and trend cards.",
        active_nav="reports",
        content=content,
        page_script=script,
        search_placeholder="Search report data, statuses, and activity...",
    )


def render_operations_html() -> str:
    content = """
      <section class="cards-2">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Create case</h2>
              <div class="panel-subtle">Spin up a new case and drop directly into the workspace.</div>
            </div>
          </div>
          <div class="form-grid">
            <label class="field">Invoice ID<input id="invoice-id" value="inv-ui-1" /></label>
            <label class="field">Currency<input id="currency" value="GBP" /></label>
            <label class="field">Principal<input id="principal" value="1200" /></label>
            <label class="field">Issue date<input id="issue-date" value="2026-01-01" /></label>
            <label class="field">Due date<input id="due-date" value="2026-01-31" /></label>
            <label class="field">Jurisdiction
              <select id="jurisdiction">
                <option>ENGLAND_WALES</option>
                <option>SCOTLAND</option>
                <option>NORTHERN_IRELAND</option>
              </select>
            </label>
            <label class="field">Debtor type
              <select id="debtor-type">
                <option>LIMITED</option>
                <option>SOLE_TRADER</option>
                <option>INDIVIDUAL</option>
              </select>
            </label>
          </div>
          <div class="inline-actions" style="margin-top: 14px;">
            <button id="create-case">Create invoice</button>
            <button id="open-workspace" class="secondary-button">Open workspace</button>
          </div>
          <div id="operations-status" class="status-line" style="margin-top: 12px;"></div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Quick actions</h2>
              <div class="panel-subtle">Jump into the busiest operator actions without overloading one screen.</div>
            </div>
          </div>
          <div class="action-grid">
            <a class="card" href="/ui/cases"><strong>Review case board</strong><div class="metric-hint">Triage live cases and pick the next move.</div></a>
            <a class="card" href="/ui/compliance"><strong>Review compliance</strong><div class="metric-hint">Audit trail, rule state, and restrictions.</div></a>
            <a class="card" id="bundle-link" href="#"><strong>Download evidence bundle</strong><div class="metric-hint">Generates the latest PDF bundle for a case.</div></a>
            <a class="card" href="/dashboard"><strong>Refresh engine data</strong><div class="metric-hint">Raw dashboard data feed for integrations.</div></a>
          </div>
        </div>
      </section>

      <section class="cards-2">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Create communication</h2>
              <div class="panel-subtle">Send or queue a case communication using the live engine endpoint.</div>
            </div>
          </div>
          <div class="form-grid">
            <label class="field">Invoice ID<input id="comm-invoice-id" value="inv-ui-1" /></label>
            <label class="field">Channel
              <select id="comm-channel">
                <option>EMAIL</option>
                <option>LETTER</option>
                <option>SMS</option>
                <option>PHONE</option>
              </select>
            </label>
            <label class="field">Recipient<input id="comm-recipient" value="accounts@example.com" /></label>
            <label class="field">Subject<input id="comm-subject" value="Invoice reminder" /></label>
            <label class="field" style="grid-column: 1 / -1;">Summary<textarea id="comm-summary">Friendly reminder for the current outstanding balance.</textarea></label>
          </div>
          <div class="inline-actions" style="margin-top: 14px;">
            <button id="create-communication" type="button">Create communication</button>
          </div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Communication result</h2>
              <div class="panel-subtle">The latest response from the communications endpoint.</div>
            </div>
          </div>
          <div id="communication-result" class="empty-state">No communication submitted yet.</div>
          <div style="margin-top: 14px;">
            <h3 style="margin:0 0 10px;">Recent communication activity</h3>
            <div id="communication-history" class="action-list">
              <div class="empty-state">No communication activity yet.</div>
            </div>
          </div>
        </div>
      </section>

      <section class="cards-3">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h3>Payment plan actions</h3>
              <div class="panel-subtle">Formalise a promise-to-pay schedule and optionally record instalment receipts.</div>
            </div>
          </div>
          <div class="form-grid">
            <label class="field">Invoice ID<input id="plan-invoice-id" value="inv-ui-1" /></label>
            <label class="field">Proposed by<input id="plan-proposed-by" value="USER-1" /></label>
            <label class="field">Installment amount<input id="plan-amount" value="300" /></label>
            <label class="field">Installment count<input id="plan-count" value="4" /></label>
            <label class="field">First due date<input id="plan-first-due-date" value="2026-02-15" /></label>
            <label class="field">Frequency days<input id="plan-frequency-days" value="30" /></label>
            <label class="field" style="grid-column: 1 / -1;">Notes<textarea id="plan-notes">Structured payment plan proposed through operations.</textarea></label>
          </div>
          <div class="inline-actions" style="margin-top: 14px;">
            <button id="create-payment-plan" type="button">Create payment plan</button>
          </div>
          <div id="payment-plan-result" class="status-line" style="margin-top: 12px;"></div>
          <div style="margin-top: 14px;">
            <h3 style="margin:0 0 10px;">Payment plan history</h3>
            <div id="payment-plan-history" class="action-list">
              <div class="empty-state">No payment plans recorded yet.</div>
            </div>
          </div>
          <div style="margin-top: 18px;">
            <h3 style="margin:0 0 10px;">Record installment payment</h3>
            <div class="form-grid">
              <label class="field">Plan<select id="plan-payment-plan-id"></select></label>
              <label class="field">Installment<select id="plan-payment-installment-id"></select></label>
              <label class="field">Amount<input id="plan-payment-amount" value="300" /></label>
              <label class="field">Recorded by<input id="plan-payment-recorded-by" value="USER-1" /></label>
            </div>
            <div class="inline-actions" style="margin-top: 14px;">
              <button id="record-plan-payment" class="secondary-button" type="button">Record plan payment</button>
            </div>
            <div id="plan-payment-result" class="status-line" style="margin-top: 12px;"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-header">
            <div>
              <h3>Settlement actions</h3>
              <div class="panel-subtle">Create full-and-final offers and record acceptance from creditor or debtor.</div>
            </div>
          </div>
          <div class="form-grid">
            <label class="field">Invoice ID<input id="offer-invoice-id" value="inv-ui-1" /></label>
            <label class="field">Offered by<input id="offer-offered-by" value="USER-1" /></label>
            <label class="field">Offer amount<input id="offer-amount" value="950" /></label>
            <label class="field">Expiry date<input id="offer-expiry-date" value="2026-02-21" /></label>
            <label class="field" style="grid-column: 1 / -1;">Notes<textarea id="offer-notes">Time-bound full and final settlement proposal.</textarea></label>
          </div>
          <div class="inline-actions" style="margin-top: 14px;">
            <button id="create-settlement-offer" type="button">Create settlement offer</button>
          </div>
          <div id="settlement-offer-result" class="status-line" style="margin-top: 12px;"></div>
          <div style="margin-top: 14px;">
            <h3 style="margin:0 0 10px;">Settlement history</h3>
            <div id="settlement-offer-history" class="action-list">
              <div class="empty-state">No settlement offers recorded yet.</div>
            </div>
          </div>
          <div style="margin-top: 18px;">
            <h3 style="margin:0 0 10px;">Accept settlement offer</h3>
            <div class="form-grid">
              <label class="field">Offer<select id="offer-accept-id"></select></label>
              <label class="field">Accepted by<input id="offer-accepted-by" value="USER-1" /></label>
              <label class="field">Role
                <select id="offer-accepter-role">
                  <option>CREDITOR</option>
                  <option>DEBTOR</option>
                </select>
              </label>
            </div>
            <div class="inline-actions" style="margin-top: 14px;">
              <button id="accept-settlement-offer" class="secondary-button" type="button">Accept settlement</button>
            </div>
            <div id="settlement-acceptance-result" class="status-line" style="margin-top: 12px;"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-header"><h3>Evidence and guardrails</h3></div>
          <div class="action-list">
            <div class="action-item"><strong>Upload artifacts</strong><span class="list-meta">Contracts, invoices, proof-of-supply, or correspondence.</span></div>
            <div class="action-item"><strong>Generate manifest</strong><span class="list-meta">Signed JSON/PDF evidence ledger manifest.</span></div>
            <div class="action-item"><strong>Compile handoff pack</strong><span class="list-meta">Create a client-ready court handoff bundle.</span></div>
          </div>
          <div class="note-box" style="margin-top: 14px;">
            This screen intentionally focuses on intake and actionable resolution controls. Detailed compliance, audit, and case review stay on their own pages to keep the operator flow less busy.
          </div>
        </div>
      </section>
    """
    script = """
<script>
  function currentInvoiceId() {
    return document.getElementById("invoice-id").value.trim();
  }

  function syncActionInvoiceId() {
    const invoiceId = currentInvoiceId();
    document.getElementById("comm-invoice-id").value = invoiceId;
    document.getElementById("plan-invoice-id").value = invoiceId;
    document.getElementById("offer-invoice-id").value = invoiceId;
    syncBundleLink();
    refreshResolutionPanels().catch((error) => fcdUi.setStatus("operations-status", error.message));
  }

  async function renderCommunicationFeedback(invoiceId, result = null) {
    if (!invoiceId) {
      document.getElementById("communication-result").textContent = "Invoice ID is required.";
      return;
    }
    const detail = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}`);
    const list = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/communications`);
    const communications = list.communications || [];
    const latest = result
      ? communications.find((item) => item.communication_id === result.communication_id) || communications.slice(-1)[0] || null
      : communications.slice(-1)[0] || null;
    document.getElementById("communication-result").innerHTML = latest ? `
      <div class="kv-list">
        <div class="kv-row"><label>Invoice</label><div>${fcdUi.escape(invoiceId)}</div></div>
        <div class="kv-row"><label>Outstanding</label><div>${fcdUi.escape(detail.currency)} ${fcdUi.escape(detail.outstanding_balance_gbp)}</div></div>
        <div class="kv-row"><label>Communication ID</label><div>${fcdUi.escape(latest.communication_id)}</div></div>
        <div class="kv-row"><label>Channel</label><div>${fcdUi.escape(latest.channel)}</div></div>
        <div class="kv-row"><label>Recipient</label><div>${fcdUi.escape(latest.recipient)}</div></div>
        <div class="kv-row"><label>State</label><div>${fcdUi.escape(latest.latest_state)}</div></div>
        <div class="kv-row"><label>Locked balance</label><div>${fcdUi.escape(result?.locked_outstanding_balance_gbp || "")}</div></div>
      </div>
    ` : '<div class="empty-state">No communication submitted yet.</div>';
    document.getElementById("communication-history").innerHTML = communications.length ? communications.slice().reverse().slice(0, 3).map((item) => `
      <div class="action-item">
        <strong>${fcdUi.escape(item.subject)}</strong>
        <span class="list-meta">${fcdUi.escape(`${item.channel} | ${item.latest_state} | ${item.created_at}`)}</span>
      </div>
    `).join("") : '<div class="empty-state">No communication activity yet.</div>';
  }

  function syncPaymentSelectors(plans) {
    const planSelect = document.getElementById("plan-payment-plan-id");
    const installmentSelect = document.getElementById("plan-payment-installment-id");
    planSelect.innerHTML = plans.length
      ? plans.map((plan) => `<option value="${fcdUi.escape(plan.plan_id)}">${fcdUi.escape(`${plan.plan_id} | ${plan.status}`)}</option>`).join("")
      : "";
    const selectedPlan = plans.find((plan) => plan.plan_id === planSelect.value) || plans[0] || null;
    installmentSelect.innerHTML = selectedPlan
      ? (selectedPlan.installments || []).map((item) => `<option value="${fcdUi.escape(item.installment_id)}">${fcdUi.escape(`#${item.sequence_number} | ${item.due_date} | ${item.amount_gbp}`)}</option>`).join("")
      : "";
    if (selectedPlan && selectedPlan.installment_amount_gbp) {
      document.getElementById("plan-payment-amount").value = selectedPlan.installment_amount_gbp;
    }
  }

  function syncOfferSelectors(offers) {
    const offerSelect = document.getElementById("offer-accept-id");
    offerSelect.innerHTML = offers.length
      ? offers.map((offer) => `<option value="${fcdUi.escape(offer.offer_id)}">${fcdUi.escape(`${offer.offer_id} | ${offer.status} | ${offer.offered_amount_gbp}`)}</option>`).join("")
      : "";
  }

  async function refreshResolutionPanels() {
    const invoiceId = currentInvoiceId();
    if (!invoiceId) return;
    try {
      const [plansPayload, offersPayload] = await Promise.all([
        fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/resolution/payment-plans`),
        fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/resolution/settlement-offers`)
      ]);
      const plans = plansPayload.plans || [];
      const offers = offersPayload.offers || [];
      document.getElementById("payment-plan-history").innerHTML = plans.length
        ? plans.slice().reverse().slice(0, 3).map((plan) => `
          <div class="action-item">
            <strong>${fcdUi.escape(plan.plan_id)}</strong>
            <span class="list-meta">${fcdUi.escape(`${plan.status} | ${plan.installment_count} installments | remaining ${plan.remaining_amount_gbp}`)}</span>
          </div>
        `).join("")
        : '<div class="empty-state">No payment plans recorded yet.</div>';
      document.getElementById("settlement-offer-history").innerHTML = offers.length
        ? offers.slice().reverse().slice(0, 3).map((offer) => `
          <div class="action-item">
            <strong>${fcdUi.escape(offer.offer_id)}</strong>
            <span class="list-meta">${fcdUi.escape(`${offer.status} | ${offer.offered_amount_gbp} | expires ${offer.expiry_date}`)}</span>
          </div>
        `).join("")
        : '<div class="empty-state">No settlement offers recorded yet.</div>';
      syncPaymentSelectors(plans);
      syncOfferSelectors(offers);
    } catch (error) {
      document.getElementById("payment-plan-history").innerHTML = `<div class="empty-state">${fcdUi.escape(error.message)}</div>`;
      document.getElementById("settlement-offer-history").innerHTML = `<div class="empty-state">${fcdUi.escape(error.message)}</div>`;
    }
  }

  async function createPaymentPlan() {
    const invoiceId = document.getElementById("plan-invoice-id").value.trim();
    fcdUi.setStatus("operations-status", "Creating payment plan...");
    try {
      const result = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/resolution/payment-plans`, "POST", {
        proposed_by: document.getElementById("plan-proposed-by").value,
        installment_amount_gbp: document.getElementById("plan-amount").value,
        installment_count: Number(document.getElementById("plan-count").value),
        first_due_date: document.getElementById("plan-first-due-date").value,
        frequency_days: Number(document.getElementById("plan-frequency-days").value),
        notes: document.getElementById("plan-notes").value
      });
      document.getElementById("payment-plan-result").innerHTML = `
        <div class="kv-list">
          <div class="kv-row"><label>Invoice</label><div>${fcdUi.escape(result.invoice_id)}</div></div>
          <div class="kv-row"><label>Plan</label><div>${fcdUi.escape(result.plan_id)}</div></div>
          <div class="kv-row"><label>Status</label><div>${fcdUi.escape(result.status)}</div></div>
          <div class="kv-row"><label>Installments</label><div>${fcdUi.escape(result.installment_count)}</div></div>
          <div class="kv-row"><label>Chasers paused</label><div>${fcdUi.escape(String(result.chasers_paused))}</div></div>
        </div>
      `;
      await refreshResolutionPanels();
      fcdUi.setStatus("operations-status", `Payment plan created for ${result.invoice_id}`);
    } catch (error) {
      document.getElementById("payment-plan-result").textContent = error.message;
      fcdUi.setStatus("operations-status", error.message);
    }
  }

  async function recordPlanPayment() {
    const invoiceId = document.getElementById("plan-invoice-id").value.trim();
    const planId = document.getElementById("plan-payment-plan-id").value;
    const installmentId = document.getElementById("plan-payment-installment-id").value;
    fcdUi.setStatus("operations-status", "Recording payment-plan payment...");
    try {
      const result = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/resolution/payment-plans/${encodeURIComponent(planId)}/payments`, "POST", {
        installment_id: installmentId,
        amount_gbp: document.getElementById("plan-payment-amount").value,
        recorded_by: document.getElementById("plan-payment-recorded-by").value
      });
      document.getElementById("plan-payment-result").innerHTML = `
        <div class="kv-list">
          <div class="kv-row"><label>Plan</label><div>${fcdUi.escape(result.plan_id)}</div></div>
          <div class="kv-row"><label>Payment</label><div>${fcdUi.escape(result.payment_id)}</div></div>
          <div class="kv-row"><label>Amount</label><div>${fcdUi.escape(result.amount_gbp)}</div></div>
          <div class="kv-row"><label>Recorded at</label><div>${fcdUi.escape(result.recorded_at)}</div></div>
        </div>
      `;
      await refreshResolutionPanels();
      fcdUi.setStatus("operations-status", `Payment-plan payment recorded for ${result.invoice_id}`);
    } catch (error) {
      document.getElementById("plan-payment-result").textContent = error.message;
      fcdUi.setStatus("operations-status", error.message);
    }
  }

  async function createSettlementOffer() {
    const invoiceId = document.getElementById("offer-invoice-id").value.trim();
    fcdUi.setStatus("operations-status", "Creating settlement offer...");
    try {
      const result = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/resolution/settlement-offers`, "POST", {
        offered_by: document.getElementById("offer-offered-by").value,
        offered_amount_gbp: document.getElementById("offer-amount").value,
        expiry_date: document.getElementById("offer-expiry-date").value,
        notes: document.getElementById("offer-notes").value
      });
      document.getElementById("settlement-offer-result").innerHTML = `
        <div class="kv-list">
          <div class="kv-row"><label>Invoice</label><div>${fcdUi.escape(result.invoice_id)}</div></div>
          <div class="kv-row"><label>Offer</label><div>${fcdUi.escape(result.offer_id)}</div></div>
          <div class="kv-row"><label>Amount</label><div>${fcdUi.escape(result.offered_amount_gbp)}</div></div>
          <div class="kv-row"><label>Expires</label><div>${fcdUi.escape(result.expiry_date)}</div></div>
          <div class="kv-row"><label>Status</label><div>${fcdUi.escape(result.status)}</div></div>
        </div>
      `;
      await refreshResolutionPanels();
      fcdUi.setStatus("operations-status", `Settlement offer created for ${result.invoice_id}`);
    } catch (error) {
      document.getElementById("settlement-offer-result").textContent = error.message;
      fcdUi.setStatus("operations-status", error.message);
    }
  }

  async function acceptSettlementOffer() {
    const invoiceId = document.getElementById("offer-invoice-id").value.trim();
    const offerId = document.getElementById("offer-accept-id").value;
    fcdUi.setStatus("operations-status", "Accepting settlement offer...");
    try {
      const result = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/resolution/settlement-offers/${encodeURIComponent(offerId)}/accept`, "POST", {
        accepted_by: document.getElementById("offer-accepted-by").value,
        accepter_role: document.getElementById("offer-accepter-role").value
      });
      document.getElementById("settlement-acceptance-result").innerHTML = `
        <div class="kv-list">
          <div class="kv-row"><label>Offer</label><div>${fcdUi.escape(result.offer_id)}</div></div>
          <div class="kv-row"><label>Acceptance</label><div>${fcdUi.escape(result.acceptance_id)}</div></div>
          <div class="kv-row"><label>Role</label><div>${fcdUi.escape(result.accepter_role)}</div></div>
          <div class="kv-row"><label>Finalized</label><div>${fcdUi.escape(String(result.finalized))}</div></div>
        </div>
      `;
      await refreshResolutionPanels();
      fcdUi.setStatus("operations-status", `Settlement acceptance recorded for ${result.invoice_id}`);
    } catch (error) {
      document.getElementById("settlement-acceptance-result").textContent = error.message;
      fcdUi.setStatus("operations-status", error.message);
    }
  }

  async function createCase() {
    fcdUi.setStatus("operations-status", "Creating invoice...");
    try {
      const payload = {
        invoice_id: currentInvoiceId(),
        currency: document.getElementById("currency").value,
        principal_amount: document.getElementById("principal").value,
        issue_date: document.getElementById("issue-date").value,
        due_date: document.getElementById("due-date").value,
        jurisdiction: document.getElementById("jurisdiction").value,
        debtor_type: document.getElementById("debtor-type").value
      };
      const result = await fcdUi.request("/invoices", "POST", payload);
      fcdUi.setStatus("operations-status", `Created ${result.invoice_id}`);
      syncActionInvoiceId();
      await renderCommunicationFeedback(result.invoice_id);
      await refreshResolutionPanels();
    } catch (error) {
      fcdUi.setStatus("operations-status", error.message);
    }
  }

  function openWorkspace() {
    const invoiceId = currentInvoiceId();
    if (!invoiceId) return;
    window.location.href = `/ui/invoices/${encodeURIComponent(invoiceId)}`;
  }

  function syncBundleLink() {
    const invoiceId = currentInvoiceId();
    document.getElementById("bundle-link").href = invoiceId
      ? `/invoices/${encodeURIComponent(invoiceId)}/evidence-bundle?output_filename=${encodeURIComponent(invoiceId + "_bundle.pdf")}`
      : "#";
  }

  async function createCommunication() {
    const invoiceId = document.getElementById("comm-invoice-id").value.trim();
    fcdUi.setStatus("operations-status", "Creating communication...");
    try {
      const result = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/communications`, "POST", {
        channel: document.getElementById("comm-channel").value,
        recipient: document.getElementById("comm-recipient").value,
        subject: document.getElementById("comm-subject").value,
        body_summary: document.getElementById("comm-summary").value,
        automated: true
      });
      await renderCommunicationFeedback(invoiceId, result);
      fcdUi.setStatus("operations-status", `Communication created for ${result.invoice_id}`);
    } catch (error) {
      document.getElementById("communication-result").textContent = error.message;
      fcdUi.setStatus("operations-status", error.message);
    }
  }

  document.getElementById("create-case").addEventListener("click", createCase);
  document.getElementById("open-workspace").addEventListener("click", openWorkspace);
  document.getElementById("create-communication").addEventListener("click", createCommunication);
  document.getElementById("create-payment-plan").addEventListener("click", createPaymentPlan);
  document.getElementById("record-plan-payment").addEventListener("click", recordPlanPayment);
  document.getElementById("create-settlement-offer").addEventListener("click", createSettlementOffer);
  document.getElementById("accept-settlement-offer").addEventListener("click", acceptSettlementOffer);
  document.getElementById("plan-payment-plan-id").addEventListener("change", refreshResolutionPanels);
  document.getElementById("invoice-id").addEventListener("input", syncActionInvoiceId);
  window.addEventListener("load", syncActionInvoiceId);
</script>
"""
    return _render_shell(
        title="Operations",
        subtitle="Focused intake and jump-off actions with the color direction from your target design.",
        active_nav="operations",
        content=content,
        page_script=script,
        search_placeholder="Search actions, invoices, or jump to a case ID...",
    )


def render_compliance_html() -> str:
    content = """
      <section class="cards-4" id="compliance-metrics"></section>

      <section class="split-layout">
        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Compliance ledger</h2>
              <div class="panel-subtle">Operational restrictions, disputes, and rule-bound case history.</div>
            </div>
            <select id="compliance-case-picker"></select>
          </div>
          <div id="compliance-summary" class="good-box" style="margin-bottom: 14px;">Loading compliance data...</div>
          <div id="compliance-list" class="log-list"></div>
        </div>
        <div class="spotlight">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Compliance actions</h2>
                <div class="panel-subtle">Run case-health, devil's-advocate, and legal-safety checks from the UI.</div>
              </div>
            </div>
            <div class="inline-actions">
              <button id="run-case-health" type="button">Run case health</button>
              <button id="run-devils-advocate" class="secondary-button" type="button">Run devil's advocate</button>
              <button id="run-legal-gate" class="secondary-button" type="button">Confirm legal gate</button>
            </div>
            <div id="compliance-action-result" class="status-line" style="margin-top: 12px;"></div>
          </div>
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Selected case intelligence</h2>
                <div class="panel-subtle">Quick drill-down on restriction, evidence posture, and latest recorded actions.</div>
              </div>
            </div>
            <div id="compliance-detail" class="empty-state">Loading case intelligence...</div>
          </div>
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>ACE audit trail</h2>
                <div class="panel-subtle">Append-only log for operational accountability.</div>
              </div>
            </div>
            <div id="audit-list" class="log-list"></div>
          </div>
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Rule pack snapshot</h2>
                <div class="panel-subtle">Active rule version and routing context.</div>
              </div>
            </div>
            <div id="rule-pack-card" class="empty-state">Loading rule-pack information...</div>
          </div>
        </div>
      </section>
    """
    script = """
<script>
  const complianceState = { dashboard: null, selectedId: null };

  function renderComplianceMetrics(item) {
    const cards = [
      ["Case", item?.invoice_id || "-", "Current invoice", "var(--primary)"],
      ["State", item?.current_state || "-", "Workflow position", "var(--orange)"],
      ["Outstanding", item ? `${item.currency} ${item.outstanding_balance_gbp}` : "£0.00", "Live debtor balance", "var(--green)"],
      ["Chain Valid", item ? String(item.chain_valid) : "-", "Tamper-evident chain", "var(--purple)"]
    ];
    document.getElementById("compliance-metrics").innerHTML = cards.map(([label, value, hint, color]) => `
      <div class="card metric-card" style="--accent:${color}">
        <div class="metric-label">${fcdUi.escape(label)}</div>
        <div class="metric-value" style="font-size:22px;">${fcdUi.escape(value)}</div>
        <div class="metric-hint">${fcdUi.escape(hint)}</div>
      </div>
    `).join("");
  }

  function syncPicker(cases) {
    const picker = document.getElementById("compliance-case-picker");
    picker.innerHTML = cases.map((item) => `
      <option value="${fcdUi.escape(item.invoice_id)}" ${item.invoice_id === complianceState.selectedId ? "selected" : ""}>
        ${fcdUi.escape(item.invoice_id)} | ${fcdUi.escape(item.current_state)}
      </option>
    `).join("");
  }

  function renderComplianceEntries(entries) {
    const target = document.getElementById("compliance-list");
    if (!entries.length) {
      target.innerHTML = '<div class="empty-state">No compliance entries recorded.</div>';
      return;
    }
    target.innerHTML = entries.slice().reverse().map((entry) => `
      <div class="log-item">
        <strong>${fcdUi.escape(entry.event_type)}</strong>
        <span class="list-meta">${fcdUi.escape(entry.timestamp)}</span>
        <div class="mono">${fcdUi.escape(JSON.stringify(entry.details || {}))}</div>
      </div>
    `).join("");
  }

  function renderAuditEntries(entries) {
    const target = document.getElementById("audit-list");
    if (!entries.length) {
      target.innerHTML = '<div class="empty-state">No audit trail entries recorded.</div>';
      return;
    }
    target.innerHTML = entries.slice().reverse().map((entry) => `
      <div class="log-item">
        <strong>${fcdUi.escape(entry.action)}</strong>
        <span class="list-meta">${fcdUi.escape(entry.category)} | ${fcdUi.escape(entry.actor)} | ${fcdUi.escape(entry.timestamp)}</span>
        <div class="mono">${fcdUi.escape(JSON.stringify(entry.details || {}))}</div>
      </div>
    `).join("");
  }

  function renderRulePackCard(invoice, payload) {
    const target = document.getElementById("rule-pack-card");
    if (!invoice || !payload) {
      target.innerHTML = "Rule-pack data unavailable.";
      return;
    }
    target.innerHTML = `
      <div class="kv-list">
        <div class="kv-row"><label>Jurisdiction</label><div>${fcdUi.escape(invoice.jurisdiction)}</div></div>
        <div class="kv-row"><label>Active on</label><div>${fcdUi.escape(payload.on_date || payload.active_on || "")}</div></div>
        <div class="kv-row"><label>Rule pack</label><div>${fcdUi.escape(payload.rule_pack_version || payload.version || "Active")}</div></div>
      </div>
    `;
  }

  function renderComplianceDetail(detail, compliance, audit) {
    const complianceEntries = compliance.entries || [];
    const auditEntries = audit.entries || [];
    const openRestriction = complianceEntries.some((entry) => {
      const eventType = String(entry.event_type || "");
      return eventType.includes("CHALLENGE_OPEN") || eventType.includes("DISPUTE_OPEN") || eventType.includes("BREATHING_SPACE");
    });
    document.getElementById("compliance-detail").innerHTML = `
      <div class="kv-list">
        <div class="kv-row"><label>Invoice</label><div>${fcdUi.escape(detail.invoice_id)}</div></div>
        <div class="kv-row"><label>Status</label><div><span class="pill ${fcdUi.stateTone(detail.current_state)}">${fcdUi.escape(detail.current_state)}</span></div></div>
        <div class="kv-row"><label>Outstanding</label><div>${fcdUi.escape(detail.currency)} ${fcdUi.escape(detail.outstanding_balance_gbp)}</div></div>
        <div class="kv-row"><label>Restriction open</label><div>${fcdUi.escape(openRestriction ? "Yes" : "No")}</div></div>
        <div class="kv-row"><label>Compliance count</label><div>${fcdUi.escape(complianceEntries.length)}</div></div>
        <div class="kv-row"><label>Audit count</label><div>${fcdUi.escape(auditEntries.length)}</div></div>
      </div>
      <div class="action-list">
        <div class="action-item"><strong>Latest compliance</strong><span class="list-meta">${fcdUi.escape(complianceEntries.slice(-1)[0]?.event_type || "None")}</span></div>
        <div class="action-item"><strong>Latest audit</strong><span class="list-meta">${fcdUi.escape(auditEntries.slice(-1)[0]?.action || "None")}</span></div>
      </div>
    `;
  }

  function renderComplianceActionResult(kind, result) {
    const lines = [];
    if (kind === "case-health") {
      lines.push(`
        <div class="kv-row"><label>Confidence</label><div>${fcdUi.escape(result.case_confidence)}</div></div>
        <div class="kv-row"><label>Criteria passed</label><div>${fcdUi.escape(`${result.passed_count}/${result.total_count}`)}</div></div>
        <div class="kv-row"><label>Chain valid</label><div>${fcdUi.escape(String(result.chain_valid))}</div></div>
      `);
      if ((result.failed_criteria || []).length) {
        lines.push(`<div class="action-item"><strong>Failed criteria</strong><span class="list-meta">${fcdUi.escape(result.failed_criteria.join(" | "))}</span></div>`);
      }
    } else if (kind === "devils-advocate") {
      lines.push(`
        <div class="kv-row"><label>Blocked</label><div>${fcdUi.escape(String(result.blocked))}</div></div>
        <div class="kv-row"><label>Chain valid</label><div>${fcdUi.escape(String(result.chain_valid))}</div></div>
      `);
      if ((result.reasons || []).length) {
        lines.push(`<div class="action-item"><strong>Reasons</strong><span class="list-meta">${fcdUi.escape(result.reasons.join(" | "))}</span></div>`);
      }
      if ((result.recommended_actions || []).length) {
        lines.push(`<div class="action-item"><strong>Recommended actions</strong><span class="list-meta">${fcdUi.escape(result.recommended_actions.join(" | "))}</span></div>`);
      }
    } else {
      lines.push(`
        <div class="kv-row"><label>Accepted</label><div>${fcdUi.escape(String(result.accepted))}</div></div>
        <div class="kv-row"><label>Declaration version</label><div>${fcdUi.escape(result.declaration_version)}</div></div>
        <div class="kv-row"><label>Compliance entry</label><div>${fcdUi.escape(result.compliance_entry_id)}</div></div>
        <div class="kv-row"><label>Chain valid</label><div>${fcdUi.escape(String(result.chain_valid))}</div></div>
      `);
    }
    document.getElementById("compliance-action-result").innerHTML = `
      <div class="kv-list">${lines.filter((line) => line.includes("kv-row")).join("")}</div>
      <div class="action-list">${lines.filter((line) => line.includes("action-item")).join("")}</div>
    `;
  }

  async function runComplianceAction(kind) {
    const invoiceId = complianceState.selectedId;
    if (!invoiceId) return;
    document.getElementById("compliance-action-result").textContent = "Running check...";
    try {
      let result;
      if (kind === "case-health") {
        result = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/case-health-check`, "POST", {
          user_id: "USER-1",
          correct_customer_legal_entity: true,
          description_of_goods_or_services: true,
          invoice_number_and_date_verified: true,
          amount_matches_contract_or_quote: true,
          correct_billing_address: true,
          vat_numbers_checked: true,
          purchase_order_supplied_if_required: true,
          payment_terms_and_due_date_established: true,
          delivery_or_acceptance_proof_attached: true,
          no_unresolved_credit_notes: true,
          direct_payments_checked: true,
          no_known_dispute: true,
          creditor_authority_verified: true,
          limitation_period_checked: true,
          debtor_contact_details_verified: true,
          court_handoff_boundary_acknowledged: true
        });
      } else if (kind === "devils-advocate") {
        result = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/devils-advocate-check`, "POST", {
          active_dispute: false,
          payment_or_credit_discrepancy: false,
          delivery_evidence_unverified: false,
          settlement_pending_and_not_due: false,
          data_accuracy_challenge_pending: false,
          insolvency_or_breathing_space_flag: false
        });
      } else {
        const detail = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}`);
        result = await fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/legal-safety-gate/confirm`, "POST", {
          user_id: "USER-1",
          amount_claimed_gbp: detail.outstanding_balance_gbp,
          payments_recorded_gbp: "0",
          authorised_to_act: true,
          info_accurate: true,
          invoice_unpaid: true,
          payments_recorded_complete: true,
          genuine_supporting_docs: true,
          no_unresolved_dispute: true,
          commercial_not_excluded: true
        });
      }
      renderComplianceActionResult(kind, result);
      await selectComplianceCase(invoiceId);
    } catch (error) {
      document.getElementById("compliance-action-result").textContent = error.message;
    }
  }

  async function selectComplianceCase(invoiceId) {
    complianceState.selectedId = invoiceId;
    fcdUi.updateQueryParam("invoice", invoiceId);
    const overview = (complianceState.dashboard?.cases || []).find((item) => item.invoice_id === invoiceId) || null;
    renderComplianceMetrics(overview);
    syncPicker(complianceState.dashboard?.cases || []);
    const [compliance, audit, detail, rulePack] = await Promise.all([
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/compliance-ledger`),
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}/audit-trail`),
      fcdUi.request(`/invoices/${encodeURIComponent(invoiceId)}`),
      overview ? fcdUi.request(`/rule-packs/${encodeURIComponent(overview.jurisdiction)}/active`) : Promise.resolve(null)
    ]);
    const restricted = (compliance.entries || []).some((entry) => String(entry.event_type || "").includes("CHALLENGE_OPEN") || String(entry.event_type || "").includes("DISPUTE"));
    document.getElementById("compliance-summary").innerHTML = restricted
      ? "Recovery is currently restricted or dispute-linked. Review the compliance and audit entries before further escalation."
      : "No immediate compliance restriction detected in the latest recorded entries.";
    renderComplianceEntries(compliance.entries || []);
    renderAuditEntries(audit.entries || []);
    renderComplianceDetail(detail, compliance, audit);
    renderRulePackCard(detail, rulePack);
  }

  async function loadCompliancePage() {
    complianceState.dashboard = await fcdUi.request("/dashboard");
    const cases = complianceState.dashboard.cases || [];
    const filteredCases = cases.filter((item) => {
      const query = (document.getElementById("global-search").value || "").trim().toLowerCase();
      if (!query) return true;
      return [item.invoice_id, item.current_state, item.jurisdiction, item.next_step].join(" ").toLowerCase().includes(query);
    });
    if (!filteredCases.length) {
      document.getElementById("compliance-summary").textContent = "No cases available.";
      document.getElementById("compliance-list").innerHTML = '<div class="empty-state">No cases available.</div>';
      document.getElementById("audit-list").innerHTML = '<div class="empty-state">No cases available.</div>';
      return;
    }
    const preferred = fcdUi.queryParam("invoice") || filteredCases[0].invoice_id;
    complianceState.dashboard.cases = filteredCases;
    await selectComplianceCase(preferred);
  }

  document.getElementById("global-search").addEventListener("input", loadCompliancePage);
  document.getElementById("compliance-case-picker").addEventListener("change", (event) => selectComplianceCase(event.target.value));
  document.getElementById("run-case-health").addEventListener("click", () => runComplianceAction("case-health"));
  document.getElementById("run-devils-advocate").addEventListener("click", () => runComplianceAction("devils-advocate"));
  document.getElementById("run-legal-gate").addEventListener("click", () => runComplianceAction("legal-gate"));
  window.addEventListener("load", loadCompliancePage);
</script>
"""
    return _render_shell(
        title="Compliance",
        subtitle="Audit, rule-pack, and restriction review separated out from the operator dashboard for a cleaner working rhythm.",
        active_nav="compliance",
        content=content,
        page_script=script,
        search_placeholder="Search cases for compliance review...",
    )


def render_invoice_workspace_html(invoice_id: str) -> str:
    content = f"""
      <section class="cards-4" id="workspace-metrics"></section>

      <section class="split-layout">
        <div class="spotlight">
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Workspace summary</h2>
                <div class="panel-subtle">Focused case workspace for invoice {invoice_id} with Outstanding Balance, status, and audit context.</div>
              </div>
            </div>
            <div id="workspace-summary" class="empty-state">Loading case summary...</div>
          </div>
          <div class="panel">
            <div class="panel-header">
              <div>
                <h2>Quick actions</h2>
                <div class="panel-subtle">Open the next operational or evidence step.</div>
              </div>
            </div>
            <div class="inline-actions">
              <a class="ghost-button" style="padding:11px 16px;" href="/ui/cases?invoice={invoice_id}">Back to cases</a>
              <a class="ghost-button" style="padding:11px 16px;" href="/ui/compliance?invoice={invoice_id}">Compliance view</a>
              <a class="ghost-button" style="padding:11px 16px;" href="/invoices/{invoice_id}/evidence-bundle?output_filename={invoice_id}_bundle.pdf">Download bundle</a>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <h2>Case activity</h2>
              <div class="panel-subtle">Communications, compliance, and audit snapshots.</div>
            </div>
          </div>
          <div id="workspace-activity" class="log-list"></div>
        </div>
      </section>

      <section class="cards-3">
        <div class="panel">
          <div class="panel-header"><h3>Communications</h3></div>
          <div id="workspace-communications" class="log-list"></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h3>Compliance ledger</h3></div>
          <div id="workspace-compliance" class="log-list"></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h3>ACE audit trail</h3></div>
          <div id="workspace-audit" class="log-list"></div>
        </div>
      </section>
    """
    script = """
<script>
  const workspaceInvoiceId = "__INVOICE_ID__";

  function renderWorkspaceMetrics(detail) {
    const cards = [
      ["Case", detail.invoice_id, "Invoice workspace", "var(--primary)"],
      ["Outstanding", `${detail.currency} ${detail.outstanding_balance_gbp}`, "Live debtor balance", "var(--green)"],
      ["State", detail.current_state, "Current workflow stage", "var(--orange)"],
      ["Chain Valid", String(detail.chain_valid), "Event chain status", "var(--purple)"]
    ];
    document.getElementById("workspace-metrics").innerHTML = cards.map(([label, value, hint, color]) => `
      <div class="card metric-card" style="--accent:${color}">
        <div class="metric-label">${fcdUi.escape(label)}</div>
        <div class="metric-value" style="font-size:22px;">${fcdUi.escape(value)}</div>
        <div class="metric-hint">${fcdUi.escape(hint)}</div>
      </div>
    `).join("");
  }

  function renderWorkspaceSummary(detail) {
    const tone = fcdUi.stateTone(detail.current_state);
    document.getElementById("workspace-summary").innerHTML = `
      <div class="kv-list">
        <div class="kv-row"><label>Invoice</label><div>${fcdUi.escape(detail.invoice_id)}</div></div>
        <div class="kv-row"><label>Principal</label><div>${fcdUi.escape(detail.currency)} ${fcdUi.escape(detail.principal_amount)}</div></div>
        <div class="kv-row"><label>Outstanding</label><div>${fcdUi.escape(detail.currency)} ${fcdUi.escape(detail.outstanding_balance_gbp)}</div></div>
        <div class="kv-row"><label>Status</label><div><span class="pill ${tone}">${fcdUi.escape(detail.current_state)}</span></div></div>
        <div class="kv-row"><label>Jurisdiction</label><div>${fcdUi.escape(detail.jurisdiction)}</div></div>
        <div class="kv-row"><label>Debtor type</label><div>${fcdUi.escape(detail.debtor_type)}</div></div>
        <div class="kv-row"><label>Due date</label><div>${fcdUi.escape(detail.due_date)}</div></div>
      </div>
    `;
  }

  function renderLogList(id, entries, formatter) {
    const target = document.getElementById(id);
    if (!entries.length) {
      target.innerHTML = '<div class="empty-state">No records yet.</div>';
      return;
    }
    target.innerHTML = entries.slice().reverse().map(formatter).join("");
  }

  async function loadWorkspace() {
    const [detail, communications, compliance, audit] = await Promise.all([
      fcdUi.request(`/invoices/${encodeURIComponent(workspaceInvoiceId)}`),
      fcdUi.request(`/invoices/${encodeURIComponent(workspaceInvoiceId)}/communications`),
      fcdUi.request(`/invoices/${encodeURIComponent(workspaceInvoiceId)}/compliance-ledger`),
      fcdUi.request(`/invoices/${encodeURIComponent(workspaceInvoiceId)}/audit-trail`)
    ]);
    renderWorkspaceMetrics(detail);
    renderWorkspaceSummary(detail);
    renderLogList("workspace-communications", communications.communications || [], (entry) => `
      <div class="log-item">
        <strong>${fcdUi.escape(entry.subject)}</strong>
        <span class="list-meta">${fcdUi.escape(entry.channel)} | ${fcdUi.escape(entry.recipient)} | ${fcdUi.escape(entry.latest_state || "CREATED")}</span>
      </div>
    `);
    renderLogList("workspace-compliance", compliance.entries || [], (entry) => `
      <div class="log-item">
        <strong>${fcdUi.escape(entry.event_type)}</strong>
        <span class="list-meta">${fcdUi.escape(entry.timestamp)}</span>
      </div>
    `);
    renderLogList("workspace-audit", audit.entries || [], (entry) => `
      <div class="log-item">
        <strong>${fcdUi.escape(entry.action)}</strong>
        <span class="list-meta">${fcdUi.escape(entry.category)} | ${fcdUi.escape(entry.timestamp)}</span>
      </div>
    `);
    const merged = [
      ...(audit.entries || []).map((entry) => ({ label: entry.action, when: entry.timestamp, type: "Audit" })),
      ...(compliance.entries || []).map((entry) => ({ label: entry.event_type, when: entry.timestamp, type: "Compliance" }))
    ].sort((left, right) => String(right.when).localeCompare(String(left.when)));
    renderLogList("workspace-activity", merged.slice(0, 10), (entry) => `
      <div class="log-item">
        <strong>${fcdUi.escape(entry.label)}</strong>
        <span class="list-meta">${fcdUi.escape(entry.type)} | ${fcdUi.escape(entry.when)}</span>
      </div>
    `);
  }

  window.addEventListener("load", loadWorkspace);
</script>
""".replace("__INVOICE_ID__", invoice_id)
    return _render_shell(
        title=f"Invoice Workspace - {invoice_id}",
        subtitle="A quieter, case-specific view so operators are not forced to work from one over-packed dashboard.",
        active_nav="cases",
        content=content,
        page_script=script,
        search_placeholder="Search within the product, then use the focused workspace for this case...",
    )


def render_home_html() -> str:
    return render_dashboard_html()
