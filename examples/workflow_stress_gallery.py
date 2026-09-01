"""Run a corpus of LLM-driven workflows and build an HTML design gallery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import inspect
from pathlib import Path
from typing import Callable

from edsl import (
    Agent,
    Model,
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionYesNo,
    Survey,
)
from edsl.sharedstate import (
    Command,
    Machine,
    SQLiteStateBackend,
    SharedState,
    SharedStateMap,
    T,
    append,
    current,
    field,
    input_,
    record,
    set_once,
    state_field,
)
from edsl.workflows import (
    AnswerCondition,
    EDSLAgentAnswerer,
    HumanStep,
    HumanWorkflow,
    ParticipantSelector,
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    WorkflowDAGVisualization,
    WorkflowSimulation,
    Workflow,
    if_,
    join_any,
    quorum,
    role,
)


@dataclass
class GalleryCase:
    slug: str
    title: str
    pattern: str
    workflow: HumanWorkflow
    state_maps: tuple[SharedStateMap, ...]
    agents: tuple[Agent, ...]
    builder: Callable
    awkward: tuple[str, ...]
    helpers: tuple[str, ...]


def artifact_map(state_id: str, field_name: str = "value") -> SharedStateMap:
    """Boilerplate deliberately kept visible as a candidate DSL helper."""
    machine = Machine(
        name="Artifact",
        constants={},
        fields={field_name: state_field(T.optional(T.text()), None)},
        commands={
            "submit": Command(
                inputs={"value": T.text()},
                effects=(set_once(field_name, input_("value")),),
            )
        },
        view={field_name: field(field_name)},
    )
    return SharedStateMap(SharedState(artifact=machine), state_id=state_id)


def log_map(state_id: str, field_name: str = "entries") -> SharedStateMap:
    machine = Machine(
        name="AppendLog",
        constants={},
        fields={field_name: state_field(T.sequence(), [])},
        commands={
            "add": Command(
                inputs={"actor": T.text(), "value": T.text()},
                effects=(
                    append(
                        field_name, record(actor=input_("actor"), value=input_("value"))
                    ),
                ),
            )
        },
        view={field_name: field(field_name)},
    )
    return SharedStateMap(SharedState(log=machine), state_id=state_id)


def brainstorm_case() -> GalleryCase:
    builder = Workflow("Parallel brainstorm and selection")
    idea = QuestionFreeText(
        question_name="idea",
        question_text="Suggest one concrete activity for the team retreat.",
    )
    suggestions = builder.step("suggest", Survey([idea]), assigned_to=role("ideator"))
    choice = QuestionFreeText(
        question_name="choice",
        question_text=(
            "Choose the strongest idea from "
            f"{suggestions.outputs(idea).template} and briefly explain why."
        ),
    )
    builder.step(
        "select", Survey([choice]), assigned_to=role("chair"), after=suggestions
    )
    workflow = builder.compile()
    agents = tuple(
        Agent(
            name=f"ideator-{n}@simulated.email",
            traits={"role": "ideator"},
            instruction=f"You are ideator {n}; be distinctive and concise.",
        )
        for n in range(1, 4)
    ) + (
        Agent(
            name="chair@simulated.email",
            traits={"role": "chair"},
            instruction="Choose exactly one submitted idea.",
        ),
    )
    return GalleryCase(
        "brainstorm",
        "Parallel brainstorm",
        "fan-out → fan-in",
        workflow,
        (),
        agents,
        brainstorm_case,
        (
            "Every ideator shares one step, so per-person deadlines or prompts cannot be expressed.",
            "Typed outputs remove the log machine, but per-person output schemas are still inferred from survey answers.",
        ),
        ("TaskPool(step, participants)", "typed output schema"),
    )


def blind_review_case() -> GalleryCase:
    submission = artifact_map("gallery-submission", "text")
    reviews = log_map("gallery-reviews")
    paper, review_log = submission.by("paper").artifact, reviews.by("paper").log
    draft = QuestionFreeText(
        question_name="draft",
        question_text="Write a one-paragraph claim about remote work productivity.",
    )
    verdict = QuestionFreeText(
        question_name="review",
        question_text="Independently critique this submission: {{ shared_state.artifact.text }}",
    )
    decision = QuestionFreeText(
        question_name="decision",
        question_text="Synthesize the independent reviews {{ shared_state.log.entries }} for submission {{ shared_state.artifact.text }}.",
    )
    workflow = HumanWorkflow(
        "Double-blind review",
        [
            HumanStep(
                "submit",
                Survey([draft]),
                ParticipantSelector.role("author"),
                writes=(paper.submit(value=draft.answer),),
            ),
            HumanStep(
                "review",
                Survey([verdict]),
                ParticipantSelector.role("reviewer"),
                after=("submit",),
                reads=(paper.read(),),
                writes=(
                    review_log.add(actor=current.agent.name, value=verdict.answer),
                ),
            ),
            HumanStep(
                "decide",
                Survey([decision]),
                ParticipantSelector.role("editor"),
                after=("review",),
                reads=(paper.read(), review_log.read()),
            ),
        ],
    )
    agents = (
        Agent(name="author@simulated.email", traits={"role": "author"}),
        Agent(
            name="reviewer-a@simulated.email",
            traits={"role": "reviewer"},
            instruction="Be skeptical.",
        ),
        Agent(
            name="reviewer-b@simulated.email",
            traits={"role": "reviewer"},
            instruction="Be constructive.",
        ),
        Agent(name="editor@simulated.email", traits={"role": "editor"}),
    )
    return GalleryCase(
        "blind-review",
        "Double-blind review",
        "private reads + fan-in",
        workflow,
        (submission, reviews),
        agents,
        blind_review_case,
        (
            "Privacy requires two separate state machines; reading the review log would leak earlier reviews to later reviewers.",
            "Visibility is an accidental consequence of which StateRead objects are attached.",
        ),
        ("private_output / reveal_to", "step.output visible_to=..."),
    )


def escalation_case() -> GalleryCase:
    report = artifact_map("gallery-incident", "report")
    incident = report.by("incident-7").artifact
    severity = QuestionMultipleChoice(
        question_name="severity",
        question_text="Classify this incident: production login failures affect all users.",
        question_options=["Low", "Medium", "High"],
    )
    response = QuestionFreeText(
        question_name="response",
        question_text="Give the immediate response plan for this High-severity incident: {{ shared_state.artifact.report }}",
    )
    workflow = HumanWorkflow(
        "Conditional incident escalation",
        [
            HumanStep(
                "classify",
                Survey([severity]),
                ParticipantSelector.role("on_call"),
                writes=(incident.submit(value=severity.answer),),
            ),
            HumanStep(
                "escalate",
                Survey([response]),
                ParticipantSelector.role("commander"),
                after=("classify",),
                enabled_when=AnswerCondition("classify", "severity", "High"),
                reads=(incident.read(),),
            ),
        ],
    )
    agents = (
        Agent(
            name="on-call@simulated.email",
            traits={"role": "on_call"},
            instruction="Classify widespread production login failure as High.",
        ),
        Agent(name="commander@simulated.email", traits={"role": "commander"}),
    )
    return GalleryCase(
        "escalation",
        "Incident escalation",
        "answer-gated branch",
        workflow,
        (report,),
        agents,
        escalation_case,
        (
            "The condition repeats step and question names as unchecked strings.",
            "A skipped escalation makes the whole workflow complete; there is no explicit terminal outcome.",
        ),
        ("classify.answer.equals('High')", "WorkflowOutcome"),
    )


def editorial_case() -> GalleryCase:
    builder = Workflow("Editorial branch join")
    first = QuestionFreeText(
        question_name="draft_1",
        question_text="Draft a two-sentence announcement for a community garden opening.",
    )
    draft = builder.step("draft", Survey([first]), assigned_to=role("writer"))
    check = QuestionYesNo(
        question_name="approved",
        question_text=f"Approve this draft? {draft.answer(first).template}",
    )
    review = builder.step(
        "check", Survey([check]), assigned_to=role("editor"), after=draft
    )
    approval_branch = if_(review.answer(check).equals("Yes"))
    revision = QuestionFreeText(
        question_name="draft_2",
        question_text=(
            "Revise the rejected draft using a warmer tone: "
            f"{draft.answer(first).template}"
        ),
    )
    revised = builder.step(
        "revise",
        Survey([revision]),
        assigned_to=role("writer"),
        when=approval_branch.otherwise,
    )
    accepted_copy = revised.answer(revision).template_or(draft.answer(first))
    publication = QuestionFreeText(
        question_name="publication",
        question_text=f"Prepare this accepted copy for publication: {accepted_copy}",
    )
    builder.step(
        "publish",
        Survey([publication]),
        assigned_to=role("publisher"),
        when=join_any(approval_branch.then, revised.completed),
    )
    workflow = builder.compile()
    agents = (
        Agent(name="writer@simulated.email", traits={"role": "writer"}),
        Agent(
            name="editor@simulated.email",
            traits={"role": "editor"},
            instruction="Reject announcements that do not explicitly welcome families.",
        ),
        Agent(name="publisher@simulated.email", traits={"role": "publisher"}),
    )
    return GalleryCase(
        "editorial",
        "Editorial revision",
        "exclusive branches",
        workflow,
        (),
        agents,
        editorial_case,
        (
            "The typed layer removes duplicated publisher steps, but template_or is still a specialized branch-merge operation.",
            "The compiled graph remains more verbose than a structured if/else block.",
        ),
        ("if_/else_ branch block", "typed union output for branch merges"),
    )


def procurement_case() -> GalleryCase:
    bids = log_map("gallery-bids", "bids")
    bid_log = bids.by("laptops").log
    bid = QuestionFreeText(
        question_name="bid",
        question_text="Submit a concise laptop supply bid with unit price and delivery time.",
    )
    award = QuestionFreeText(
        question_name="award",
        question_text="Select the best bid from {{ shared_state.log.bids }} using price and delivery time.",
    )
    workflow = HumanWorkflow(
        "Sealed procurement",
        [
            HumanStep(
                "bid",
                Survey([bid]),
                ParticipantSelector.role("vendor"),
                writes=(bid_log.add(actor=current.agent.name, value=bid.answer),),
            ),
            HumanStep(
                "award",
                Survey([award]),
                ParticipantSelector.role("buyer"),
                after=("bid",),
                reads=(bid_log.read(),),
            ),
        ],
    )
    agents = tuple(
        Agent(
            name=f"vendor-{n}@simulated.email",
            traits={"role": "vendor"},
            instruction=f"Offer {50 + n * 7} laptops at a plausible price; do not mention other vendors.",
        )
        for n in range(1, 4)
    ) + (Agent(name="buyer@simulated.email", traits={"role": "buyer"}),)
    return GalleryCase(
        "procurement",
        "Sealed procurement",
        "confidential fan-in",
        workflow,
        (bids,),
        agents,
        procurement_case,
        (
            "The bids are confidential only because the vendor step has writes without reads.",
            "There is no schema for bids, so the buyer parses prose.",
        ),
        ("sealed_collection", "typed step output schema"),
    )


def moderation_case() -> GalleryCase:
    vote = QuestionMultipleChoice(
        question_name="label",
        question_text="Label this post: 'You are an idiot and nobody wants you here.'",
        question_options=["Allow", "Warn", "Remove"],
    )
    builder = Workflow("Moderation panel")
    panel = builder.step(
        "vote",
        Survey([vote]),
        assigned_to=role("moderator"),
        completion=quorum(2),
        visible_to=role("lead"),
    )
    adjudicate = QuestionFreeText(
        question_name="decision",
        question_text=(
            f"Make a final moderation decision from {panel.outputs(vote).template}."
        ),
    )
    builder.step(
        "adjudicate",
        Survey([adjudicate]),
        assigned_to=role("lead"),
        after=panel,
        when=panel.outputs(vote).has_disagreement,
    )
    workflow = builder.compile()
    agents = (
        Agent(
            name="strict@simulated.email",
            traits={"role": "moderator"},
            instruction="Apply policy strictly.",
        ),
        Agent(
            name="contextual@simulated.email",
            traits={"role": "moderator"},
            instruction="Consider proportionality.",
        ),
        Agent(
            name="safety@simulated.email",
            traits={"role": "moderator"},
            instruction="Prioritize user safety.",
        ),
        Agent(name="lead@simulated.email", traits={"role": "lead"}),
    )
    return GalleryCase(
        "moderation",
        "Moderation panel",
        "quorum + adjudication",
        workflow,
        (),
        agents,
        moderation_case,
        (
            "A response already in flight may arrive after quorum and must be ignored safely.",
            "Quorum counts responses, not distinct semantic positions or confidence.",
        ),
        ("timeout fallback", "weighted or confidence-aware aggregation"),
    )


def translation_case() -> GalleryCase:
    text = log_map("gallery-translation", "versions")
    versions = text.by("notice").log
    questions = [
        QuestionFreeText(
            question_name="brief",
            question_text="Write a short English emergency-weather notice.",
        ),
        QuestionFreeText(
            question_name="translation",
            question_text="Translate the latest version into Spanish: {{ shared_state.log.versions[-1].value }}",
        ),
        QuestionFreeText(
            question_name="critique",
            question_text="Back-translate and identify any lost meaning: {{ shared_state.log.versions[-1].value }}",
        ),
        QuestionFreeText(
            question_name="revision",
            question_text="Revise the Spanish translation using this history: {{ shared_state.log.versions }}",
        ),
        QuestionYesNo(
            question_name="accepted",
            question_text="Is the final Spanish notice ready? {{ shared_state.log.versions[-1].value }}",
        ),
    ]
    names_roles = [
        ("brief", "owner"),
        ("translate", "translator"),
        ("backcheck", "reviewer"),
        ("revise", "translator"),
        ("accept", "owner"),
    ]
    steps = []
    for index, ((name, role_name), question) in enumerate(zip(names_roles, questions)):
        steps.append(
            HumanStep(
                name,
                Survey([question]),
                ParticipantSelector.role(role_name),
                after=((names_roles[index - 1][0],) if index else ()),
                reads=((versions.read(),) if index else ()),
                writes=(
                    (versions.add(actor=current.agent.name, value=question.answer),)
                    if name != "accept"
                    else ()
                ),
            )
        )
    workflow = HumanWorkflow("Translation QA chain", steps)
    agents = (
        Agent(name="owner@simulated.email", traits={"role": "owner"}),
        Agent(
            name="translator@simulated.email",
            traits={"role": "translator"},
            instruction="You are a professional Spanish translator.",
        ),
        Agent(
            name="reviewer@simulated.email",
            traits={"role": "reviewer"},
            instruction="Check semantic fidelity carefully.",
        ),
    )
    return GalleryCase(
        "translation",
        "Translation QA",
        "five-stage chain",
        workflow,
        (text,),
        agents,
        translation_case,
        (
            "The same translator receives two separate static steps; a reusable role task is not available.",
            "Passing artifacts requires a log machine and repeated Jinja indexing.",
        ),
        ("artifact.latest", "repeat_until(accepted)"),
    )


def cases() -> list[GalleryCase]:
    return [
        brainstorm_case(),
        blind_review_case(),
        escalation_case(),
        editorial_case(),
        procurement_case(),
        moderation_case(),
        translation_case(),
    ]


def run_case(case: GalleryCase, root: Path, answerer) -> dict:
    store = SQLiteWorkflowStore(root / "workflow.sqlite")
    backends = {
        state_map.state_id: SQLiteStateBackend(
            state_map, root / f"{state_map.state_id}.sqlite"
        )
        for state_map in case.state_maps
    }
    coordinator = WorkflowCoordinator(case.workflow, store, state_backends=backends)
    instance_id = coordinator.launch(case.agents)
    simulation = WorkflowSimulation(
        coordinator, {agent.name: agent for agent in case.agents}, answerer
    )
    simulation.run(instance_id)
    dag = WorkflowDAGVisualization(coordinator, instance_id).save(root / "dag.html")
    return {
        "case": case,
        "store": store,
        "instance_id": instance_id,
        "simulation": simulation,
        "dag": dag,
    }


def build_gallery(runs: list[dict], output: Path) -> Path:
    sections = []
    for run in runs:
        case, store, instance_id = run["case"], run["store"], run["instance_id"]
        responses = [
            (item["step_name"], store.item_answers(item["id"]))
            for item in store.items(instance_id)
            if store.item_answers(item["id"])
        ]
        response_html = "".join(
            f"<tr><td>{escape(step)}</td><td><pre>{escape(str(answer))}</pre></td></tr>"
            for step, answer in responses
        )
        awkward = "".join(f"<li>{escape(item)}</li>" for item in case.awkward)
        helpers = "".join(
            f"<li><code>{escape(item)}</code></li>" for item in case.helpers
        )
        source = escape(inspect.getsource(case.builder))
        relative_dag = run["dag"].relative_to(output.parent)
        sections.append(
            f"""<section class="case"><div class="case-head"><div><span class="pattern">{escape(case.pattern)}</span><h2>{escape(case.title)}</h2></div><button onclick="toggleSource(this)">Show source</button></div><iframe src="{escape(str(relative_dag), quote=True)}" loading="lazy"></iframe><div class="analysis"><div><h3>LLM responses</h3><table>{response_html}</table></div><div><h3>Awkward / risky</h3><ul>{awkward}</ul><h3>Candidate concepts</h3><ul>{helpers}</ul></div></div><pre class="source" hidden>{source}</pre></section>"""
        )
    output.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>Workflow language stress gallery</title><style>body{{margin:0;background:#eef1f5;color:#172033;font:14px/1.5 system-ui,sans-serif}}header{{padding:38px;max-width:1400px;margin:auto}}header h1{{margin:0}}header p{{max-width:850px;color:#5d6878}}.case{{margin:0 auto 34px;max-width:1400px;background:white;border:1px solid #d7dde6;border-radius:14px;overflow:hidden;box-shadow:0 5px 18px #18212f12}}.case-head{{display:flex;justify-content:space-between;align-items:center;padding:20px 24px}}h2{{margin:3px 0 0}}.pattern{{color:#6d28d9;font-size:11px;font-weight:800;text-transform:uppercase}}button{{border:1px solid #cbd3df;background:white;border-radius:7px;padding:7px 11px;cursor:pointer}}iframe{{display:block;width:100%;height:760px;border:0;border-top:1px solid #dde2ea;border-bottom:1px solid #dde2ea}}.analysis{{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:22px}}h3{{font-size:13px}}table{{width:100%;border-collapse:collapse}}td{{border-top:1px solid #e5e7eb;padding:8px;vertical-align:top}}pre{{white-space:pre-wrap;margin:0;font:11px/1.4 ui-monospace,monospace}}code{{color:#6d28d9}}.source{{padding:22px;background:#111827;color:#dbeafe;max-height:520px;overflow:auto}}@media(max-width:800px){{.analysis{{grid-template-columns:1fr}}}}</style></head><body><header><h1>Workflow language stress gallery</h1><p>{len(runs)} workflows executed with LLM respondents through simulated inboxes. Each case preserves its detailed DAG, rendered surveys, responses, state transitions, authoring friction, and proposed language concepts.</p></header>{"".join(sections)}<script>function toggleSource(b){{const p=b.closest('.case').querySelector('.source');p.hidden=!p.hidden;b.textContent=p.hidden?'Show source':'Hide source'}}</script></body></html>""",
        encoding="utf-8",
    )
    return output.resolve()


def run_gallery(output_dir: Path, model_name: str = "gpt-4o-mini") -> Path:
    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
    root = output_dir / "workflow_gallery_artifacts" / run_id
    root.mkdir(parents=True, exist_ok=False)
    answerer = EDSLAgentAnswerer(
        Model(model_name, service_name="openai"),
        run_options={"disable_remote_inference": False},
    )
    runs = []
    for case in cases():
        print(f"Running {case.slug}...", flush=True)
        runs.append(run_case(case, root / case.slug, answerer))
    return build_gallery(runs, output_dir / "workflow_stress_gallery.html")


if __name__ == "__main__":
    print(run_gallery(Path(__file__).parent))
