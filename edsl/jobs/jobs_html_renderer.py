"""Standalone HTML rendering for Jobs artifacts."""

from __future__ import annotations

import json
from typing import Any

from edsl.base.html_artifacts import EDSL_BRAND_HTML, render_standalone_html


class JobsHTMLRenderer:
    """Build a single-document Jobs artifact from the job's component objects."""

    def __init__(
        self, job: "Jobs", package_context: dict[str, Any] | None = None
    ) -> None:
        self.job = job
        self.package_context = package_context

    def render(self, *, title: str = "EDSL Jobs") -> str:
        return render_standalone_html(
            title=title,
            data_variable="DATA",
            data=self._payload(title=title),
            body=BODY_HTML,
            script=SCRIPT,
            extra_css=EXTRA_CSS,
        )

    def _payload(self, *, title: str) -> dict[str, Any]:
        metadata = {
            "post_run_methods": getattr(self.job, "_post_run_methods", []),
            "where_clauses": list(getattr(self.job, "_where_clauses", [])),
            "include_expression": getattr(self.job, "_include_expression", None),
            "has_dependency": getattr(self.job, "_depends_on", None) is not None,
        }
        if getattr(self.job, "_depends_on", None) is not None:
            metadata["dependency_summary"] = self.job._depends_on._summary()

        return {
            "title": title,
            "summary": {
                "questions": len(self.job.survey.questions),
                "agents": len(self.job.agents),
                "scenarios": len(self.job.scenarios),
                "models": len(self.job.models),
                "interviews": self.job.num_interviews,
                "total_questions": self.job.nr_questions,
            },
            "survey": _survey_payload(self.job.survey),
            "agents": _agents_payload(self.job.agents),
            "scenarios": _scenarios_payload(self.job.scenarios),
            "models": _models_payload(self.job.models),
            "metadata": metadata,
            "package_context": self.package_context,
        }


def _survey_payload(survey: Any) -> dict[str, Any]:
    rows = []
    for index, question in enumerate(survey.questions, start=1):
        question_dict = _to_dict(question)
        options = question_dict.get("question_options")
        rows.append(
            {
                "#": index,
                "name": getattr(question, "question_name", f"q{index}"),
                "type": getattr(question, "question_type", type(question).__name__),
                "text": getattr(question, "question_text", ""),
                "options": options if options not in (None, []) else "",
                "details": {
                    key: value
                    for key, value in question_dict.items()
                    if key
                    not in {
                        "question_name",
                        "question_type",
                        "question_text",
                        "question_options",
                    }
                    and value not in (None, "", [], {})
                },
            }
        )
    return {
        "title": "Survey",
        "columns": ["#", "name", "type", "text", "options"],
        "rows": rows,
        "details": {
            "memory_plan": _to_dict(getattr(survey, "memory_plan", {})),
            "question_groups": _to_dict(getattr(survey, "question_groups", {})),
            "rule_collection": _to_dict(getattr(survey, "rule_collection", {})),
        },
    }


def _agents_payload(agents: Any) -> dict[str, Any]:
    trait_keys: list[str] = []
    rows = []
    for index, agent in enumerate(agents, start=1):
        traits = dict(getattr(agent, "traits", {}) or {})
        for key in traits:
            if key not in trait_keys:
                trait_keys.append(key)
        row = {"#": index, "name": getattr(agent, "name", None) or f"Agent {index}"}
        row.update(traits)
        rows.append(row)
    return {
        "title": "Agents",
        "columns": ["#", "name", *trait_keys],
        "rows": rows,
        "details": {"codebook": _to_dict(getattr(agents, "codebook", {}) or {})},
    }


def _scenarios_payload(scenarios: Any) -> dict[str, Any]:
    fields: list[str] = []
    rows = []
    for index, scenario in enumerate(scenarios, start=1):
        values = dict(scenario)
        for key in values:
            if key not in fields:
                fields.append(key)
        rows.append({"#": index, **values})
    return {
        "title": "Scenarios",
        "columns": ["#", *fields],
        "rows": rows,
        "details": {"codebook": _to_dict(getattr(scenarios, "codebook", {}) or {})},
    }


def _models_payload(models: Any) -> dict[str, Any]:
    rows = []
    for index, model in enumerate(models, start=1):
        rows.append(
            {
                "#": index,
                "model": getattr(model, "model", getattr(model, "_model_", "")),
                "service": getattr(model, "_inference_service_", ""),
                "parameters": _to_dict(getattr(model, "parameters", {}) or {}),
            }
        )
    return {
        "title": "Models",
        "columns": ["#", "model", "service", "parameters"],
        "rows": rows,
        "details": {},
    }


