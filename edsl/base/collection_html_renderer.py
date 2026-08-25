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
    facts_layout: str = "cards",
    transcript_rows: list[dict[str, Any]] | None = None,
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
        "facts_layout": facts_layout,
        "transcript_rows": transcript_rows,
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
.facts-table { width: auto; margin-top: 18px; }
.facts-table th, .facts-table td { min-width: 110px; padding: 8px 14px; text-align: center; }
.view-tabs { display: flex; gap: 4px; margin-top: 18px; border-bottom: 1px solid var(--line); }
.view-tab { border: 0; border-bottom: 2px solid transparent; padding: 9px 14px; background: transparent; color: var(--muted); cursor: pointer; font-weight: 700; }
.view-tab.active { color: var(--text); border-bottom-color: var(--accent); }
.transcript-panel { margin-top: 16px; }
.transcript-toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 14px; }
.transcript-toolbar select { min-width: 220px; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--text); }
.transcript-counter { color: var(--muted); font-size: 13px; }
.transcript-meta { width: auto; margin-bottom: 18px; }
.transcript-meta th { color: var(--muted); text-align: left; }
.context-fields { display: grid; grid-template-columns: max-content minmax(140px, 1fr); gap: 5px 14px; }
.context-key { color: var(--muted); font-size: 12px; font-weight: 700; }
.context-value { white-space: pre-wrap; overflow-wrap: anywhere; }
.scenario-token { padding: 1px 4px; border-radius: 4px; background: #fff0d9; color: #8a4b08; }
th.column-agent { background: #eef6ff; color: #245b91; }
th.column-scenario { background: #fff4e5; color: #8a4b08; }
td.column-agent { background: #f8fbff; }
td.column-scenario { background: #fffbf5; }
.interview-link { border: 1px solid var(--line); border-radius: 999px; padding: 5px 9px; background: var(--panel); color: var(--accent); cursor: pointer; white-space: nowrap; }
.dimension-nav { display: flex; align-items: center; gap: 5px; padding: 5px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel); }
.dimension-label { margin: 0 4px; color: var(--muted); font-size: 11px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.dimension-value { min-width: 90px; max-width: 210px; overflow: hidden; text-align: center; text-overflow: ellipsis; white-space: nowrap; }
.dimension-nav.agent { border-color: #bfd8f2; background: #f8fbff; }
.dimension-nav.scenario { border-color: #efd5aa; background: #fffbf5; }
.column-picker { position: relative; }
.column-picker-panel { position: absolute; z-index: 10; right: 0; top: calc(100% + 6px); width: 270px; max-height: 360px; overflow: auto; padding: 10px; border: 1px solid var(--line); border-radius: 10px; background: var(--panel); box-shadow: 0 10px 30px rgba(0,0,0,.12); }
.column-picker-actions { display: flex; gap: 6px; margin-bottom: 8px; }
.column-option { display: flex; align-items: center; gap: 8px; padding: 5px 3px; font-family: var(--font-mono); font-size: 12px; }
.transcript-question { padding: 18px; margin-bottom: 14px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); }
.transcript-question-name { color: var(--muted); font-family: var(--font-mono); font-size: 11px; font-weight: 700; }
.transcript-question-text { margin: 5px 0 14px; font-size: 17px; font-weight: 700; }
.transcript-answer { white-space: pre-wrap; overflow-wrap: anywhere; }
.cell-code { font-family: var(--font-mono); font-size: 12px; }
.cell-json {
  max-width: 520px;
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.results-answers { min-width: 320px; display: grid; gap: 12px; }
.results-answer-name {
  margin-bottom: 6px;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
}
.interview-transcript { display: grid; gap: 8px; }
.interview-turn {
  max-width: 88%;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--panel);
}
.interview-turn.respondent {
  justify-self: end;
  background: var(--accent-soft);
  border-color: var(--line-strong);
}
.interview-role {
  margin-bottom: 3px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
}
.interview-text { white-space: pre-wrap; overflow-wrap: anywhere; }
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
    <nav class="view-tabs" id="view-tabs" hidden>
      <button class="view-tab active" id="table-tab" type="button">Table</button>
      <button class="view-tab" id="transcript-tab" type="button">Transcript</button>
    </nav>
  </header>

  <section class="panel collection-panel" id="table-panel">
    <div class="toolbar">
      <input class="search" id="search" type="search">
      <span class="muted" id="visible-count"></span>
      <div class="column-picker">
        <button class="btn" id="columns-button" type="button">Columns</button>
        <div class="column-picker-panel" id="columns-panel" hidden></div>
      </div>
      <button class="btn" id="copy-csv" type="button">Copy shown CSV</button>
    </div>
    <div class="table-wrap">
      <table id="collection-table"></table>
    </div>
  </section>

  <section class="transcript-panel" id="transcript-panel" hidden>
    <div class="transcript-toolbar" id="transcript-toolbar"></div>
    <div id="transcript-content"></div>
  </section>

  <details class="collection-json">
    <summary>Raw JSON</summary>
    <pre id="raw-json"></pre>
  </details>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
"""


SCRIPT = r"""
const state = {
  query: "",
  sortKey: DATA.columns[0] || "",
  sortDir: 1,
  transcriptIndex: 0,
  visibleColumns: new Set(DATA.columns || []),
};
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
  renderFacts();
  document.getElementById("raw-json").textContent = JSON.stringify(DATA.raw, null, 2);
  renderRemoteSummary();
  bindEvents();
  renderTable();
  renderColumnPicker();
  initTranscript();
}

function renderFacts() {
  const facts = DATA.facts || [];
  document.getElementById("facts").innerHTML = DATA.facts_layout === "table"
    ? `<table class="facts-table"><thead><tr>${facts.map(f => `<th>${escapeHtml(f.label)}</th>`).join("")}</tr></thead><tbody><tr>${facts.map(f => `<td>${escapeHtml(f.value)}</td>`).join("")}</tr></tbody></table>`
    : facts.map(fact => `<span class="fact"><strong>${escapeHtml(fact.value)}</strong>${escapeHtml(fact.label)}</span>`).join("");
}

function initTranscript() {
  if (!Array.isArray(DATA.transcript_rows)) return;
  document.getElementById("view-tabs").hidden = false;
  renderTranscript();
}

function activateView(view) {
  const transcript = view === "transcript";
  document.getElementById("table-panel").hidden = transcript;
  document.getElementById("transcript-panel").hidden = !transcript;
  document.getElementById("table-tab").classList.toggle("active", !transcript);
  document.getElementById("transcript-tab").classList.toggle("active", transcript);
}

function renderTranscript() {
  const rows = DATA.transcript_rows || [];
  const content = document.getElementById("transcript-content");
  if (!rows.length) {
    content.innerHTML = '<div class="empty">No results.</div>';
    document.getElementById("transcript-toolbar").innerHTML = "0 results";
    return;
  }
  const row = rows[state.transcriptIndex];
  renderTranscriptToolbar(row);
  content.innerHTML = `${metadataHtml(row)}${(row.questions || []).map(question => `
    <article class="transcript-question">
      <div class="transcript-question-name">${escapeHtml(question.name)}</div>
      <div class="transcript-question-text">${questionTextHtml(question.text || question.name, row.scenario)}</div>
      <div class="transcript-answer">${answerHtml(question.answer)}</div>
    </article>`).join("") || '<div class="empty">No answers.</div>'}`;
}

function renderTranscriptToolbar(row) {
  const dimensions = [
    ["agent", row.label],
    ["scenario", contextLabel(row.scenario, `Scenario ${row.index}`)],
    ["model", row.model || "NA"],
    ["iteration", String(row.iteration ?? 0)],
  ];
  document.getElementById("transcript-toolbar").innerHTML = dimensions.map(([field, value]) => `
    <div class="dimension-nav ${field}">
      <span class="dimension-label">${field}</span>
      <button class="btn" type="button" data-dimension="${field}" data-direction="-1" aria-label="Previous ${field}">‹</button>
      <span class="dimension-value" title="${escapeHtml(value)}">${escapeHtml(value)} <span class="muted">${dimensionPosition(row, field)}</span></span>
      <button class="btn" type="button" data-dimension="${field}" data-direction="1" aria-label="Next ${field}">›</button>
    </div>`).join("");
}

function contextLabel(value, fallback) {
  if (!value || typeof value !== "object") return text(value) || fallback;
  return text(value.name || value.title || value.product || value.label) || fallback;
}

function dimensionKey(row, field) {
  if (field === "agent") return JSON.stringify(row.agent);
  return JSON.stringify(row[field]);
}

function dimensionValues(field) {
  const unique = [];
  (DATA.transcript_rows || []).forEach(row => {
    const key = dimensionKey(row, field);
    if (!unique.includes(key)) unique.push(key);
  });
  return unique;
}

function dimensionPosition(row, field) {
  const values = dimensionValues(field);
  return `${values.indexOf(dimensionKey(row, field)) + 1}/${values.length}`;
}

function navigateDimension(field, direction) {
  const rows = DATA.transcript_rows || [];
  if (!rows.length) return;
  const unique = dimensionValues(field);
  const current = dimensionKey(rows[state.transcriptIndex], field);
  const target = unique[(unique.indexOf(current) + direction + unique.length) % unique.length];
  const otherFields = ["agent", "scenario", "model"].filter(item => item !== field);
  if (field !== "iteration") otherFields.push("iteration");
  const currentRow = rows[state.transcriptIndex];
  const next = rows.findIndex(row =>
    dimensionKey(row, field) === target
    && otherFields.every(item => dimensionKey(row, item) === dimensionKey(currentRow, item))
  );
  if (next >= 0) state.transcriptIndex = next;
  renderTranscript();
}

function questionTextHtml(questionText, scenario) {
  const source = String(questionText || "");
  const pattern = /{{\s*scenario\.([\w.-]+)\s*}}/g;
  let html = "";
  let cursor = 0;
  for (const match of source.matchAll(pattern)) {
    html += escapeHtml(source.slice(cursor, match.index));
    const value = match[1].split(".").reduce((item, key) => item?.[key], scenario);
    html += value === undefined
      ? escapeHtml(match[0])
      : `<span class="scenario-token">${escapeHtml(text(value))}</span>`;
    cursor = match.index + match[0].length;
  }
  return html + escapeHtml(source.slice(cursor));
}

function metadataHtml(row) {
  const values = [["Agent", row.agent], ["Model", row.model], ["Scenario", row.scenario], ["Iteration", row.iteration]];
  return `<table class="transcript-meta"><tbody>${values.map(([label, value]) =>
    `<tr><th>${label}</th><td>${contextHtml(value)}</td></tr>`).join("")}</tbody></table>`;
}

function contextHtml(value) {
  if (value === null || value === undefined || value === "") return '<span class="missing">NA</span>';
  if (!value || typeof value !== "object" || Array.isArray(value)) return escapeHtml(text(value));
  const fields = value.traits && typeof value.traits === "object"
    ? {...value.traits, ...(value.name ? {name: value.name} : {})}
    : value;
  const entries = Object.entries(fields);
  if (!entries.length) return '<span class="missing">None</span>';
  return `<div class="context-fields">${entries.map(([key, field]) => `
    <div class="context-key">${escapeHtml(key)}</div>
    <div class="context-value">${escapeHtml(typeof field === "string" ? field : JSON.stringify(field, null, 2))}</div>
  `).join("")}</div>`;
}

function answerHtml(answer) {
  if (answer?.__edsl_cell_type === "interview_transcript") return interviewHtml(answer.turns || []);
  if (answer === null || answer === undefined || answer === "") return '<span class="missing">NA</span>';
  return escapeHtml(typeof answer === "string" ? answer : JSON.stringify(answer, null, 2));
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
  const columns = DATA.columns.filter(column => state.visibleColumns.has(column));
  document.getElementById("visible-count").textContent = `${fmt.format(rows.length)} of ${fmt.format((DATA.rows || []).length)} visible`;
  if (!columns.length) {
    table.innerHTML = "<tbody><tr><td class='empty'>No columns.</td></tr></tbody>";
    return;
  }
  table.innerHTML = `
    <thead><tr>${columns.map(col => `<th class="${columnClass(col)}" data-sort="${escapeHtml(col)}">${escapeHtml(col)}${sortArrow(col)}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows.length ? rows.map(row => `<tr>${columns.map(col => cell(row[col], col, row)).join("")}</tr>`).join("") : "<tr><td class='empty' colspan='99'>No rows.</td></tr>"}
    </tbody>
  `;
}

function renderColumnPicker() {
  const panel = document.getElementById("columns-panel");
  panel.innerHTML = `<div class="column-picker-actions">
    <button class="btn" type="button" data-columns="all">All</button>
    <button class="btn" type="button" data-columns="none">None</button>
  </div>${DATA.columns.map(column => `<label class="column-option">
    <input type="checkbox" data-column="${escapeHtml(column)}" ${state.visibleColumns.has(column) ? "checked" : ""}>
    ${escapeHtml(column)}
  </label>`).join("")}`;
}

function csvCell(value) {
  let output = value;
  if (value?.__edsl_cell_type === "interview_transcript") {
    output = (value.turns || []).map(turn => `${turn.role}: ${turn.text || ""}`).join("\n");
  } else if (typeof value === "object" && value !== null) output = JSON.stringify(value);
  const string = output === null || output === undefined ? "" : String(output);
  return `"${string.replaceAll('"', '""')}"`;
}

function shownCsv() {
  const columns = DATA.columns.filter(column => state.visibleColumns.has(column));
  return [columns, ...filteredRows().map(row => columns.map(column => row[column]))]
    .map(row => row.map(csvCell).join(","))
    .join("\n");
}

function sortArrow(col) {
  if (state.sortKey !== col) return "";
  return state.sortDir === 1 ? " ↑" : " ↓";
}

function columnClass(column) {
  if (column.startsWith("agent.")) return "column-agent";
  if (column.startsWith("scenario.")) return "column-scenario";
  return "";
}

function cell(value, column, row) {
  const groupClass = columnClass(column);
  if (value === null || value === undefined || value === "") return `<td class="${groupClass}"><span class='missing'>NA</span></td>`;
  if (value?.__edsl_cell_type === "interview_transcript") {
    const count = (value.turns || []).length;
    return `<td><button class="interview-link" type="button" data-open-transcript="${escapeHtml(row["#"])}">${fmt.format(count)}-turn interview →</button></td>`;
  }
  if (hasInterviewAnswer(value)) return `<td class="${groupClass}">${answersHtml(value)}</td>`;
  if (typeof value === "object") return `<td class="${groupClass}"><div class="cell-json">${escapeHtml(JSON.stringify(value, null, 2))}</div></td>`;
  const valueClass = String(value).length > 80 ? "cell-json" : "value";
  return `<td class="${groupClass}"><div class="${valueClass}">${escapeHtml(value)}</div></td>`;
}

function hasInterviewAnswer(value) {
  return value && typeof value === "object" && !Array.isArray(value)
    && Object.values(value).some(answer => answer?.__edsl_cell_type === "interview_transcript");
}

function answersHtml(answers) {
  return `<div class="results-answers">${Object.entries(answers).map(([name, answer]) => `
    <section class="results-answer">
      <div class="results-answer-name">${escapeHtml(name)}</div>
      ${answer?.__edsl_cell_type === "interview_transcript"
        ? interviewHtml(answer.turns || [])
        : `<div class="cell-json">${escapeHtml(text(answer))}</div>`}
    </section>
  `).join("")}</div>`;
}

function interviewHtml(turns) {
  if (!turns.length) return '<span class="missing">No transcript turns</span>';
  return `<div class="interview-transcript">${turns.map(turn => {
    const role = turn.role === "respondent" ? "respondent" : "interviewer";
    const label = turn.role || "unknown";
    const message = turn.text || "(non-text content)";
    return `<div class="interview-turn ${role}">
      <div class="interview-role">${escapeHtml(label)}</div>
      <div class="interview-text">${escapeHtml(message)}</div>
    </div>`;
  }).join("")}</div>`;
}

function bindEvents() {
  document.getElementById("search").addEventListener("input", event => {
    state.query = event.target.value;
    renderTable();
  });
  document.getElementById("collection-table").addEventListener("click", event => {
    const transcriptLink = event.target.closest("[data-open-transcript]");
    if (transcriptLink) {
      const index = (DATA.transcript_rows || []).findIndex(row => String(row.index) === transcriptLink.dataset.openTranscript);
      if (index >= 0) state.transcriptIndex = index;
      activateView("transcript");
      renderTranscript();
      return;
    }
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
  document.getElementById("columns-button").addEventListener("click", () => {
    const panel = document.getElementById("columns-panel");
    panel.hidden = !panel.hidden;
  });
  document.getElementById("columns-panel").addEventListener("change", event => {
    const column = event.target.dataset.column;
    if (!column) return;
    if (event.target.checked) state.visibleColumns.add(column);
    else state.visibleColumns.delete(column);
    renderTable();
  });
  document.getElementById("columns-panel").addEventListener("click", event => {
    const action = event.target.dataset.columns;
    if (!action) return;
    state.visibleColumns = new Set(action === "all" ? DATA.columns : []);
    renderColumnPicker();
    renderTable();
  });
  document.getElementById("copy-csv").addEventListener("click", () => {
    navigator.clipboard?.writeText(shownCsv()).then(
      () => showToast("Shown CSV copied"),
      () => showToast("Clipboard blocked by browser")
    );
  });
  document.getElementById("table-tab").addEventListener("click", () => activateView("table"));
  document.getElementById("transcript-tab").addEventListener("click", () => activateView("transcript"));
  document.getElementById("transcript-toolbar").addEventListener("click", event => {
    const button = event.target.closest("[data-dimension]");
    if (!button) return;
    navigateDimension(button.dataset.dimension, Number(button.dataset.direction));
  });
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
