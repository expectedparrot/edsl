"""Standalone HTML rendering for ScenarioList artifacts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edsl.base.html_artifacts import (
    EDSL_BRAND_HTML,
    package_remote_context,
    render_standalone_html,
)


class ScenarioListHTMLRenderer:
    """Build a standalone, interactive HTML artifact for a ScenarioList."""

    def __init__(self, scenario_list: "ScenarioList") -> None:
        self.scenario_list = scenario_list

    def render(self, *, title: str = "ScenarioList") -> str:
        return _render_payload(self._payload(title=title), title=title)

    def save(self, filename: str | Path, *, title: str = "ScenarioList") -> Path:
        path = Path(filename)
        path.write_text(self.render(title=title), encoding="utf-8")
        return path

    @classmethod
    def from_package(
        cls, path: str | Path, ref: str = "HEAD"
    ) -> "ScenarioListPackageHTMLRenderer":
        return ScenarioListPackageHTMLRenderer(Path(path), ref=ref)

    def _payload(self, *, title: str) -> dict[str, Any]:
        fields = _fields_in_order([dict(scenario) for scenario in self.scenario_list])
        codebook = dict(getattr(self.scenario_list, "codebook", {}) or {})
        rows = [
            {
                "index": index,
                "values": _jsonable(dict(scenario)),
                "raw": _jsonable(
                    scenario.to_dict(add_edsl_version=False)
                    if hasattr(scenario, "to_dict")
                    else dict(scenario)
                ),
            }
            for index, scenario in enumerate(self.scenario_list)
        ]
        diagnostics = _diagnostics(fields, codebook, len(rows), None)
        return {
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provenance": {},
            "manifest": {},
            "summary": _summary(rows, fields, codebook),
            "fields": fields,
            "codebook": codebook,
            "diagnostics": diagnostics,
            "rows": rows,
        }


class ScenarioListPackageHTMLRenderer:
    """Build an HTML artifact from a ScenarioList git package tree."""

    def __init__(self, path: Path, ref: str = "HEAD") -> None:
        self.path = Path(path)
        self.ref = ref

    def render(self, *, title: str = "ScenarioList") -> str:
        return _render_payload(self._payload(title=title), title=title)

    def save(self, filename: str | Path, *, title: str = "ScenarioList") -> Path:
        path = Path(filename)
        path.write_text(self.render(title=title), encoding="utf-8")
        return path

    def _payload(self, *, title: str) -> dict[str, Any]:
        from edsl.base import git_package as gitpkg
        from .scenario_list_git import ScenarioListGitError, _load_manifest_at_ref
        from .scenario_list_git import _read_scenario_list

        manifest = _load_manifest_at_ref(self.path, self.ref)
        scenario_list = _read_scenario_list(self.path, self.ref)
        scenario_ids = manifest.get("scenario_order", [])
        scenario_dicts = [dict(scenario) for scenario in scenario_list]
        fields = _fields_in_order(scenario_dicts)
        codebook = dict(getattr(scenario_list, "codebook", {}) or {})
        rows = []

        for index, scenario in enumerate(scenario_list):
            rows.append(
                {
                    "index": index,
                    "id": scenario_ids[index] if index < len(scenario_ids) else None,
                    "values": _jsonable(dict(scenario)),
                    "raw": _jsonable(
                        scenario.to_dict(add_edsl_version=False)
                        if hasattr(scenario, "to_dict")
                        else dict(scenario)
                    ),
                }
            )

        provenance = {"path": str(self.path), "ref": self.ref}
        try:
            provenance["commit"] = gitpkg.resolve_commit(
                self.path, self.ref, error_cls=ScenarioListGitError
            )
            provenance["branch"] = gitpkg.current_branch(
                self.path, error_cls=ScenarioListGitError
            )
        except Exception:
            pass

        return {
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provenance": provenance,
            "manifest": manifest,
            "remote_context": package_remote_context(
                self.path, self.ref, manifest=manifest, error_cls=ScenarioListGitError
            ),
            "summary": _summary(rows, fields, codebook),
            "fields": fields,
            "codebook": codebook,
            "diagnostics": _diagnostics(fields, codebook, len(rows), manifest),
            "rows": rows,
        }


def _render_payload(payload: dict[str, Any], *, title: str) -> str:
    return render_standalone_html(
        title=title,
        data_variable="DATA",
        data=payload,
        body=BODY_HTML,
        script=SCRIPT,
    )


def _summary(
    rows: list[dict[str, Any]], fields: list[str], codebook: dict[str, str]
) -> dict[str, Any]:
    missing_cells = 0
    for row in rows:
        values = row.get("values", {})
        missing_cells += sum(1 for field in fields if field not in values)
    return {
        "scenarios": len(rows),
        "fields": len(fields),
        "codebook_entries": len(codebook),
        "codebook_coverage": _coverage(fields, codebook),
        "missing_cells": missing_cells,
    }


def _fields_in_order(scenario_dicts: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for scenario in scenario_dicts:
        for key in scenario.keys():
            if key not in fields:
                fields.append(key)
    return fields


def _diagnostics(
    fields: list[str],
    codebook: dict[str, str],
    row_count: int,
    manifest: dict[str, Any] | None,
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    field_set = set(fields)
    codebook_set = set(codebook)

    if manifest and manifest.get("n_scenarios") != len(manifest.get("scenario_order", [])):
        diagnostics.append(
            {
                "level": "warning",
                "title": "Manifest count mismatch",
                "detail": "n_scenarios does not match scenario_order length.",
            }
        )

    missing = sorted(field_set - codebook_set)
    if missing:
        diagnostics.append(
            {
                "level": "warning",
                "title": "Fields without codebook entries",
                "detail": ", ".join(missing),
            }
        )

    unused = sorted(codebook_set - field_set)
    if unused:
        diagnostics.append(
            {
                "level": "info",
                "title": "Codebook entries not used by these scenarios",
                "detail": ", ".join(unused),
            }
        )

    if not row_count:
        diagnostics.append(
            {
                "level": "warning",
                "title": "No scenarios",
                "detail": "This ScenarioList does not contain any scenarios.",
            }
        )

    if not diagnostics:
        diagnostics.append(
            {
                "level": "ok",
                "title": "No diagnostics",
                "detail": "Package manifest, fields, and codebook look consistent.",
            }
        )
    return diagnostics


def _coverage(fields: list[str], codebook: dict[str, str]) -> float:
    if not fields:
        return 1.0
    return len(set(fields) & set(codebook)) / len(fields)


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(k): _jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [_jsonable(v) for v in value]
        return repr(value)


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
    <div class="notice" id="diagnostic-summary"></div>
    <div class="notice" id="remote-summary"></div>
  </header>

  <nav class="tabs" aria-label="ScenarioList views">
    <button class="tab active" data-view-tab="scenarios">Scenarios</button>
    <button class="tab" data-view-tab="codebook">Codebook</button>
    <button class="tab" data-view-tab="package">Package</button>
  </nav>

  <section class="view active" id="view-scenarios">
    <div class="panel">
      <div class="toolbar">
        <input class="search" id="search" type="search" placeholder="Search scenarios and fields">
        <span class="muted" id="visible-count"></span>
      </div>
      <div class="table-wrap">
        <table id="scenario-table"></table>
      </div>
    </div>
  </section>

  <section class="view" id="view-codebook">
    <div class="panel">
      <div class="toolbar">
        <strong>Codebook</strong>
        <span class="muted" id="codebook-status"></span>
      </div>
      <div class="grid" id="codebook"></div>
      <details>
        <summary>Diagnostics</summary>
        <div class="grid" id="diagnostics"></div>
      </details>
    </div>
  </section>

  <section class="view" id="view-package">
    <div class="panel">
      <div class="toolbar">
        <strong>Package</strong>
        <span class="muted">Git-backed object provenance</span>
      </div>
      <div class="package-list" id="package"></div>
      <details>
        <summary>Manifest JSON</summary>
        <pre id="manifest-json"></pre>
      </details>
    </div>
  </section>
</div>

<div class="drawer-backdrop" id="drawer-backdrop"></div>
<aside class="drawer" id="drawer">
  <div class="drawer-head">
    <div>
      <div class="drawer-title" id="drawer-title"></div>
      <div class="muted" id="drawer-subtitle"></div>
    </div>
    <button class="btn" id="drawer-close">Close</button>
  </div>
  <div class="drawer-tabs">
    <button class="tab active" data-drawer-tab="values">Values</button>
    <button class="tab" data-drawer-tab="raw">Raw JSON</button>
  </div>
  <div class="drawer-body">
    <pre id="drawer-content"></pre>
  </div>
</aside>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
"""


