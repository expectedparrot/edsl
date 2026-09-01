"""Standalone, detailed HTML DAG visualization for workflow instances."""

from __future__ import annotations

from collections import Counter
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
}


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
        edges = [
            (source["id"], target["id"])
            for step in workflow.steps
            for dependency in step.after
            for source in by_step[dependency]
            for target in by_step[step.name]
        ]
        rows = "".join(
            self._step_row(step, by_step[step.name]) for step in workflow.steps
        )
        counts = Counter(item["status"] for item in items)
        summary = "".join(
            f'<span class="pill {escape(status)}">{escape(STATUS_LABELS.get(status, status.title()))} {count}</span>'
            for status, count in sorted(counts.items())
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
.summary {{ display:flex;gap:8px;flex-wrap:wrap;padding:13px 30px;background:white;border-bottom:1px solid #dbe1e9 }} .pill {{ border-radius:999px;padding:5px 10px;background:#eef1f5;font-size:12px;font-weight:750 }}
.pill.completed {{ color:#08734d;background:#dcfce7 }} .pill.ready {{ color:#1d4ed8;background:#dbeafe }} .pill.in_progress {{ color:#9a4b05;background:#ffedd5 }} .pill.skipped {{ color:#5b6471;background:#e5e7eb }}
.layout {{ display:grid;grid-template-columns:minmax(650px,1fr) 330px;min-height:calc(100vh - 125px) }} .dag-shell {{ overflow:auto;padding:35px 40px;position:relative }}
.dag {{ display:flex;flex-direction:column;gap:58px;position:relative;z-index:1;min-width:620px }} #edges {{ position:absolute;inset:35px 40px;pointer-events:none;overflow:visible;z-index:0 }}
.step-row {{ display:grid;grid-template-columns:180px minmax(390px,760px);gap:24px;justify-content:center;align-items:start }} .step-heading {{ padding-top:10px;text-align:right }}
.step-heading h2 {{ margin:0;font-size:15px }} .step-heading p {{ margin:5px 0 0;color:var(--muted);font-size:11px }} .condition {{ color:var(--purple)!important }} .node-lane {{ display:flex;gap:18px;flex-wrap:wrap }}
details.card {{ width:360px;border:1px solid #d5dce6;border-top:5px solid var(--gray);border-radius:12px;background:white;box-shadow:0 4px 14px rgba(16,24,40,.08);overflow:hidden }}
details.card.completed {{ border-top-color:var(--green) }} details.card.ready {{ border-top-color:var(--blue) }} details.card.in_progress {{ border-top-color:var(--amber) }} details.card.skipped {{ background:repeating-linear-gradient(135deg,#fff,#fff 9px,#f4f5f7 9px,#f4f5f7 18px) }}
summary {{ cursor:pointer;list-style:none;padding:14px 16px }} summary::-webkit-details-marker {{ display:none }} summary:after {{ content:'＋';float:right;color:var(--muted);font-size:17px }} details[open] summary:after {{ content:'−' }}
.status {{ display:inline-block;padding:3px 7px;margin-bottom:8px;border-radius:5px;background:#eef1f5;font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.04em }} .completed .status {{ color:#08734d;background:#dcfce7 }} .ready .status {{ color:#1d4ed8;background:#dbeafe }} .in_progress .status {{ color:#9a4b05;background:#ffedd5 }}
.assignee {{ font-weight:750;word-break:break-word }} .item-id {{ color:var(--muted);font:10px ui-monospace,monospace;margin-top:3px }} .detail {{ border-top:1px solid #e4e8ef;padding:4px 16px 16px;background:rgba(255,255,255,.92) }}
.section {{ margin-top:14px }} .section h3 {{ margin:0 0 7px;color:#4b5668;font-size:10px;text-transform:uppercase;letter-spacing:.08em }} .question {{ border-left:3px solid #cbd5e1;padding-left:10px;margin-top:10px }}
.question-type {{ color:var(--muted);font-size:10px }} .question-text {{ margin:3px 0 6px;font-weight:650 }} .options {{ margin:5px 0 0;padding-left:19px;color:#465166 }}
.response {{ margin-top:8px;padding:8px 10px;border-radius:7px;background:#ecfdf3;color:#12633f }} .response b {{ display:block;font-size:10px;text-transform:uppercase }} pre {{ margin:0;padding:9px;border-radius:7px;background:#f1f4f8;white-space:pre-wrap;word-break:break-word;font:11px/1.4 ui-monospace,monospace }}
.metadata {{ display:grid;grid-template-columns:86px 1fr;gap:4px 8px;font-size:11px }} .metadata b {{ color:var(--muted) }} aside {{ background:white;border-left:1px solid #d8dee8;padding:22px;overflow:auto }} aside h2 {{ margin:0 0 15px;font-size:15px }}
.event {{ display:grid;grid-template-columns:25px 1fr;gap:8px;margin-bottom:13px }} .event-seq {{ display:grid;place-items:center;width:23px;height:23px;border-radius:50%;color:white;background:#64748b;font-size:10px }} .event-kind {{ font-weight:700;font-size:12px }} .event-detail {{ color:var(--muted);font-size:11px;word-break:break-word }}
path.edge {{ stroke:var(--line);stroke-width:2;fill:none }} path.edge.active {{ stroke:#73a58d }} marker path {{ fill:var(--line);stroke:none }} @media(max-width:950px) {{ .layout {{ grid-template-columns:1fr }} aside {{ border-left:0;border-top:1px solid #d8dee8 }} }}
</style></head><body>
<header><h1>{escape(workflow.name)}</h1><p>Instance {escape(self.instance_id)} · {escape(instance["status"].title())}</p></header><div class="summary">{summary}<span class="pill">Select a node to expand details</span></div>
<main class="layout"><section class="dag-shell"><svg id="edges" aria-hidden="true"><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10z"/></marker></defs></svg><div class="dag">{rows}</div></section><aside><h2>Event timeline</h2>{timeline}</aside></main>
<script>const edges={edge_data};function drawEdges(){{const svg=document.getElementById('edges'),shell=svg.parentElement,base=shell.getBoundingClientRect();svg.querySelectorAll('.edge').forEach(p=>p.remove());svg.setAttribute('width',shell.scrollWidth-80);svg.setAttribute('height',shell.scrollHeight-70);for(const[fromId,toId]of edges){{const from=document.querySelector(`[data-node-id="${{CSS.escape(fromId)}}"]`),to=document.querySelector(`[data-node-id="${{CSS.escape(toId)}}"]`);if(!from||!to)continue;const a=from.getBoundingClientRect(),b=to.getBoundingClientRect(),x1=a.left+a.width/2-base.left-40+shell.scrollLeft,y1=a.bottom-base.top-35+shell.scrollTop,x2=b.left+b.width/2-base.left-40+shell.scrollLeft,y2=b.top-base.top-35+shell.scrollTop,bend=Math.max(22,(y2-y1)/2),p=document.createElementNS('http://www.w3.org/2000/svg','path');p.setAttribute('class','edge '+(from.classList.contains('completed')?'active':''));p.setAttribute('d',`M ${{x1}} ${{y1}} C ${{x1}} ${{y1+bend}}, ${{x2}} ${{y2-bend}}, ${{x2}} ${{y2}}`);p.setAttribute('marker-end','url(#arrow)');svg.appendChild(p);}}}}addEventListener('load',drawEdges);addEventListener('resize',drawEdges);document.querySelectorAll('details').forEach(d=>d.addEventListener('toggle',()=>requestAnimationFrame(drawEdges)));</script></body></html>"""

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.to_html(), encoding="utf-8")
        return destination.resolve()

    def _step_row(self, step, items) -> str:
        from .definition import Quorum

        condition = ""
        if step.enabled_when is not None:
            condition = (
                f'<p class="condition">Enable if '
                f"{escape(self._condition_text(step.enabled_when))}</p>"
            )
        dependency = (
            f"After {', '.join(step.after)}" if step.after else "Starts immediately"
        )
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
        return f'<section class="step-row"><div class="step-heading"><h2>{escape(step.name)}</h2><p>{escape(dependency)}</p><p>{escape(completion)}</p><p>{escape(visibility)}</p>{condition}</div><div class="node-lane">{cards}</div></section>'

    @classmethod
    def _condition_text(cls, condition) -> str:
        from .definition import (
            AllCondition,
            AnswerCondition,
            AnyCondition,
            NotCondition,
            OutputCountCondition,
            OutputDisagreementCondition,
            OutputMajorityCondition,
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
        return repr(condition)

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
        status = item["status"]
        expanded = " open" if status == "completed" else ""
        return f'<details class="card {escape(status)}" data-node-id="{escape(item["id"], quote=True)}"{expanded}><summary><span class="status">{escape(STATUS_LABELS.get(status, status))}</span><div class="assignee">{escape(item["participant_id"])}</div><div class="item-id">{escape(item["id"][:8])}</div></summary><div class="detail"><div class="section"><h3>Survey</h3>{questions}</div>{state_html}{writes_html}<div class="section"><h3>Lifecycle</h3><div class="metadata"><b>Created</b><span>{escape(item["created_at"])}</span><b>Opened</b><span>{escape(item["opened_at"] or "—")}</span><b>Completed</b><span>{escape(item["completed_at"] or "—")}</span></div></div></div></details>'

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
        return f'<div class="question"><div class="question-type">{escape(question.question_type)} · {escape(question.question_name)}</div><div class="question-text">{escape(str(question.question_text))}</div>{option_html}{response_html}</div>'

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
