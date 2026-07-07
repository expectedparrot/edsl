"""Shared standalone HTML renderer for row-oriented EDSL artifacts."""

from __future__ import annotations

from typing import Any

from edsl.base.html_artifacts import EDSL_BRAND_HTML, render_standalone_html


def render_collection_html(
    *,
    title: str,
    subtitle: str,
    facts: list[tuple[Any, str]],
    columns: list[str],
    rows: list[dict[str, Any]],
    raw: Any,
    search_placeholder: str = "Search",
    remote_context: dict[str, Any] | None = None,
) -> str:
    """Render a searchable table artifact using the shared Expected Parrot shell."""
    data = {
        "title": title,
        "subtitle": subtitle,
        "facts": [{"value": value, "label": label} for value, label in facts],
        "columns": columns,
        "rows": rows,
        "raw": raw,
        "search_placeholder": search_placeholder,
        "remote_context": remote_context,
    }
    return render_standalone_html(
        title=title,
        data_variable="DATA",
        data=data,
        body=BODY_HTML,
        script=SCRIPT,
        extra_css=EXTRA_CSS,
    )


EXTRA_CSS = """
.collection-panel { margin-top: 16px; }
.collection-json { margin-top: 14px; }
.cell-code { font-family: var(--font-mono); font-size: 12px; }
.cell-json {
  max-width: 520px;
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
"""


BODY_HTML = f"""
<div class="shell">
  <header>
    {EDSL_BRAND_HTML}
    <div class="title-row">
      <div>
        <h1 id="title"></h1>
        <div class="subtitle" id="subtitle"></div>
      </div>
      <div class="actions">
        <button class="btn" id="copy-json">Copy JSON</button>
        <button class="btn" id="download-json">Download JSON</button>
      </div>
    </div>
    <div class="facts" id="facts"></div>
    <div class="notice" id="remote-summary"></div>
  </header>

  <section class="panel collection-panel">
    <div class="toolbar">
      <input class="search" id="search" type="search">
      <span class="muted" id="visible-count"></span>
    </div>
    <div class="table-wrap">
      <table id="collection-table"></table>
    </div>
  </section>

  <details class="collection-json">
    <summary>Raw JSON</summary>
    <pre id="raw-json"></pre>
  </details>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
"""