SCRIPT = r"""
const state = {
  view: "scenarios",
  drawerTab: "values",
  query: "",
  sortKey: "index",
  sortDir: 1,
  selected: null
};

const fmt = new Intl.NumberFormat();
const pct = value => `${Math.round(value * 100)}%`;
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
const cellText = value => {
  if (value === null || value === undefined) return "<span class='missing'>NA</span>";
  if (typeof value === "string" && value.length === 0) return "<span class='missing'>empty</span>";
  return escapeHtml(text(value));
};

function init() {
  document.getElementById("title").textContent = DATA.title;
  document.getElementById("subtitle").textContent = subtitleText();
  renderFacts();
  renderDiagnosticSummary();
  renderRemoteSummary();
  renderTable();
  renderCodebook();
  renderPackage();
  bindEvents();
}

function subtitleText() {
  const p = DATA.provenance || {};
  const bits = [];
  if (p.path) bits.push(p.path.split("/").pop());
  if (p.branch) bits.push(p.branch);
  if (p.commit) bits.push(p.commit.slice(0, 8));
  return bits.length ? bits.join(" · ") : `Generated ${DATA.generated_at}`;
}

function renderFacts() {
  const s = DATA.summary;
  const items = [
    [fmt.format(s.scenarios), "scenarios"],
    [fmt.format(s.fields), "fields"],
    [fmt.format(s.codebook_entries), "codebook entries"],
    [pct(s.codebook_coverage), "coverage"]
  ];
  document.getElementById("facts").innerHTML = items.map(([value, label]) => `
    <span class="fact"><strong>${value}</strong>${label}</span>
  `).join("");
}

function meaningfulDiagnostics() {
  return DATA.diagnostics.filter(d => d.level !== "ok");
}

function renderDiagnosticSummary() {
  const notice = document.getElementById("diagnostic-summary");
  const diagnostics = meaningfulDiagnostics();
  if (!diagnostics.length) {
    notice.className = "notice show ok";
    notice.textContent = "No package or codebook issues detected.";
    return;
  }
  const hasError = diagnostics.some(d => d.level === "error");
  notice.className = `notice show ${hasError ? "error" : "warning"}`;
  notice.textContent = diagnostics.map(d => d.title).join("; ");
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
  const q = state.query.trim().toLowerCase();
  let rows = DATA.rows;
  if (q) rows = rows.filter(row => JSON.stringify(row).toLowerCase().includes(q));
  return [...rows].sort((a, b) => {
    const av = sortValue(a, state.sortKey);
    const bv = sortValue(b, state.sortKey);
    return av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" }) * state.sortDir;
  });
}

function sortValue(row, key) {
  if (key === "index") return String(row.index).padStart(10, "0");
  return text(row.values[key]);
}

function renderTable() {
  const columns = ["index", ...DATA.fields];
  const rows = filteredRows();
  document.getElementById("visible-count").textContent = `${fmt.format(rows.length)} of ${fmt.format(DATA.rows.length)} visible`;
  if (!DATA.rows.length) {
    document.getElementById("scenario-table").innerHTML = "<tbody><tr><td class='empty'>No scenarios.</td></tr></tbody>";
    return;
  }
  document.getElementById("scenario-table").innerHTML = `
    <thead><tr>${columns.map(key => `<th data-sort="${escapeHtml(key)}">${escapeHtml(key)}${sortArrow(key)}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows.map(row => `<tr data-index="${row.index}">
        ${columns.map(key => cellHtml(row, key)).join("")}
      </tr>`).join("")}
    </tbody>
  `;
}

function sortArrow(key) {
  if (state.sortKey !== key) return "";
  return state.sortDir === 1 ? " ↑" : " ↓";
}

function cellHtml(row, key) {
  if (key === "index") return `<td class="index">${row.index + 1}</td>`;
  return `<td><div class="value">${cellText(row.values[key])}</div></td>`;
}

function renderCodebook() {
  document.getElementById("codebook-status").textContent = `${pct(DATA.summary.codebook_coverage)} coverage`;
  const entries = Object.entries(DATA.codebook);
  document.getElementById("codebook").innerHTML = entries.length
    ? entries.map(([key, desc]) => `
      <div class="item">
        <div class="key">${escapeHtml(key)}</div>
        <div class="desc">${escapeHtml(desc)}</div>
      </div>
    `).join("")
    : "<div class='empty'>No codebook entries.</div>";
  document.getElementById("diagnostics").innerHTML = DATA.diagnostics.map(d => `
    <div class="item diag" data-level="${escapeHtml(d.level)}">
      <div class="diag-title">${escapeHtml(d.title)}</div>
      <div class="diag-detail">${escapeHtml(d.detail)}</div>
    </div>
  `).join("");
}

function renderPackage() {
  const p = DATA.provenance || {};
  const remoteRows = (DATA.remote_context?.display_rows || []).map(row => ({ label: row.label, value: row.value, href: row.href }));
  const rows = [
    { label: "path", value: p.path },
    { label: "ref", value: p.ref },
    { label: "branch", value: p.branch },
    { label: "commit", value: p.commit },
    { label: "format", value: DATA.manifest?.format },
    { label: "edsl version", value: DATA.manifest?.edsl_version },
    { label: "generated", value: DATA.generated_at },
    ...remoteRows
  ].filter(row => row.value !== undefined && row.value !== null && row.value !== "");
  document.getElementById("package").innerHTML = rows.map(row => `
    <div class="package-row"><span>${escapeHtml(row.label)}</span><code>${remoteValueHtml(row)}</code></div>
  `).join("");
  document.getElementById("manifest-json").textContent = JSON.stringify(DATA.manifest, null, 2);
}

function bindEvents() {
  document.querySelectorAll("[data-view-tab]").forEach(button => {
    button.addEventListener("click", () => setView(button.dataset.viewTab));
  });
  document.getElementById("search").addEventListener("input", event => {
    state.query = event.target.value;
    renderTable();
  });
  document.getElementById("scenario-table").addEventListener("click", event => {
    const th = event.target.closest("th[data-sort]");
    if (th) {
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortDir *= -1;
      else {
        state.sortKey = key;
        state.sortDir = 1;
      }
      renderTable();
      return;
    }
    const row = event.target.closest("tr[data-index]");
    if (row) openDrawer(Number(row.dataset.index));
  });
  document.querySelectorAll("[data-drawer-tab]").forEach(button => {
    button.addEventListener("click", () => setDrawerTab(button.dataset.drawerTab));
  });
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
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
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeDrawer();
  });
}

function setView(view) {
  state.view = view;
  document.querySelectorAll("[data-view-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.viewTab === view);
  });
  document.querySelectorAll(".view").forEach(section => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });
}

function openDrawer(index) {
  state.selected = DATA.rows.find(row => row.index === index);
  state.drawerTab = "values";
  document.getElementById("drawer-title").textContent = `Scenario ${index + 1}`;
  document.getElementById("drawer-subtitle").textContent = state.selected.id ? `scenario file ${state.selected.id}.json` : "";
  setDrawerTab("values");
  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer-backdrop").classList.add("open");
}

function closeDrawer() {
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawer-backdrop").classList.remove("open");
}

function setDrawerTab(tab) {
  state.drawerTab = tab;
  document.querySelectorAll("[data-drawer-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.drawerTab === tab);
  });
  renderDrawerContent();
}

function renderDrawerContent() {
  if (!state.selected) return;
  const value = state.drawerTab === "values" ? state.selected.values : state.selected.raw;
  document.getElementById("drawer-content").textContent = JSON.stringify(value, null, 2);
}

function copyJson() {
  const json = JSON.stringify(DATA, null, 2);
  navigator.clipboard?.writeText(json).then(
    () => showToast("JSON copied"),
    () => showToast("Clipboard blocked by browser")
  );
}

function downloadJson() {
  const blob = new Blob([JSON.stringify(DATA, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${DATA.title.replace(/[^a-z0-9_-]+/gi, "_").toLowerCase() || "scenario_list"}.json`;
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