def _to_dict(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        try:
            return value.to_dict(add_edsl_version=False)
        except TypeError:
            return value.to_dict()
    if isinstance(value, dict):
        return value
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


EXTRA_CSS = """
.jobs-tabs { position: sticky; top: 0; z-index: 5; background: var(--bg); }
.jobs-section { margin-top: 16px; }
.jobs-section-body { padding: 0; overflow: auto; }
.jobs-table td, .jobs-table th { white-space: normal; }
.jobs-detail { margin: 14px; }
.light-json {
  margin: 0;
  padding: 10px;
  overflow: auto;
  color: #26332c;
  background: #f8faf8;
  border: 1px solid var(--line);
  border-radius: 7px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-family: var(--font-mono);
  font-size: 12px;
}
.jobs-value { max-width: 460px; overflow-wrap: anywhere; }
.jobs-pill {
  display: inline-flex;
  border-radius: 999px;
  padding: 2px 8px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12px;
  font-weight: 650;
}
"""


BODY_HTML = f"""
<div class="shell">
  <header>
    {EDSL_BRAND_HTML}
    <div class="title-row">
      <div>
        <h1 id="title"></h1>
        <div class="subtitle">Survey, agents, scenarios, models, and run metadata.</div>
      </div>
    </div>
    <div class="facts" id="facts"></div>
    <div class="notice" id="remote-summary"></div>
  </header>

  <nav class="tabs jobs-tabs" aria-label="Jobs sections">
    <button class="tab active" data-view-tab="survey">Survey</button>
    <button class="tab" data-view-tab="agents">Agents</button>
    <button class="tab" data-view-tab="scenarios">Scenarios</button>
    <button class="tab" data-view-tab="models">Models</button>
    <button class="tab" data-view-tab="metadata">Metadata</button>
  </nav>

  <section class="view active" id="view-survey"></section>
  <section class="view" id="view-agents"></section>
  <section class="view" id="view-scenarios"></section>
  <section class="view" id="view-models"></section>
  <section class="view" id="view-metadata"></section>
</div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
"""


SCRIPT = r"""
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
const fmt = new Intl.NumberFormat();

function init() {
  document.getElementById("title").textContent = DATA.title;
  renderFacts();
  renderRemoteSummary();
  renderComponent("survey", DATA.survey);
  renderComponent("agents", DATA.agents);
  renderComponent("scenarios", DATA.scenarios);
  renderComponent("models", DATA.models);
  renderMetadata();
  bindTabs();
  bindRemoteCopy();
}

function renderRemoteSummary() {
  const notice = document.getElementById("remote-summary");
  const context = DATA.package_context || {};
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

function renderFacts() {
  const items = [
    [DATA.summary.questions, "questions"],
    [DATA.summary.agents, "agents"],
    [DATA.summary.scenarios, "scenarios"],
    [DATA.summary.models, "models"],
    [DATA.summary.interviews, "interviews"],
    [DATA.summary.total_questions, "total questions"]
  ];
  document.getElementById("facts").innerHTML = items.map(([value, label]) => `
    <span class="fact"><strong>${escapeHtml(fmt.format(value))}</strong>${escapeHtml(label)}</span>
  `).join("");
}

function renderComponent(name, component) {
  const section = document.getElementById(`view-${name}`);
  section.innerHTML = `
    <div class="panel jobs-section">
      <div class="toolbar">
        <strong>${escapeHtml(component.title)}</strong>
        <span class="muted">${fmt.format(component.rows.length)} rows</span>
      </div>
      <div class="jobs-section-body">
        ${table(component)}
      </div>
      ${details(component.details)}
    </div>
  `;
}

function table(component) {
  if (!component.rows.length) return "<div class='empty'>No rows.</div>";
  return `
    <div class="table-wrap">
      <table class="jobs-table">
        <thead><tr>${component.columns.map(column => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead>
        <tbody>
          ${component.rows.map(row => `<tr>${component.columns.map(column => cell(row[column], column)).join("")}</tr>`).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function cell(value, column) {
  if (value === null || value === undefined || value === "") return "<td><span class='missing'>NA</span></td>";
  if (column === "type") return `<td><span class="jobs-pill">${escapeHtml(value)}</span></td>`;
  if (typeof value === "object") return `<td><div class="jobs-value">${escapeHtml(JSON.stringify(value))}</div></td>`;
  return `<td><div class="jobs-value">${escapeHtml(value)}</div></td>`;
}

function details(value) {
  if (!value || !Object.keys(value).length) return "";
  return `
    <details class="jobs-detail">
      <summary>Details</summary>
      <pre class="light-json">${escapeHtml(JSON.stringify(value, null, 2))}</pre>
    </details>
  `;
}

function renderMetadata() {
  const packageContext = DATA.package_context
    ? `<details class="jobs-detail"><summary>Coop and remote package metadata</summary>${packageRowsHtml(DATA.package_context.display_rows || [])}<pre class="light-json">${escapeHtml(JSON.stringify(DATA.package_context, null, 2))}</pre></details>`
    : "";
  document.getElementById("view-metadata").innerHTML = `
    <div class="panel jobs-section">
      <div class="toolbar"><strong>Run Metadata</strong></div>
      <div class="jobs-detail">
        <pre class="light-json">${escapeHtml(JSON.stringify(DATA.metadata, null, 2))}</pre>
      </div>
      ${packageContext}
    </div>
  `;
}

function packageRowsHtml(rows) {
  if (!rows.length) return "";
  return `<div class="package-list">${rows.map(row => `
    <div class="package-row"><span>${escapeHtml(row.label)}</span><code>${remoteValueHtml(row)}</code></div>
  `).join("")}</div>`;
}

function bindTabs() {
  document.querySelectorAll("[data-view-tab]").forEach(button => {
    button.addEventListener("click", () => setView(button.dataset.viewTab));
  });
}

function bindRemoteCopy() {
  document.getElementById("remote-summary").addEventListener("click", event => {
    const button = event.target.closest("[data-copy]");
    if (!button) return;
    navigator.clipboard?.writeText(button.dataset.copy).then(
      () => showToast("Copied"),
      () => showToast("Clipboard blocked by browser")
    );
  });
}

function setView(view) {
  document.querySelectorAll("[data-view-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.viewTab === view);
  });
  document.querySelectorAll(".view").forEach(section => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });
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
