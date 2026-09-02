"""Standalone, detailed HTML DAG visualization for workflow instances."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
import json
from pathlib import Path
from typing import Any

from edsl.surveys import Survey

from .coordinator import WorkflowCoordinator

STATUS_LABELS = {
    "blocked": "Blocked",
    "ready": "Ready",
    "in_progress": "In progress",
    "completed": "Completed",
    "skipped": "Skipped",
    "failed": "Failed",
}

PARTICIPANT_COLORS = (
    "#2563eb",
    "#db2777",
    "#059669",
    "#d97706",
    "#7c3aed",
    "#0891b2",
    "#dc2626",
    "#4f46e5",
)


class WorkflowDAGVisualization:
    """Render live state and respondent-visible content for one instance."""

    def __init__(self, coordinator: WorkflowCoordinator, instance_id: str):
        self.coordinator, self.instance_id = coordinator, instance_id

    def to_html(self) -> str:
        store, workflow = self.coordinator.store, self.coordinator.workflow
        items = store.items(self.instance_id)
        if not items:
            raise ValueError(
                f"workflow instance {self.instance_id!r} has no work items"
            )
        by_step = {
            step.name: store.items(self.instance_id, step_name=step.name)
            for step in workflow.steps
        }
        instance = store.rows(
            "SELECT * FROM workflow_instances WHERE id = ?", (self.instance_id,)
        )[0]
        edges = []
        for step in workflow.steps:
            for dependency in (*step.after, *step.settled_after):
                sources, targets = by_step[dependency], by_step[step.name]
                source_by_participant = {
                    item["participant_id"]: item for item in sources
                }
                target_by_participant = {
                    item["participant_id"]: item for item in targets
                }
                shared = source_by_participant.keys() & target_by_participant.keys()
                if shared:
                    edges.extend(
                        (
                            source_by_participant[participant_id]["id"],
                            target_by_participant[participant_id]["id"],
                        )
                        for participant_id in sorted(shared)
                    )
                else:
                    edges.extend(
                        (source["id"], target["id"])
                        for source in sources
                        for target in targets
                    )
        step_times = [self._step_time(by_step[step.name]) for step in workflow.steps]
        rows = "".join(
            self._step_row(
                step,
                by_step[step.name],
                step_time,
                self._time_gap(step_times[index - 1], step_time) if index else 0,
            )
            for index, (step, step_time) in enumerate(zip(workflow.steps, step_times))
        )
        counts = Counter(item["status"] for item in items)
        summary = "".join(
            f'<span class="pill {escape(status)}">{escape(STATUS_LABELS.get(status, status.title()))} {count}</span>'
            for status, count in sorted(counts.items())
        )
        participants = sorted({item["participant_id"] for item in items})
        participant_legend = "".join(
            f'<span class="person-key"><i style="background:{self._participant_color(participant)}"></i>{escape(participant)}</span>'
            for participant in participants
        )
        timeline = "".join(
            self._event(event) for event in store.events(self.instance_id)
        )
        edge_data = json.dumps(edges).replace("<", "\\u003c")
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(workflow.name)} · workflow state</title>
<style>
:root {{ --ink:#172033;--muted:#687386;--line:#aeb8c7;--canvas:#f4f6f9;--green:#16835b;--blue:#2563eb;--amber:#c56a09;--gray:#7b8493;--purple:#7c3aed }}
* {{ box-sizing:border-box }} body {{ margin:0;color:var(--ink);background:var(--canvas);font:14px/1.45 Inter,ui-sans-serif,system-ui,sans-serif }}
header {{ padding:24px 30px 18px;background:#111827;color:white }} header h1 {{ margin:0 0 5px;font-size:22px }} header p {{ margin:0;color:#cbd5e1 }}
.summary {{ display:flex;gap:8px;flex-wrap:wrap;padding:13px 30px;background:white;border-bottom:1px solid #dbe1e9 }} .pill {{ border-radius:999px;padding:5px 10px;background:#eef1f5;font-size:12px;font-weight:750 }} .legend {{ display:flex;gap:12px;flex-wrap:wrap;align-items:center;padding:9px 30px;background:#fbfcfe;border-bottom:1px solid #dbe1e9;font-size:11px }} .person-key {{ display:inline-flex;align-items:center;gap:5px }} .person-key i {{ width:9px;height:9px;border-radius:50% }}
.pill.completed {{ color:#08734d;background:#dcfce7 }} .pill.ready {{ color:#1d4ed8;background:#dbeafe }} .pill.in_progress {{ color:#9a4b05;background:#ffedd5 }} .pill.skipped {{ color:#5b6471;background:#e5e7eb }} .pill.failed {{ color:#991b1b;background:#fee2e2 }}
.layout {{ display:grid;grid-template-columns:minmax(650px,1fr) 300px;min-height:calc(100vh - 125px) }} .dag-shell {{ overflow:auto;padding:35px 28px;position:relative;background:repeating-linear-gradient(to bottom,transparent 0,transparent 79px,#e8edf4 80px) }}
.dag {{ display:flex;flex-direction:column;position:relative;z-index:1;min-width:620px }} #edges {{ position:absolute;inset:35px 28px;pointer-events:none;overflow:visible;z-index:0 }}
.step-row {{ display:grid;grid-template-columns:205px max-content;gap:18px;align-items:start;margin-top:var(--time-gap) }} .step-heading {{ padding-top:2px;text-align:right;border-right:2px solid #cbd5e1;padding-right:15px;min-height:76px }} .wall-time {{ color:#0f172a!important;font:700 11px ui-monospace,monospace!important }}
.step-heading h2 {{ margin:0;font-size:15px }} .step-heading p {{ margin:3px 0 0;color:var(--muted);font-size:10px }} .condition {{ color:var(--purple)!important }} .node-lane {{ display:flex;gap:10px;flex-wrap:nowrap }}
details.card {{ width:230px;border:1px solid #d5dce6;border-left:6px solid var(--participant-color);border-radius:9px;background:white;box-shadow:0 3px 10px rgba(16,24,40,.07);overflow:hidden }}
details.card.skipped {{ opacity:.65;background:repeating-linear-gradient(135deg,#fff,#fff 9px,#f4f5f7 9px,#f4f5f7 18px) }}
details.card.failed {{ border-color:#ef4444;background:#fff7f7 }}
summary {{ cursor:pointer;list-style:none;padding:9px 11px;min-height:72px }} summary::-webkit-details-marker {{ display:none }} summary:after {{ content:'＋';float:right;color:var(--muted);font-size:14px }} details[open] summary:after {{ content:'−' }}
.status {{ display:inline-block;padding:3px 7px;margin-bottom:8px;border-radius:5px;background:#eef1f5;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em }} .completed .status {{ color:#08734d;background:#dcfce7 }} .ready .status {{ color:#1d4ed8;background:#dbeafe }} .in_progress .status {{ color:#9a4b05;background:#ffedd5 }} .failed .status {{ color:#991b1b;background:#fee2e2 }}
.performer {{ display:inline-block;float:right;padding:3px 7px;border:1px solid #cbd5e1;border-radius:999px;font-size:9px;font-weight:850;letter-spacing:.05em }} .performer.human {{ color:#166534;background:#dcfce7;border-color:#86efac }} .performer.llm {{ color:#6b21a8;background:#f3e8ff;border-color:#d8b4fe;clip-path:polygon(8% 0,92% 0,100% 25%,100% 75%,92% 100%,8% 100%,0 75%,0 25%) }}
.assignee {{ font-weight:750;word-break:break-word;font-size:12px }} .item-id {{ color:var(--muted);font:9px ui-monospace,monospace;margin-top:2px }} .detail {{ border-top:1px solid #e4e8ef;padding:4px 12px 13px;background:rgba(255,255,255,.96) }}
.section {{ margin-top:11px }} .section h3 {{ margin:0 0 7px;color:#4b5668;font-size:9px;text-transform:uppercase;letter-spacing:.08em }} .question {{ padding-left:2px;margin-top:9px }}
.question-type {{ display:flex;align-items:center;gap:7px;color:var(--muted);font-size:10px }} .q-glyph {{ width:12px;height:12px;display:inline-block;background:#64748b }} .q-glyph.multiple_choice,.q-glyph.checkbox {{ border-radius:50%;background:#2563eb }} .q-glyph.yes_no {{ transform:rotate(45deg);background:#7c3aed }} .q-glyph.free_text {{ border-radius:2px;background:#059669 }} .q-glyph.numerical {{ clip-path:polygon(50% 0,100% 100%,0 100%);background:#d97706 }} .question-text {{ margin:5px 0 6px;font-size:12px;font-weight:650 }} .options {{ margin:5px 0 0;padding-left:19px;color:#465166 }}
.response {{ margin-top:8px;padding:8px 10px;border-radius:7px;background:#ecfdf3;color:#12633f }} .response b {{ display:block;font-size:10px;text-transform:uppercase }} pre {{ margin:0;padding:9px;border-radius:7px;background:#f1f4f8;white-space:pre-wrap;word-break:break-word;font:11px/1.4 ui-monospace,monospace }}
.metadata {{ display:grid;grid-template-columns:86px 1fr;gap:4px 8px;font-size:11px }} .metadata b {{ color:var(--muted) }} aside {{ background:white;border-left:1px solid #d8dee8;padding:22px;overflow:auto }} aside h2 {{ margin:0 0 15px;font-size:15px }}
.event {{ display:grid;grid-template-columns:25px 1fr;gap:8px;margin-bottom:13px }} .event-seq {{ display:grid;place-items:center;width:23px;height:23px;border-radius:50%;color:white;background:#64748b;font-size:10px }} .event-kind {{ font-weight:700;font-size:12px }} .event-detail {{ color:var(--muted);font-size:11px;word-break:break-word }}
path.edge {{ stroke:var(--line);stroke-width:2;fill:none }} path.edge.active {{ stroke:#73a58d }} marker path {{ fill:var(--line);stroke:none }} @media(max-width:950px) {{ .layout {{ grid-template-columns:1fr }} aside {{ border-left:0;border-top:1px solid #d8dee8 }} }}
</style></head><body>
<header><h1>{escape(workflow.name)}</h1><p>Instance {escape(self.instance_id)} · {escape(instance["status"].title())}</p></header><div class="summary">{summary}<span class="pill">Vertical axis: wall-clock time</span><span class="pill">Select a compact node to expand</span></div><div class="legend"><b>Respondents</b>{participant_legend}<b>Intended performer</b><span class="performer human">PERSON</span><span class="performer llm">LLM</span><b>Question shapes</b><span>● choice</span><span>◆ yes/no</span><span>■ free text</span><span>▲ numerical</span></div>
<main class="layout"><section class="dag-shell"><svg id="edges" aria-hidden="true"><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z"/></marker></defs></svg><div class="dag">{rows}</div></section><aside><h2>Event timeline</h2>{timeline}</aside></main>
<script>const edges={edge_data};function drawEdges(){{const svg=document.getElementById('edges'),shell=svg.parentElement,base=shell.getBoundingClientRect();svg.querySelectorAll('.edge').forEach(p=>p.remove());svg.setAttribute('width',shell.scrollWidth-56);svg.setAttribute('height',shell.scrollHeight-70);for(const[fromId,toId]of edges){{const from=document.querySelector(`[data-node-id="${{CSS.escape(fromId)}}"]`),to=document.querySelector(`[data-node-id="${{CSS.escape(toId)}}"]`);if(!from||!to)continue;const a=from.getBoundingClientRect(),b=to.getBoundingClientRect(),x1=a.left+a.width/2-base.left-28+shell.scrollLeft,y1=a.bottom-base.top-35+shell.scrollTop,x2=b.left+b.width/2-base.left-28+shell.scrollLeft,y2=b.top-base.top-35+shell.scrollTop,bend=Math.max(22,(y2-y1)/2),p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('class','edge '+(from.classList.contains('completed')?'active':''));p.setAttribute('d',`M ${{x1}} ${{y1}} C ${{x1}} ${{y1+bend}}, ${{x2}} ${{y2-bend}}, ${{x2}} ${{y2}}`);p.setAttribute('marker-end','url(#arrow)');svg.appendChild(p);}}}}addEventListener('load',drawEdges);addEventListener('resize',drawEdges);document.querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>requestAnimationFrame(drawEdges)));</script></body></html>"""

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_html(), encoding="utf-8")
        return destination.resolve()

    def _step_row(self, step, items, step_time: datetime, time_gap: int) -> str:
        from .definition import Quorum

        condition = ""
        if step.enabled_when is not None:
            condition = (
                f'<p class="condition">Enable if '
                f"{escape(self._condition_text(step.enabled_when))}</p>"
            )
        dependency_parts = []
        if step.after:
            dependency_parts.append(f"After {', '.join(step.after)}")
        if step.settled_after:
            dependency_parts.append(f"After settled {', '.join(step.settled_after)}")
        dependency = "; ".join(dependency_parts) or "Starts immediately"
        completion = (
            f"Quorum: {step.completion.count} of {len(items)}"
            if isinstance(step.completion, Quorum)
            else f"Completion: all {len(items)} assigned"
        )
        visibility = (
            "Outputs: visible to all"
            if step.output_visibility is None
            else "Outputs: "
            + ", ".join(
                ", ".join(f"{key}={value}" for key, value in selector.traits.items())
                or "all"
                for selector in step.output_visibility
            )
        )
        cards = "".join(self._card(step, item) for item in items)
        wall_time = step_time.astimezone().strftime("%H:%M:%S")
        return f'<section class="step-row" style="--time-gap:{time_gap}px"><div class="step-heading"><p class="wall-time">{escape(wall_time)}</p><h2>{escape(step.name)}</h2><p>{escape(dependency)}</p><p>{escape(completion)}</p><p>{escape(visibility)}</p>{condition}</div><div class="node-lane">{cards}</div></section>'

    @staticmethod
    def _step_time(items) -> datetime:
        timestamps = [
            item["opened_at"] or item["completed_at"] or item["created_at"]
            for item in items
        ]
        return min(datetime.fromisoformat(value) for value in timestamps)

    @staticmethod
    def _time_gap(previous: datetime, current: datetime) -> int:
        elapsed = max(0.0, (current - previous).total_seconds())
        return min(160, 34 + round(elapsed * 2))

    @staticmethod
    def _participant_color(participant_id: str) -> str:
        import hashlib

        index = hashlib.sha256(participant_id.encode("utf-8")).digest()[0]
        return PARTICIPANT_COLORS[index % len(PARTICIPANT_COLORS)]

    @classmethod
    def _condition_text(cls, condition) -> str:
        from .definition import (
            AllCondition,
            AnswerCondition,
            AnyCondition,
            ChanceCondition,
            ExpressionCondition,
            NotCondition,
            OutputCountCondition,
            OutputDisagreementCondition,
            OutputMajorityCondition,
            OutputRangeCondition,
            StepCompletedCondition,
        )

        if isinstance(condition, AnswerCondition):
            return (
                f"{condition.step_name}.{condition.question_name} = {condition.equals}"
            )
        if isinstance(condition, StepCompletedCondition):
            return f"{condition.step_name} completed"
        if isinstance(condition, AllCondition):
            return " and ".join(
                cls._condition_text(item) for item in condition.conditions
            )
        if isinstance(condition, AnyCondition):
            return " or ".join(
                cls._condition_text(item) for item in condition.conditions
            )
        if isinstance(condition, NotCondition):
            return f"not ({cls._condition_text(condition.condition)})"
        if isinstance(condition, ChanceCondition):
            return f"chance({condition.probability:.0%}, key={condition.key})"
        if isinstance(condition, OutputCountCondition):
            return (
                f"count({condition.step_name}.{condition.question_name} = "
                f"{condition.value}) >= {condition.minimum}"
            )
        if isinstance(condition, OutputDisagreementCondition):
            return f"{condition.step_name}.{condition.question_name} has disagreement"
        if isinstance(condition, OutputMajorityCondition):
            return (
                f"majority({condition.step_name}.{condition.question_name}) = "
                f"{condition.value}"
            )
        if isinstance(condition, OutputRangeCondition):
            return (
                f"range({condition.step_name}.{condition.question_name}) <= "
                f"{condition.maximum}"
            )
        if isinstance(condition, ExpressionCondition):
            return cls._expression_text(condition.expression)
        return repr(condition)

    @classmethod
    def _expression_text(cls, expression) -> str:
        if expression.op == "derived_ref":
            return f"{expression.options['name']}.{expression.options['field']}"
        if expression.op == "step_outputs":
            return (
                f"{expression.options['step_name']}."
                f"{expression.options['question_name']}[]"
            )
        unary = {"mean", "median", "minimum", "maximum", "range"}
        if expression.op in unary:
            return f"{expression.op}({cls._expression_text(expression.args[0])})"
        symbols = {
            "add": "+",
            "subtract": "-",
            "multiply": "×",
            "divide": "÷",
            "at_most": "≤",
            "at_least": "≥",
            "equals": "=",
        }
        if expression.op in symbols:
            left, right = expression.args
            left_text = (
                cls._expression_text(left) if hasattr(left, "op") else repr(left)
            )
            right_text = (
                cls._expression_text(right) if hasattr(right, "op") else repr(right)
            )
            return f"{left_text} {symbols[expression.op]} {right_text}"
        return expression.op

    def _card(self, step, item) -> str:
        store = self.coordinator.store
        rendered = store.rendered_item(item["id"])
        survey = Survey.from_dict(rendered["survey"]) if rendered else step.survey
        answers = store.item_answers(item["id"]) or {}
        questions = "".join(
            self._question(question, answers) for question in survey.questions
        )
        state = rendered["shared_state"] if rendered else {}
        state_html = self._json_section("Shared state shown", state) if state else ""
        writes = [
            {
                "state_id": write.state_id,
                "target": write.target,
                "command": write.command,
            }
            for write in step.writes
        ]
        writes_html = self._json_section("State transitions", writes) if writes else ""
        attempts = [
            {
                "attempt": attempt["attempt_number"],
                "status": attempt["status"],
                "error_kind": attempt["error_kind"],
                "started_at": attempt["started_at"],
                "finished_at": attempt["finished_at"],
            }
            for attempt in store.attempts(item["id"])
        ]
        attempts_html = (
            self._json_section("Execution attempts", attempts) if attempts else ""
        )
        status = item["status"]
        color = self._participant_color(item["participant_id"])
        performer = str(step.metadata.get("performed_by", "")).lower()
        performer_html = (
            f'<span class="performer {escape(performer, quote=True)}">'
            f'{escape("PERSON" if performer == "human" else performer.upper())}</span>'
            if performer in {"human", "llm"}
            else ""
        )
        return f'<details class="card {escape(status)}" style="--participant-color:{color}" data-node-id="{escape(item["id"], quote=True)}"><summary><span class="status">{escape(STATUS_LABELS.get(status, status))}</span>{performer_html}<div class="assignee">{escape(item["participant_id"])}</div><div class="item-id">{escape(item["id"][:8])}</div></summary><div class="detail"><div class="section"><h3>Survey</h3>{questions}</div>{state_html}{writes_html}{attempts_html}<div class="section"><h3>Lifecycle</h3><div class="metadata"><b>Created</b><span>{escape(item["created_at"])}</span><b>Opened</b><span>{escape(item["opened_at"] or "—")}</span><b>Completed</b><span>{escape(item["completed_at"] or "—")}</span></div></div></div></details>'

    @staticmethod
    def _question(question, answers) -> str:
        options = getattr(question, "question_options", None)
        option_html = (
            ""
            if not options
            else '<ul class="options">'
            + "".join(f"<li>{escape(str(option))}</li>" for option in options)
            + "</ul>"
        )
        response = answers.get(question.question_name)
        response_html = (
            ""
            if response is None
            else f'<div class="response"><b>Response</b>{escape(str(response))}</div>'
        )
        question_type = escape(question.question_type, quote=True)
        return f'<div class="question"><div class="question-type"><span class="q-glyph {question_type}"></span>{escape(question.question_type)} · {escape(question.question_name)}</div><div class="question-text">{escape(str(question.question_text))}</div>{option_html}{response_html}</div>'

    @staticmethod
    def _json_section(title: str, value: Any) -> str:
        return f'<div class="section"><h3>{escape(title)}</h3><pre>{escape(json.dumps(value, indent=2, ensure_ascii=False))}</pre></div>'

    @staticmethod
    def _event(event: dict[str, Any]) -> str:
        details = ", ".join(
            f"{key}={value}"
            for key, value in event.items()
            if key not in {"sequence", "kind", "work_item_id"}
        )
        return f'<div class="event"><span class="event-seq">{event["sequence"]}</span><div><div class="event-kind">{escape(event["kind"])}</div><div class="event-detail">{escape(details)}</div></div></div>'
