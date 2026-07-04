"""Standalone HTML rendering for Survey artifacts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from edsl.base.html_artifacts import (
    EDSL_BRAND_HTML,
    package_remote_context,
    render_standalone_html,
)


class SurveyPackageHTMLRenderer:
    """Build an HTML artifact from a Survey git package tree."""

    def __init__(self, path: Path, ref: str = "HEAD") -> None:
        self.path = Path(path)
        self.ref = ref

    def render(self, *, title: str = "EDSL Survey") -> str:
        return render_standalone_html(
            title=title,
            data_variable="DATA",
            data=self._payload(title=title),
            body=BODY_HTML,
            script=SCRIPT,
            extra_css=EXTRA_CSS,
        )

    def save(self, filename: str | Path, *, title: str = "EDSL Survey") -> Path:
        path = Path(filename)
        path.write_text(self.render(title=title), encoding="utf-8")
        return path

    def _payload(self, *, title: str) -> dict[str, Any]:
        from edsl.base import git_package as gitpkg
        from .survey_git import SurveyGitError, _load_manifest_at_ref
        from .survey_git import _read_survey_dict_at_ref

        manifest = _load_manifest_at_ref(self.path, self.ref)
        survey_dict = _read_survey_dict_at_ref(self.path, self.ref)
        question_ids = manifest.get("question_order", [])
        questions = survey_dict.get("questions", [])
        rule_collection = survey_dict.get("rule_collection") or {}
        rules = rule_collection.get("rules") or []
        memory_plan = survey_dict.get("memory_plan") or {}
        question_groups = survey_dict.get("question_groups") or {}
        questions_to_randomize = survey_dict.get("questions_to_randomize") or []
        options_to_pin = survey_dict.get("options_to_pin") or {}
        question_names = [q.get("question_name", f"q{idx}") for idx, q in enumerate(questions)]

        rows = []
        for index, question in enumerate(questions):
            q_rules = [rule for rule in rules if rule.get("current_q") == index]
            rule_views = [
                _rule_view(rule, question_names, len(questions)) for rule in q_rules
            ]
            piping = _piping_references(question)
            rows.append(
                {
                    "index": index,
                    "id": question_ids[index] if index < len(question_ids) else None,
                    "name": question.get("question_name"),
                    "type": question.get("question_type"),
                    "text": question.get("question_text"),
                    "options": question.get("question_options"),
                    "details": _question_details(question),
                    "rules": rule_views,
                    "piping": piping,
                    "logic": _logic_items(rule_views, piping),
                    "raw": _jsonable(question),
                }
            )

        provenance = {"path": str(self.path), "ref": self.ref}
        try:
            provenance["commit"] = gitpkg.resolve_commit(
                self.path, self.ref, error_cls=SurveyGitError
            )
            provenance["branch"] = gitpkg.current_branch(
                self.path, error_cls=SurveyGitError
            )
        except Exception:
            pass

        non_default_rules = [rule for rule in rules if rule.get("priority", -1) > -1]
        return {
            "title": title,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provenance": provenance,
            "manifest": manifest,
            "remote_context": package_remote_context(
                self.path, self.ref, manifest=manifest, error_cls=SurveyGitError
            ),
            "summary": {
                "questions": len(rows),
                "question_types": len({row.get("type") for row in rows if row.get("type")}),
                "rules": len(non_default_rules),
                "memory_entries": len((memory_plan.get("data") or {})),
                "groups": len(question_groups),
                "randomized": len(questions_to_randomize),
            },
            "questions": rows,
            "rules": [
                _rule_view(rule, question_names, len(questions)) for rule in rules
            ],
            "non_default_rules": [
                _rule_view(rule, question_names, len(questions))
                for rule in non_default_rules
            ],
            "memory_plan": _jsonable(memory_plan),
            "question_groups": _jsonable(question_groups),
            "questions_to_randomize": questions_to_randomize,
            "options_to_pin": _jsonable(options_to_pin),
            "flow_diagram": _flow_diagram_svg(rows, rules, question_names),
            "diagnostics": _diagnostics(
                rows,
                manifest,
                rules,
                memory_plan,
                question_groups,
                questions_to_randomize,
            ),
        }


def _question_details(question: dict[str, Any]) -> list[tuple[str, Any]]:
    hidden = {"question_name", "question_type", "question_text", "question_options"}
    return [
        (key, value)
        for key, value in question.items()
        if key not in hidden and value not in (None, "", [], {})
    ]


def _piping_references(question: dict[str, Any]) -> list[dict[str, str]]:
    references: dict[tuple[str, str], dict[str, str]] = {}
    for location, value in _walk_question_values(question):
        if not isinstance(value, str) or "{{" not in value:
            continue
        for match in re.finditer(r"\{\{\s*([A-Za-z_]\w*)\.([A-Za-z_]\w*)[^}]*\}\}", value):
            key = (match.group(1), match.group(2))
            references[key] = {
                "source": match.group(1),
                "field": match.group(2),
                "location": location,
                "expression": match.group(0),
            }
    return list(references.values())


def _walk_question_values(value: Any, prefix: str = "question"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_question_values(child, f"{prefix}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_question_values(child, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _logic_items(
    rules: list[dict[str, Any]], piping: list[dict[str, str]]
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for rule in rules:
        if rule.get("is_default"):
            continue
        behavior = str(rule.get("behavior") or "rule")
        items.append(
            {
                "kind": behavior,
                "label": str(rule.get("summary") or f"{behavior} -> {rule.get('target')}"),
                "detail": str(rule.get("detail") or rule.get("expression") or ""),
            }
        )
    for reference in piping:
        items.append(
            {
                "kind": "pipe",
                "label": f"pipes {reference['source']}.{reference['field']}",
                "detail": f"{reference['location']}: {reference['expression']}",
            }
        )
    return items


def _rule_view(
    rule: dict[str, Any], question_names: list[str], num_questions: int
) -> dict[str, Any]:
    current_q = rule.get("current_q")
    next_q = rule.get("next_q")
    is_default = rule.get("priority", -1) <= -1
    before_rule = bool(rule.get("before_rule"))
    skipped = _skipped_questions(current_q, next_q, before_rule, question_names)
    behavior = _rule_behavior(current_q, next_q, before_rule, num_questions)
    expression = rule.get("expression")
    return {
        "current_q": current_q,
        "current": _question_label(current_q, question_names),
        "expression": rule.get("expression"),
        "next_q": next_q,
        "target": _question_label(next_q, question_names),
        "priority": rule.get("priority"),
        "before_rule": before_rule,
        "is_default": is_default,
        "behavior": "default" if is_default else behavior,
        "condition": _human_condition(expression),
        "source_q": _rule_source_index(current_q, before_rule),
        "source": _rule_source_label(current_q, before_rule, question_names),
        "skipped": skipped,
        "summary": _rule_summary(
            expression,
            current_q,
            next_q,
            before_rule,
            question_names,
            num_questions,
            is_default,
        ),
        "detail": _rule_detail(
            expression, current_q, next_q, before_rule, question_names, skipped
        ),
        "raw": _jsonable(rule),
    }


def _question_label(index: Any, question_names: list[str]) -> str:
    if isinstance(index, int) and 0 <= index < len(question_names):
        return question_names[index]
    if isinstance(index, int) and index >= len(question_names):
        return "END"
    return str(index)


def _rule_behavior(
    current_q: Any, next_q: Any, before_rule: bool, num_questions: int
) -> str:
    if before_rule:
        return "skip"
    if isinstance(next_q, int) and next_q >= num_questions:
        return "end"
    if (
        isinstance(current_q, int)
        and isinstance(next_q, int)
        and next_q > current_q + 1
    ):
        return "jump"
    if (
        isinstance(current_q, int)
        and isinstance(next_q, int)
        and next_q <= current_q
    ):
        return "jump"
    return "branch"


def _rule_source_label(
    current_q: Any, before_rule: bool, question_names: list[str]
) -> str:
    if before_rule and isinstance(current_q, int) and current_q > 0:
        return _question_label(current_q - 1, question_names)
    return _question_label(current_q, question_names)


def _rule_source_index(current_q: Any, before_rule: bool) -> Any:
    if before_rule and isinstance(current_q, int) and current_q > 0:
        return current_q - 1
    return current_q


def _skipped_questions(
    current_q: Any, next_q: Any, before_rule: bool, question_names: list[str]
) -> list[str]:
    if not isinstance(current_q, int):
        return []
    if before_rule:
        end = next_q if isinstance(next_q, int) else current_q + 1
        return [
            _question_label(index, question_names)
            for index in range(current_q, min(end, len(question_names)))
        ]
    if isinstance(next_q, int) and next_q > current_q + 1:
        return [
            _question_label(index, question_names)
            for index in range(current_q + 1, min(next_q, len(question_names)))
        ]
    return []


def _rule_summary(
    expression: Any,
    current_q: Any,
    next_q: Any,
    before_rule: bool,
    question_names: list[str],
    num_questions: int,
    is_default: bool,
) -> str:
    target = _question_label(next_q, question_names)
    current = _question_label(current_q, question_names)
    condition = _human_condition(expression)
    if is_default:
        return f"otherwise continue to {target}"
    if before_rule:
        skipped = _skipped_questions(current_q, next_q, True, question_names)
        skipped_label = ", ".join(skipped) if skipped else current
        return f"if {condition}: skip {skipped_label} -> {target}"
    behavior = _rule_behavior(current_q, next_q, False, num_questions)
    if behavior == "end":
        return f"if {condition}: end survey"
    if behavior == "jump":
        skipped = _skipped_questions(current_q, next_q, False, question_names)
        if skipped:
            return f"if {condition}: jump to {target} (skips {', '.join(skipped)})"
        return f"if {condition}: jump to {target}"
    return f"if {condition}: go to {target}"


def _rule_detail(
    expression: Any,
    current_q: Any,
    next_q: Any,
    before_rule: bool,
    question_names: list[str],
    skipped: list[str],
) -> str:
    source = _rule_source_label(current_q, before_rule, question_names)
    target = _question_label(next_q, question_names)
    timing = "before showing" if before_rule else "after answering"
    current = _question_label(current_q, question_names)
    skipped_text = f" Skipped questions: {', '.join(skipped)}." if skipped else ""
    return (
        f"Evaluate {expression!s} {timing} {current}; "
        f"the flow from {source} goes to {target}.{skipped_text}"
    )


def _human_condition(expression: Any) -> str:
    text = str(expression or "").strip()
    if text == "True":
        return "always"
    if text == "False":
        return "never"

    def replace_reference(match: re.Match[str]) -> str:
        return f"{match.group(1)}.{match.group(2)}"

    text = re.sub(
        r"\{\{\s*([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*\}\}",
        replace_reference,
        text,
    )
    text = re.sub(r"\s*==\s*", " is ", text)
    text = re.sub(r"\s*!=\s*", " is not ", text)
    return text


def _flow_diagram_svg(
    rows: list[dict[str, Any]], rules: list[dict[str, Any]], question_names: list[str]
) -> str | None:
    try:
        import pydot
    except Exception:
        return None

    graph = pydot.Dot(
        graph_type="digraph",
        rankdir="TB",
        bgcolor="transparent",
        margin="0",
        nodesep="0.18",
        ranksep="0.28",
        splines="spline",
    )
    graph.set_node_defaults(
        shape="box",
        style='"rounded,filled"',
        fillcolor="white",
        color="#c9d4ce",
        fontname="Arial",
        fontsize="10",
        margin="0.08,0.05",
        height="0.36",
        width="1.55",
    )
    graph.set_edge_defaults(
        color="#a8b4ad",
        arrowsize="0.65",
        fontname="Arial",
        fontsize="9",
    )

    for row in rows:
        label = f"Q{row['index'] + 1}\\n{row.get('name') or ''}"
        graph.add_node(pydot.Node(f"Q{row['index']}", label=label))

    graph.add_node(
        pydot.Node(
            "EndOfSurvey",
            label="END",
            fillcolor="#f0f3f1",
            color="#c9d4ce",
        )
    )

    for index in range(len(rows) - 1):
        graph.add_edge(pydot.Edge(f"Q{index}", f"Q{index + 1}"))
    if rows:
        graph.add_edge(pydot.Edge(f"Q{len(rows) - 1}", "EndOfSurvey"))

    custom_rules = [rule for rule in rules if rule.get("priority", -1) > -1]
    colors = ["#527fd8", "#d88722", "#3d9660", "#7b61b8", "#9a5b12"]
    for index, rule in enumerate(custom_rules):
        view = _rule_view(rule, question_names, len(rows))
        source_q = view.get("source_q")
        next_q = rule.get("next_q")
        if not isinstance(source_q, int):
            continue
        source = f"Q{source_q}"
        target = (
            f"Q{next_q}"
            if isinstance(next_q, int) and next_q < len(rows)
            else "EndOfSurvey"
        )
        color = colors[index % len(colors)]
        graph.add_edge(
            pydot.Edge(
                source,
                target,
                label=_compact_rule_label(view),
                color=color,
                fontcolor=color,
                penwidth="2",
                constraint="false",
            )
        )

    try:
        svg = graph.create_svg().decode("utf-8")
    except Exception:
        return None
    svg_start = svg.find("<svg")
    return svg[svg_start:] if svg_start >= 0 else svg


def _compact_rule_label(rule_view: dict[str, Any]) -> str:
    condition = str(rule_view.get("condition") or "")
    target = str(rule_view.get("target") or "next")
    match = re.match(r"^[A-Za-z_]\w*\.answer is ['\"]?([^'\"]+)['\"]?$", condition)
    if match:
        return f"{match.group(1)} -> {target}"
    match = re.match(r"^[A-Za-z_]\w*\.answer is not ['\"]?([^'\"]+)['\"]?$", condition)
    if match:
        return f"not {match.group(1)} -> {target}"
    if condition == "always":
        return f"always -> {target}"
    return condition[:28]


def _diagnostics(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    rules: list[dict[str, Any]],
    memory_plan: dict[str, Any],
    question_groups: dict[str, Any],
    questions_to_randomize: list[str],
) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    question_names = {row.get("name") for row in rows}

    if manifest.get("n_questions") != len(manifest.get("question_order", [])):
        diagnostics.append(
            {
                "level": "warning",
                "title": "Manifest count mismatch",
                "detail": "n_questions does not match question_order length.",
            }
        )

    missing_randomized = sorted(set(questions_to_randomize) - question_names)
    if missing_randomized:
        diagnostics.append(
            {
                "level": "warning",
                "title": "Randomized questions not found",
                "detail": ", ".join(missing_randomized),
            }
        )

    for group_name, group_questions in question_groups.items():
        missing = sorted(set(group_questions or []) - question_names)
        if missing:
            diagnostics.append(
                {
                    "level": "warning",
                    "title": f"Question group '{group_name}' references missing questions",
                    "detail": ", ".join(missing),
                }
            )

    memory_names = set((memory_plan.get("data") or {}).keys())
    missing_memory = sorted(memory_names - question_names)
    if missing_memory:
        diagnostics.append(
            {
                "level": "warning",
                "title": "Memory entries reference missing questions",
                "detail": ", ".join(missing_memory),
            }
        )

    non_default_rules = [rule for rule in rules if rule.get("priority", -1) > -1]
    if not non_default_rules:
        diagnostics.append(
            {
                "level": "info",
                "title": "No custom skip logic",
                "detail": "Only default next-question rules are present.",
            }
        )

    if not diagnostics:
        diagnostics.append(
            {
                "level": "ok",
                "title": "No diagnostics",
                "detail": "Question order, rules, memory, and groups look consistent.",
            }
        )
    return diagnostics


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


EXTRA_CSS = """
.question-text { max-width: 520px; line-height: 1.35; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 8px;
  background: #fff;
  color: #344139;
  font-size: 12px;
}
.chip.skip { border-color: #f0b36a; background: #fff7e8; color: #6d3d00; }
.chip.jump, .chip.end { border-color: #8fb4ff; background: #eef4ff; color: #173f8a; }
.chip.branch { border-color: #9ed4ba; background: #eefaf3; color: #1b5a36; }
.chip.pipe { border-color: #c7b5ee; background: #f6f1ff; color: #4c2b84; }
.flow-diagram-wrap {
  overflow: auto;
  border-bottom: 1px solid var(--line);
  background: linear-gradient(#fff, #fbfdfb);
  padding: 14px;
  text-align: center;
}
.flow-diagram-wrap svg {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 0 auto;
}
.flow-list { display: grid; gap: 10px; padding: 14px; }
.flow-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr) 120px;
  gap: 12px;
  align-items: start;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: #fff;
  padding: 10px;
}
.flow-expression { font-family: var(--font-mono); font-size: 12px; overflow-wrap: anywhere; }
.flow-target { font-weight: 700; color: var(--accent); }
.flow-summary { font-weight: 700; color: #17201b; }
.flow-skipped { margin-top: 5px; color: #6d3d00; }
.flow-row.default { opacity: .62; }
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
    <div class="notice" id="diagnostic-summary"></div>
    <div class="notice" id="remote-summary"></div>
  </header>

  <nav class="tabs" aria-label="Survey views">
    <button class="tab active" data-view-tab="questions">Questions</button>
    <button class="tab" data-view-tab="flow">Flow</button>
    <button class="tab" data-view-tab="memory">Memory</button>
    <button class="tab" data-view-tab="package">Package</button>
  </nav>

  <section class="view active" id="view-questions">
    <div class="panel">
      <div class="toolbar">
        <input class="search" id="search" type="search" placeholder="Search questions, options, rules">
        <span class="muted" id="visible-count"></span>
      </div>
      <div class="table-wrap">
        <table id="survey-question-table"></table>
      </div>
    </div>
  </section>

  <section class="view" id="view-flow">
    <div class="panel">
      <div class="toolbar">
        <strong>Flow and skip logic</strong>
        <span class="muted" id="flow-count"></span>
      </div>
      <div class="flow-diagram-wrap" id="flow-diagram"></div>
      <div class="flow-list" id="flow"></div>
      <details>
        <summary>Diagnostics</summary>
        <div class="grid" id="diagnostics"></div>
      </details>
    </div>
  </section>

  <section class="view" id="view-memory">
    <div class="panel">
      <div class="toolbar">
        <strong>Memory, groups, and randomization</strong>
        <span class="muted" id="memory-summary"></span>
      </div>
      <div class="grid" id="memory-cards"></div>
      <details>
        <summary>Raw memory and randomization JSON</summary>
        <pre id="memory-json"></pre>
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
    <button class="tab active" data-drawer-tab="overview">Overview</button>
    <button class="tab" data-drawer-tab="rules">Rules</button>
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
  view: "questions",
  drawerTab: "overview",
  query: "",
  sortKey: "index",
  sortDir: 1,
  selected: null
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
  renderQuestionTable();
  renderFlow();
  renderMemory();
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
    [fmt.format(s.questions), "questions"],
    [fmt.format(s.question_types), "types"],
    [fmt.format(s.rules), "custom rules"],
    [fmt.format(s.memory_entries), "memory entries"],
    [fmt.format(s.randomized), "randomized"]
  ];
  document.getElementById("facts").innerHTML = items.map(([value, label]) => `
    <span class="fact"><strong>${value}</strong>${label}</span>
  `).join("");
}

function meaningfulDiagnostics() {
  return DATA.diagnostics.filter(d => d.level !== "ok" && d.level !== "info");
}

function renderDiagnosticSummary() {
  const notice = document.getElementById("diagnostic-summary");
  const diagnostics = meaningfulDiagnostics();
  if (!diagnostics.length) {
    notice.className = "notice show ok";
    notice.textContent = "No survey structure issues detected.";
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

function filteredQuestions() {
  const q = state.query.trim().toLowerCase();
  let rows = DATA.questions;
  if (q) rows = rows.filter(row => JSON.stringify(row).toLowerCase().includes(q));
  return [...rows].sort((a, b) => {
    const av = sortValue(a, state.sortKey);
    const bv = sortValue(b, state.sortKey);
    return av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" }) * state.sortDir;
  });
}

function sortValue(row, key) {
  if (key === "index") return String(row.index).padStart(10, "0");
  return text(row[key]);
}

function renderQuestionTable() {
  const rows = filteredQuestions();
  document.getElementById("visible-count").textContent = `${fmt.format(rows.length)} of ${fmt.format(DATA.questions.length)} visible`;
  if (!DATA.questions.length) {
    document.getElementById("survey-question-table").innerHTML = "<tbody><tr><td class='empty'>No questions.</td></tr></tbody>";
    return;
  }
  const columns = ["index", "name", "type", "text", "options", "logic"];
  document.getElementById("survey-question-table").innerHTML = `
    <thead><tr>${columns.map(key => `<th data-sort="${escapeHtml(key)}">${escapeHtml(key)}${sortArrow(key)}</th>`).join("")}</tr></thead>
    <tbody>
      ${rows.map(row => `<tr data-index="${row.index}">
        ${columns.map(key => questionCell(row, key)).join("")}
      </tr>`).join("")}
    </tbody>
  `;
}

function sortArrow(key) {
  if (state.sortKey !== key) return "";
  return state.sortDir === 1 ? " ↑" : " ↓";
}

function questionCell(row, key) {
  if (key === "index") return `<td class="index">${row.index + 1}</td>`;
  if (key === "text") return `<td><div class="question-text">${cellText(row.text)}</div></td>`;
  if (key === "options") return `<td><div class="chips">${optionChips(row.options)}</div></td>`;
  if (key === "logic") return `<td><div class="chips">${logicChips(row.logic)}</div></td>`;
  return `<td><div class="value">${cellText(row[key])}</div></td>`;
}

function optionChips(options) {
  if (!options || !options.length) return "<span class='missing'>none</span>";
  return options.map(option => `<span class="chip">${escapeHtml(text(option))}</span>`).join("");
}

function logicChips(logic) {
  if (!logic || !logic.length) return "<span class='missing'>none</span>";
  return logic.map(item => `
    <span class="chip ${escapeHtml(item.kind)}" title="${escapeHtml(item.detail)}">${escapeHtml(item.label)}</span>
  `).join("");
}

function renderFlow() {
  const rules = DATA.rules;
  document.getElementById("flow-count").textContent = `${fmt.format(DATA.non_default_rules.length)} custom, ${fmt.format(rules.length)} total`;
  renderFlowDiagram();
  document.getElementById("flow").innerHTML = rules.length
    ? rules.map(rule => `
      <div class="flow-row ${rule.is_default ? "default" : ""}">
        <div><strong>${escapeHtml(rule.current)}</strong><div class="muted">${rule.before_rule ? "before question" : "after answer"} · priority ${escapeHtml(rule.priority)}</div></div>
        <div>
          <div class="flow-summary">${escapeHtml(rule.summary)}</div>
          <div class="flow-expression">${escapeHtml(rule.expression)}</div>
          ${rule.skipped && rule.skipped.length ? `<div class="flow-skipped">skips ${escapeHtml(rule.skipped.join(", "))}</div>` : ""}
        </div>
        <div class="flow-target">→ ${escapeHtml(rule.target)}</div>
      </div>
    `).join("")
    : "<div class='empty'>No rules.</div>";
  document.getElementById("diagnostics").innerHTML = DATA.diagnostics.map(d => `
    <div class="item diag" data-level="${escapeHtml(d.level)}">
      <div class="diag-title">${escapeHtml(d.title)}</div>
      <div class="diag-detail">${escapeHtml(d.detail)}</div>
    </div>
  `).join("");
}

function renderMemory() {
  document.getElementById("memory-summary").textContent =
    `${fmt.format(DATA.summary.memory_entries)} memory entries · ${fmt.format(DATA.summary.groups)} groups`;
  const cards = [
    ["Questions to randomize", DATA.questions_to_randomize],
    ["Options to pin", DATA.options_to_pin],
    ["Question groups", DATA.question_groups],
    ["Memory plan", DATA.memory_plan?.data || {}]
  ];
  document.getElementById("memory-cards").innerHTML = cards.map(([title, value]) => `
    <div class="item">
      <div class="key">${escapeHtml(title)}</div>
      <pre>${escapeHtml(JSON.stringify(value, null, 2))}</pre>
    </div>
  `).join("");
  document.getElementById("memory-json").textContent = JSON.stringify({
    memory_plan: DATA.memory_plan,
    question_groups: DATA.question_groups,
    questions_to_randomize: DATA.questions_to_randomize,
    options_to_pin: DATA.options_to_pin
  }, null, 2);
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

function renderFlowDiagram() {
  const container = document.getElementById("flow-diagram");
  if (DATA.flow_diagram) {
    container.innerHTML = DATA.flow_diagram;
    const svg = container.querySelector("svg");
    if (svg) {
      svg.classList.add("flow-diagram");
      svg.setAttribute("data-layout", "vertical");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", "Survey flow diagram");
    }
    return;
  }
  container.innerHTML = "<div class='empty'>Flow diagram unavailable. Install pydot and Graphviz to render it.</div>";
}

function bindEvents() {
  document.querySelectorAll("[data-view-tab]").forEach(button => {
    button.addEventListener("click", () => setView(button.dataset.viewTab));
  });
  document.getElementById("search").addEventListener("input", event => {
    state.query = event.target.value;
    renderQuestionTable();
  });
  document.getElementById("survey-question-table").addEventListener("click", event => {
    const th = event.target.closest("th[data-sort]");
    if (th) {
      const key = th.dataset.sort;
      if (state.sortKey === key) state.sortDir *= -1;
      else {
        state.sortKey = key;
        state.sortDir = 1;
      }
      renderQuestionTable();
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
  state.selected = DATA.questions.find(row => row.index === index);
  state.drawerTab = "overview";
  document.getElementById("drawer-title").textContent = state.selected.name || `Question ${index + 1}`;
  document.getElementById("drawer-subtitle").textContent = state.selected.id ? `question file ${state.selected.id}.json` : "";
  setDrawerTab("overview");
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
  let value;
  if (state.drawerTab === "overview") {
    value = {
      name: state.selected.name,
      type: state.selected.type,
      text: state.selected.text,
      options: state.selected.options,
      details: state.selected.details,
      logic: state.selected.logic
    };
  } else if (state.drawerTab === "rules") {
    value = state.selected.rules;
  } else {
    value = state.selected.raw;
  }
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
  a.download = `${DATA.title.replace(/[^a-z0-9_-]+/gi, "_").toLowerCase() || "survey"}.json`;
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