SCRIPT = r"""
const state = { query: "", sortKey: DATA.columns[0] || "", sortDir: 1 };
const fmt = new Intl.NumberFormat();
const escapeHtml = value => String(value)
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;")
  .replaceAll('"', "&quot;")
  .replaceAll("'", "&#039;");
const text = value => {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
};

function init() {
  document.getElementById("title").textContent = DATA.title;
  document.getElementById("subtitle").textContent = DATA.subtitle || "";
  document.getElementById("search").placeholder = DATA.search_placeholder || "Search";
  document.getElementById("facts").innerHTML = DATA.facts.map(fact => `
    <span class="fact"><strong>${escapeHtml(fact.value)}</strong>${escapeHtml(fact.label)}</span>
  `).join("");
  document.getElementById("raw-json").textContent = JSON.stringify(DATA.raw, null, 2);
  renderRemoteSummary();
  bindEvents();
  renderTable();
}

function renderRemoteSummary() {
  const notice = document.getElementById("remote-summary");
  const context = DATA.remote_context || {};
  const rows = context.display_rows || [];
  if (!rows.length) {
    notice.className = "notice";
    notice.textContent = "";
    return;
  }
  const firstUrl = rows.find(row => row.label.toLowerCase().includes("url"));
  const primary = firstUrl || rows[0];
  const heading = context.display_name && firstUrl
    ? { label: "object", value: context.display_name, href: firstUrl.href || firstUrl.value }
    : primary;
  const headingCopy = context.display_name ? copyButtonHtml({ label: "display name", value: context.display_name }) : "";
  notice.className = "notice show ok";
  notice.innerHTML = `<div class="remote-heading"><strong>Expected Parrot Server:</strong> ${remoteValueHtml(heading)}${headingCopy}</div>${remoteMetaHtml(rows)}`;
}

function remoteValueHtml(row) {
  const href = row.href || (isHttpUrl(row.value) ? row.value : "");
  if (!href) return escapeHtml(row.value);
  return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(row.value)}</a>`;
}

function copyButtonHtml(row) {
  const label = row.label.toLowerCase();
  if (label !== "url" && label !== "alias url" && label !== "uuid" && label !== "display name") return "";
  return `<button class="copy-mini" data-copy="${escapeHtml(row.value)}" type="button">Copy</button>`;
}

function isHttpUrl(value) {
  return typeof value === "string" && (value.startsWith("https://") || value.startsWith("http://"));
}

function remoteMetaHtml(rows) {
  const preferred = ["object alias", "owner", "URL", "UUID", "description", "visibility", "updated", "created"];
  const rank = row => {
    const index = preferred.indexOf(row.label);
    return index === -1 ? preferred.length : index;
  };
  const visible = rows
    .sort((a, b) => rank(a) - rank(b))
    .slice(0, 8);
  if (!visible.length) return "";
  return `<table class="remote-meta"><tbody>${visible.map(row => `
    <tr><th>${escapeHtml(row.label)}</th><td>${remoteValueHtml(row)}${copyButtonHtml(row)}</td></tr>
  `).join("")}</tbody></table>`;
}

function filteredRows() {
  const query = state.query.trim().toLowerCase();
  let rows = DATA.rows || [];
  if (query) rows = rows.filter(row => JSON.stringify(row).toLowerCase().includes(query));
  return [...rows].sort((a, b) => {
    const av = text(a[state.sortKey]);
    const bv = text(b[state.sortKey]);
    return av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" }) * state.sortDir;
  });
}

function renderTable() {
  const table = document.getElementById("collection-table");
  const rows = filteredRows();
  document.getElementById("visible-count").textContent = `${fmt.format(rows.length)} of ${fmt.format((DATA.rows || []).length)} visible`;
  if (!DATA.columns.length) {
    table.innerHTML = "<tbody><tr><td class='empty'>No columns.</td></tr></tbody>";
    return;
  }
  table.innerHTML = `
    <thead><tr>${DATA.columns.map(col => `<th data-sort="${escapeHtml(col)}">${escapeHtml(col)}${sortArrow(col)}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows.length ? rows.map(row => `<tr>${DATA.columns.map(col => cell(row[col])).join("")}</tr>`).join("") : "<tr><td class='empty' colspan='99'>No rows.</td></tr>"}
    </tbody>
  `;
}

function sortArrow(col) {
  if (state.sortKey !== col) return "";
  return state.sortDir === 1 ? " ↑" : " ↓";
}

function cell(value) {
  if (value === null || value === undefined || value === "") return "<td><span class='missing'>NA</span></td>";
  if (typeof value === "object") return `<td><div class="cell-json">${escapeHtml(JSON.stringify(value, null, 2))}</div></td>`;
  const className = String(value).length > 80 ? "cell-json" : "value";
  return `<td><div class="${className}">${escapeHtml(value)}</div></td>`;
}

function bindEvents() {
  document.getElementById("search").addEventListener("input", event => {
    state.query = event.target.value;
    renderTable();
  });
  document.getElementById("collection-table").addEventListener("click", event => {
    const th = event.target.closest("th[data-sort]");
    if (!th) return;
    const key = th.dataset.sort;
    if (state.sortKey === key) state.sortDir *= -1;
    else {
      state.sortKey = key;
      state.sortDir = 1;
    }
    renderTable();
  });
  document.getElementById("copy-json").addEventListener("click", copyJson);
  document.getElementById("download-json").addEventListener("click", downloadJson);
  document.getElementById("remote-summary").addEventListener("click", event => {
    const button = event.target.closest("[data-copy]");
    if (!button) return;
    navigator.clipboard?.writeText(button.dataset.copy).then(
      () => showToast("Copied"),
      () => showToast("Clipboard blocked by browser")
    );
  });
}

function copyJson() {
  navigator.clipboard?.writeText(JSON.stringify(DATA.raw, null, 2)).then(
    () => showToast("JSON copied"),
    () => showToast("Clipboard blocked by browser")
  );
}

function downloadJson() {
  const blob = new Blob([JSON.stringify(DATA.raw, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${DATA.title.replace(/[^a-z0-9_-]+/gi, "_").toLowerCase() || "edsl"}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 1700);
}

init();
"""
