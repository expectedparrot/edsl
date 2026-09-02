"""Run a corpus of LLM-driven workflows and build an HTML design gallery."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import inspect
from pathlib import Path
from typing import Callable

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import PythonLexer

from edsl import (
    Agent,
    Model,
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionNumerical,
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
    RetryPolicy,
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    WorkflowDAGVisualization,
    WorkflowSimulation,
    Workflow,
    ExecutionPlan,
    any_of,
    chance,
    choose,
    if_,
    join_any,
    not_,
    quorum,
    role,
    human,
    llm,
    match,
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
    demo_instance_id: str | None = None
    execution_plan: ExecutionPlan | None = None


@dataclass(frozen=True)
class CaseNarrative:
    built: str
    learned: str


CASE_NARRATIVES = {
    "brainstorm": CaseNarrative(
        "Three ideators receive the same prompt independently. Their suggestions fan into one selector task, which receives the complete typed output collection.",
        "Fan-out and fan-in are natural in the current model. The remaining need is a reusable task-pool abstraction when prompts, deadlines, or eligibility differ by participant.",
    ),
    "blind-review": CaseNarrative(
        "An author submits one artifact, two reviewers independently critique it without seeing one another, and an editor receives the collected reviews for a final decision.",
        "Shared-state capabilities can implement blind review, but confidentiality is implicit in read/write wiring. Visibility deserves a policy that can be audited directly.",
    ),
    "escalation": CaseNarrative(
        "A reporter classifies an incident. A critical classification releases parallel technical and communications responses; their outputs then converge on a resolution step.",
        "Typed branch conditions make escalation readable. Operational use still needs priorities, deadlines, cancellation, and late evidence that can revise an earlier decision.",
    ),
    "editorial": CaseNarrative(
        "A writer drafts copy, an editor approves or rejects it, rejection releases a revision, and one publication step selects either the original or revised artifact.",
        "Typed references eliminate most fragile template strings. Branch joins are workable, although fallback selection would be clearer as an explicit accepted-artifact concept.",
    ),
    "procurement": CaseNarrative(
        "Three vendors submit sealed bids in parallel. A buyer receives the batch only after all vendors respond and chooses a supplier.",
        "The workflow captures sealed fan-in, but bids remain prose. Typed bid schemas, deterministic ranking, and per-vendor award or rejection notices are the next useful abstractions.",
    ),
    "moderation": CaseNarrative(
        "Three moderators are invited to vote, the first two responses satisfy quorum, and a lead adjudicator is contacted only when those completed votes disagree.",
        "Quorum and aggregate predicates compose cleanly. In-flight responses need explicit supersession semantics, and production systems will need timeouts and weighted votes.",
    ),
    "translation": CaseNarrative(
        "An owner writes a notice, a translator renders it in Spanish, a reviewer back-translates it, the translator revises it, and the owner performs final acceptance.",
        "Long artifact chains work but repeat substantial state and template boilerplate. A versioned artifact with latest(), history(), and repeat-until-accepted operations would be much clearer.",
    ),
    "delphi": CaseNarrative(
        "Six experts independently estimate a 2030 adoption rate and explain their reasoning. An anonymous facilitator synthesis is returned to the panel, experts revise, and a third round runs only if the second-round range remains wider than ten percentage points.",
        "The typed gate correctly stopped after round two, but the LLM facilitator misstated both the mean and whether round three was required. Derived values now inject those facts, and a serializable bounded repeat removes manual unrolling; runtime expansion and explicit anonymity remain useful next steps.",
    ),
    "peer-prediction": CaseNarrative(
        "Six informants privately report a Red/Blue signal and forecast the percentage of Red reports. A scorer receives identity-preserving sealed submissions and scores each forecast against a cyclic peer before notices go out.",
        "The run proved that identity must accompany answers for scoring. It also exposed inconsistent LLM arithmetic and a weak reporting incentive, making deterministic derived payments and typed peer matching high-priority features.",
    ),
    "public-goods": CaseNarrative(
        "Six strategic players receive ten tokens per round, contribute simultaneously, observe the prior contribution vector, and continue with 70% probability up to five rounds.",
        "Stable probabilistic gates work, and the agents adapted visibly. The serializable repeat block removes manual unrolling, while prompt-level payoff arithmetic and the lack of a common termination hook still argue for derive() and on_termination().",
    ),
    "mixed-research": CaseNarrative(
        "Three human field researchers submit independent observations. Two LLM coders classify the sealed batch, a human adjudicator is activated only when their structured labels disagree, and an LLM writer drafts a report from the codes and any adjudication.",
        "A separate serializable ExecutionPlan now routes participants to human, LLM, or scripted executors, while after_settled lets one report wait for optional adjudication without inheriting its skip. Production still needs a dispatcher registry and durable records of the executor selected for each attempt.",
    ),
    "ultimatum": CaseNarrative(
        "A proposer offers part of a ten-token endowment, a responder accepts or rejects after observing the offer, and a settlement agent reports the resulting allocation.",
        "Serializable piecewise expressions now compute both payoffs authoritatively. Participant-specific private payoff notices and a reusable game-settlement result remain useful abstractions.",
    ),
    "trust-game": CaseNarrative(
        "A sender invests part of a ten-token endowment, the investment is tripled, and a trustee decides how much of the resulting amount to return before settlement.",
        "The coordinator now performs authoritative balance arithmetic. A question constraint still cannot derive its maximum from an earlier answer, so validation of the trustee return remains too permissive.",
    ),
    "prisoners-dilemma": CaseNarrative(
        "Two players choose Cooperate or Defect simultaneously and privately; a settlement agent reveals the joint action and applies the stated payoff matrix.",
        "Sealed simultaneous choice now composes with deterministic pair matching, an executable payoff matrix, and private per-player payoff notices. Larger populations still need a runner that launches one instance per matched group.",
    ),
    "beauty-contest": CaseNarrative(
        "Six players choose numbers from zero to one hundred; an analyst computes two-thirds of the group mean and identifies the closest participant.",
        "The engine now computes the mean, target, identity-aware argmin, and an explicit all-winners tie policy. The LLM is limited to narrating the authoritative result.",
    ),
    "dictator": CaseNarrative(
        "A dictator unilaterally allocates a ten-token endowment between themself and a passive recipient, after which both parties receive private notices of the authoritative allocation.",
        "Single-answer arithmetic and participant-specific projections work cleanly, but the passive recipient still needs a survey-shaped notification task and balances are not posted to a durable ledger.",
    ),
    "first-price-auction": CaseNarrative(
        "Five bidders submit sealed integer bids for a private-value prize; the workflow computes the maximum bid, identifies every tied winner, and asks an auctioneer to announce the result.",
        "Maximum and identity-aware nearest-value ranking compose into a winner rule, but tie-breaking, bidder-specific values, and conditional winner payments need first-class auction or ranking operators.",
    ),
    "jury-vote": CaseNarrative(
        "Seven jurors vote Guilty or Not guilty in parallel and privately. Exactly one of two verdict branches is released according to the majority predicate after all ballots settle.",
        "A binary majority is concise as a workflow condition, although the DSL cannot yet expose vote counts as ordinary derived values or express supermajority and unanimity thresholds uniformly.",
    ),
    "market-entry": CaseNarrative(
        "Six firms simultaneously choose whether to enter a market with capacity for two profitable entrants. A market operator observes the sealed submissions and settles congestion-dependent returns.",
        "The graph and confidentiality policy are straightforward, but authoritative settlement still falls back to an LLM because collection count, per-participant map, and lookup-table expressions are missing.",
    ),
    "battle-of-sexes": CaseNarrative(
        "Two players simultaneously choose Opera or Football. They prefer either coordinated outcome to separation, but each player receives a larger payoff at a different coordinated outcome.",
        "The existing identity-preserving payoff matrix handles asymmetric coordination without new machinery. The main remaining repetition is boilerplate for settlement and private payoff notices.",
    ),
    "chicken": CaseNarrative(
        "Two drivers simultaneously choose Swerve or Straight. Standing firm against a yielding opponent pays best, mutual yielding is safe, and mutual aggression produces the worst outcome.",
        "This second asymmetric matrix confirms that settlement is general rather than Prisoner's-Dilemma-specific, while highlighting the need for a reusable two-player normal-form-game constructor.",
    ),
}

CODE_FORMATTER = HtmlFormatter(
    cssclass="highlight",
    linenos="table",
    style="github-dark",
)


def highlight_python(source: str) -> str:
    """Return self-contained Pygments markup for a Python source fragment."""
    return highlight(source, PythonLexer(), CODE_FORMATTER)


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


def peer_prediction_case() -> GalleryCase:
    """Sealed reports scored against a peer rather than observed ground truth."""
    builder = Workflow(
        "Peer prediction without ground truth",
        metadata={
            "mechanism": "cyclic-peer quadratic score",
            "respondent_count": 6,
        },
    )


    signal = QuestionMultipleChoice(
        question_name="reported_signal",
        question_text=(
            "Your private signal is {{ participant.private_signal }}. Report which "
            "signal you observed. Your report remains sealed until all six people "
            "have responded."
        ),
        question_options=["Red", "Blue"],
    )
    forecast = QuestionNumerical(
        question_name="predicted_red_percent",
        question_text=(
            "What percentage of the other five respondents do you predict will "
            "report Red? Give a number from 0 to 100."
        ),
        min_value=0,
        max_value=100,
        include_comment=False,
    )
    reports = builder.step(
        "sealed-report",
        Survey([signal, forecast]),
        assigned_to=role("respondent"),
        visible_to=role("scorer"),
    )
    scoring_report = QuestionFreeText(
        question_name="scoring_report",
        question_text=(
            "Score this identity-preserving sealed batch: "
            f"{reports.submissions.template}. Sort respondents by participant_id "
            "and pair each with the next respondent cyclically. For forecast p as a "
            "fraction and peer outcome y=1 for Red or 0 for Blue, award "
            "100 * (1 - (p-y)^2), rounded to two decimals. Return one concise line "
            "per respondent showing their report, forecast, peer outcome, and score."
        ),
    )
    scored = builder.step(
        "score",
        Survey([scoring_report]),
        assigned_to=role("scorer"),
        after=reports,
        visible_to=role("respondent"),
    )
    receipt = QuestionYesNo(
        question_name="received",
        question_text=(
            "Your participant ID is {{ participant.name }}. Here is the score report: "
            f"{scored.answer(scoring_report).template}. Do you acknowledge receipt?"
        ),
    )
    builder.step(
        "score-notice",
        Survey([receipt]),
        assigned_to=role("respondent"),
        after=scored,
    )
    signals = ("Red", "Blue", "Red", "Red", "Blue", "Red")
    instructions = (
        "Report your signal honestly and give a calibrated forecast.",
        "You may strategically shade reports if it improves expected score.",
        "Be literal and numerically conservative.",
        "Use your signal as evidence about what others probably observed.",
        "Think independently; do not assume consensus.",
        "Maximize expected score under the stated mechanism.",
    )
    respondents = tuple(
        Agent(
            name=f"informant-{index}@simulated.email",
            traits={"role": "respondent", "private_signal": private_signal},
            instruction=instructions[index - 1],
        )
        for index, private_signal in enumerate(signals, start=1)
    )
    agents = respondents + (
        Agent(
            name="mechanism@simulated.email",
            traits={"role": "scorer"},
            instruction="Apply the specified scoring rule exactly and transparently.",
        ),
    )
    return GalleryCase(
        "peer-prediction",
        "Peer prediction / information elicitation",
        "sealed reports → peer scoring → notices",
        builder.compile(),
        (),
        agents,
        peer_prediction_case,
        (
            "The first live scorer produced inconsistent arithmetic, confirming that scoring must be deterministic.",
            "The elicited signal affects a peer's score but not the reporter's own payoff, so truthful reporting is not yet incentive-compatible.",
            "Every respondent receives the full report because per-recipient output projection is absent.",
            "Peer assignment is prose rather than a typed matching policy.",
        ),
        (
            "derive(scores, from=reports, using=quadratic_peer_score)",
            "project(score, key=participant.id)",
            "match_each(respondent, peer, strategy='random-derangement')",
        ),
    )


def mixed_research_case() -> GalleryCase:
    """Human observations, LLM coding, human adjudication, and LLM reporting."""
    builder = Workflow(
        "Mixed human–LLM research pipeline",
        metadata={"study": "urban public-space observations"},
    )
    observation = QuestionFreeText(
        question_name="observation",
        question_text=(
            "Record one concrete observation from the assigned public space. "
            "Describe behavior and context without interpreting intent."
        ),
    )
    observations = builder.step(
        "collect-observations",
        Survey([observation]),
        assigned_to=role("field-researcher"),
        visible_to=(role("coder"), role("adjudicator"), role("report-writer")),
        metadata={"performed_by": "human", "channel": "humanize-email"},
    )
    theme = QuestionMultipleChoice(
        question_name="dominant_theme",
        question_text=(
            "Independently code the dominant theme in this sealed batch: "
            f"{observations.submissions.template}"
        ),
        question_options=["social-connection", "active-mobility", "solitude"],
    )
    valence = QuestionMultipleChoice(
        question_name="overall_valence",
        question_text="Classify the overall valence of the same batch.",
        question_options=["positive", "mixed", "negative"],
    )
    rationale = QuestionFreeText(
        question_name="coding_rationale",
        question_text="Give a short evidence-based rationale for both labels.",
    )
    codes = builder.step(
        "independent-coding",
        Survey([theme, valence, rationale]),
        assigned_to=role("coder"),
        after=observations,
        visible_to=(role("adjudicator"), role("report-writer")),
        metadata={"performed_by": "llm", "model_policy": "research-coder"},
    )
    disagreement = any_of(
        codes.outputs(theme).has_disagreement,
        codes.outputs(valence).has_disagreement,
    )
    resolution = QuestionFreeText(
        question_name="resolution",
        question_text=(
            "The coders disagreed. Review their submissions "
            f"{codes.submissions.template}. State final dominant_theme and "
            "overall_valence labels, with a brief evidence-based justification."
        ),
    )
    adjudication = builder.step(
        "human-adjudication",
        Survey([resolution]),
        assigned_to=role("adjudicator"),
        after=codes,
        when=disagreement,
        visible_to=role("report-writer"),
        metadata={"performed_by": "human", "channel": "humanize-email"},
    )
    report = QuestionFreeText(
        question_name="report",
        question_text=(
            "Draft a concise research memo from observations "
            f"{observations.outputs(observation).template}, codes "
            f"{codes.submissions.template}, and any adjudication "
            f"{adjudication.outputs(resolution).optional()}. Distinguish facts from "
            "interpretation and disclose whether adjudication occurred."
        ),
    )
    builder.step(
        "draft-report",
        Survey([report]),
        assigned_to=role("report-writer"),
        after_settled=adjudication,
        metadata={"performed_by": "llm", "model_policy": "research-writer"},
    )
    role_specs = (
        ("fieldworker-1", "field-researcher", "human", "Observe accessibility and movement."),
        ("fieldworker-2", "field-researcher", "human", "Observe social interaction."),
        ("fieldworker-3", "field-researcher", "human", "Observe solitary use and comfort."),
        ("coder-a", "coder", "llm", "Code literally; privilege repeated behavior."),
        ("coder-b", "coder", "llm", "Code conservatively; privilege counterexamples."),
        ("adjudicator", "adjudicator", "human", "Resolve ambiguity as a research lead."),
        ("writer", "report-writer", "llm", "Write a transparent, restrained memo."),
    )
    agents = tuple(
        Agent(
            name=f"{name}@simulated.email",
            traits={"role": role_name, "intended_performer": performer},
            instruction=instruction,
        )
        for name, role_name, performer, instruction in role_specs
    )
    return GalleryCase(
        "mixed-research",
        "Mixed human–LLM research pipeline",
        "people → LLMs → conditional people → LLM",
        builder.compile(),
        (),
        agents,
        mixed_research_case,
        (
            "Execution routing is separate from the scientific workflow, so one protocol can be rehearsed and deployed differently.",
            "The all-LLM rehearsal cannot test email latency, abandonment, or authentic human variance.",
            "after_settled removes the duplicated report branches while preserving the wait for optional adjudication.",
            "Named model policies are not resolved to pinned, auditable model configurations.",
        ),
        (
            "adapter registry keyed by ExecutorSpec.kind",
            "persist the resolved executor on each attempt",
            "optional_output(adjudication).otherwise(codes)",
        ),
        execution_plan=(
            ExecutionPlan()
            .bind(role("field-researcher"), human(channel="humanize-email"))
            .bind(role("coder"), llm(model_policy="research-coder"))
            .bind(role("adjudicator"), human(channel="humanize-email"))
            .bind(role("report-writer"), llm(model_policy="research-writer"))
        ),
    )


def delphi_case() -> GalleryCase:
    """Anonymous expert forecasting with feedback and an early convergence gate."""
    builder = Workflow(
        "Three-round Delphi forecast",
        metadata={
            "method": "Delphi",
            "panel_size": 6,
            "convergence_range": 10,
            "maximum_rounds": 3,
        },
    )

    def forecast_survey(round_number: int, feedback: str | None = None) -> Survey:
        context = (
            "Make your initial estimate independently."
            if feedback is None
            else f"Review this anonymous facilitator synthesis: {feedback}"
        )
        return Survey(
            [
                QuestionNumerical(
                    question_name="estimate",
                    question_text=(
                        "Delphi forecast, round "
                        f"{round_number}. What percentage of new US passenger "
                        "vehicle sales in 2030 will be fully electric? Give a "
                        f"number from 0 to 100. {context}"
                    ),
                    min_value=0,
                    max_value=100,
                    include_comment=False,
                ),
                QuestionFreeText(
                    question_name="rationale",
                    question_text=(
                        "Briefly state the strongest evidence or assumption behind "
                        "your estimate. Do not identify yourself."
                    ),
                ),
            ]
        )

    def synthesis_survey(round_number: int, forecasts) -> Survey:
        summary = QuestionFreeText(
            question_name="summary",
            question_text=(
                f"Anonymously synthesize Delphi round {round_number}. Estimates: "
                f"{forecasts.outputs('estimate').template}. Rationales: "
                f"{forecasts.outputs('rationale').template}. Report the range and "
                "central tendency, explain the main sources of disagreement, and "
                "give no recommendation or participant identities."
            ),
        )
        return Survey([summary])

    forecasts_by_round = {}
    syntheses_by_round = {}

    def build_round(iteration):
        number = iteration.number
        feedback = (
            None
            if number == 1
            else syntheses_by_round[number - 1].answer("summary").template
        )
        forecasts = iteration.step(
            "round",
            forecast_survey(number, feedback),
            assigned_to=role("expert"),
            visible_to=role("facilitator"),
        )
        synthesis = iteration.step(
            "synthesis",
            synthesis_survey(number, forecasts),
            assigned_to=role("facilitator"),
            after=forecasts,
            visible_to=(role("expert"), role("facilitator")),
        )
        iteration.stop_when(forecasts.outputs("estimate").range().at_most(10))
        forecasts_by_round[number] = forecasts
        syntheses_by_round[number] = synthesis

    builder.repeat(
        "delphi-rounds", max_iterations=3, min_iterations=2, build=build_round
    )
    round_2 = forecasts_by_round[2]
    synthesis_2 = syntheses_by_round[2]
    synthesis_3 = syntheses_by_round[3]
    stats = builder.derive(
        "round-2-statistics",
        mean=round_2.outputs("estimate").mean(),
        median=round_2.outputs("estimate").median(),
        minimum=round_2.outputs("estimate").minimum(),
        maximum=round_2.outputs("estimate").maximum(),
        spread=round_2.outputs("estimate").range(),
    )
    outcome = builder.derive(
        "round-2-outcome",
        converged=stats.field("spread").expression.compare_at_most(10),
    )
    converged = outcome.field("converged").equals(True)
    final_summary = QuestionFreeText(
        question_name="final_summary",
        question_text=(
            "Publish the final anonymous Delphi result using the latest available "
            "synthesis: "
            f"{synthesis_3.answer('summary').template_or(synthesis_2.answer('summary'))}. "
            f"The authoritative round-2 statistics are: mean "
            f"{stats.field('mean').template}, median "
            f"{stats.field('median').template}, minimum "
            f"{stats.field('minimum').template}, maximum "
            f"{stats.field('maximum').template}, and range "
            f"{stats.field('spread').template}. The authoritative convergence result "
            f"is {outcome.field('converged').template}. These values are computed by "
            "the workflow engine; reproduce them exactly."
        ),
    )
    builder.step(
        "final-report",
        Survey([final_summary]),
        assigned_to=role("facilitator"),
        after=synthesis_2,
        when=any_of(converged, synthesis_3.completed),
    )

    expert_instructions = (
        "Emphasize technology cost curves and learning rates.",
        "Emphasize charging infrastructure and grid constraints.",
        "Emphasize policy, regulation, and manufacturer commitments.",
        "Be a skeptical forecaster attentive to base rates and bottlenecks.",
        "Use adoption-curve analogies and quantify uncertainty.",
        "Emphasize consumer behavior, prices, and vehicle availability.",
    )
    agents = tuple(
        Agent(
            name=f"expert-{index}@simulated.email",
            traits={"role": "expert", "panel_number": index},
            instruction=instruction,
        )
        for index, instruction in enumerate(expert_instructions, start=1)
    ) + (
        Agent(
            name="facilitator@simulated.email",
            traits={"role": "facilitator"},
            instruction=(
                "Act as a neutral Delphi facilitator. Preserve anonymity, summarize "
                "disagreement faithfully, and do not invent panel responses."
            ),
        ),
    )
    return GalleryCase(
        "delphi",
        "Delphi expert forecast",
        "anonymous rounds + synthesis + convergence",
        builder.compile(),
        (),
        agents,
        delphi_case,
        (
            "The repeat body is concise, but bounded iterations are currently materialized into concrete steps at compile time.",
            "The facilitator estimates summary statistics in prose instead of consuming deterministic derived values.",
            "A raw range is sensitive to one outlier and may be a poor consensus measure for larger panels.",
        ),
        (
            "runtime materialization for very large or unbounded repeats",
            "derive_statistics(outputs, median=True, iqr=True, range=True)",
            "anonymous_panel(role='expert')",
        ),
    )


def public_goods_case() -> GalleryCase:
    """A simultaneous, repeated public-goods game delivered through inboxes."""
    builder = Workflow(
        "Probabilistic public goods game",
        metadata={
            "endowment_per_round": 10,
            "group_size": 6,
            "public_good_multiplier": 2,
            "continuation_probability": 0.7,
            "maximum_rounds": 5,
        },
    )
    rounds_by_number = {}

    def build_round(iteration):
        round_number = iteration.number
        previous = rounds_by_number.get(round_number - 1)
        history = (
            "This is round 1; there is no prior contribution history."
            if previous is None
            else (
                "The previous round's six contributions were "
                f"{previous.outputs('contribution').template}."
            )
        )
        contribution = QuestionMultipleChoice(
            question_name="contribution",
            question_text=(
                f"Public-goods game, round {round_number}. You receive 10 tokens. "
                "Choose how many to contribute to the group account. The group "
                "account is doubled and divided equally among all six players; you "
                f"also keep tokens you do not contribute. {history}"
            ),
            question_options=list(range(11)),
        )
        current_round = iteration.step(
            "round",
            Survey([contribution]),
            assigned_to=role("player"),
        )
        iteration.stop_when(
            not_(chance(0.7, key=f"continue-after-round-{round_number}"))
        )
        rounds_by_number[round_number] = current_round

    builder.repeat("public-goods-rounds", max_iterations=5, build=build_round)
    agents = tuple(
        Agent(
            name=f"player-{index}@simulated.email",
            traits={"role": "player", "player_number": index},
            instruction=instruction,
        )
        for index, instruction in enumerate(
            (
                "Cooperate unless the group persistently free-rides.",
                "Maximize your own expected token payoff.",
                "Begin generously, then reciprocate the group's behavior.",
                "Contribute near the group average from the preceding round.",
                "Prefer fair outcomes and discourage free-riding.",
                "Use a cautious mixed strategy and adapt to observed contributions.",
            ),
            start=1,
        )
    )
    return GalleryCase(
        "public-goods",
        "Probabilistic public-goods game",
        "simultaneous rounds + random stopping",
        builder.compile(),
        (),
        agents,
        public_goods_case,
        (
            "The repeat block removes manual unrolling, but its bounded iterations are still materialized at compile time.",
            "Payoffs and round summaries live in prompt prose rather than typed derived values.",
            "There is no terminal debrief step that naturally joins every possible stopping round.",
        ),
        (
            "runtime materialization for very large or unbounded repeats",
            "derive('group_return', expression=...) ",
            "on_termination(debrief)",
        ),
        "gallery-public-goods-11",
    )


def _game_agents(*roles: str) -> tuple[Agent, ...]:
    return tuple(
        Agent(
            name=f"{role}@simulated.email",
            traits={"role": role},
            instruction="Maximize your token payoff while reasoning strategically.",
        )
        for role in roles
    )


def ultimatum_case() -> GalleryCase:
    builder = Workflow("Ultimatum game", metadata={"endowment": 10})
    offer_q = QuestionNumerical(
        question_name="offer", question_text="You have 10 tokens. Offer the responder an integer from 0 to 10.",
        min_value=0, max_value=10, include_comment=False,
    )
    offer = builder.step("offer", Survey([offer_q]), assigned_to=role("proposer"))
    accept_q = QuestionYesNo(
        question_name="accept", question_text=f"The proposer offered you {offer.answer(offer_q).template} of 10 tokens. Accept?",
    )
    response = builder.step("respond", Survey([accept_q]), assigned_to=role("responder"), after=offer)
    accepted = response.answer("accept").value.compare_equals("Yes")
    payoffs = builder.derive(
        "payoffs",
        proposer=choose(accepted, 10 - offer.answer("offer").value, 0),
        responder=choose(accepted, offer.answer("offer").value, 0),
    )
    settlement_q = QuestionFreeText(
        question_name="settlement", question_text=f"Report authoritative payoffs: proposer={payoffs.field('proposer').template}, responder={payoffs.field('responder').template}.",
    )
    builder.step("settle", Survey([settlement_q]), assigned_to=role("settler"), after=response)
    return GalleryCase("ultimatum", "Ultimatum game", "sequential offer → response → settlement", builder.compile(), (), _game_agents("proposer", "responder", "settler"), ultimatum_case,
        ("Derived payoffs are not yet participant-addressable private values.", "The settlement narration is still a survey task."),
        ("payoff.for_participant(role)", "deterministic settlement step"))


def trust_game_case() -> GalleryCase:
    builder = Workflow("Trust game", metadata={"endowment": 10, "multiplier": 3})
    sent_q = QuestionNumerical(question_name="sent", question_text="You have 10 tokens. Send an integer from 0 to 10; it will be tripled.", min_value=0, max_value=10, include_comment=False)
    sent = builder.step("send", Survey([sent_q]), assigned_to=role("sender"))
    returned_q = QuestionNumerical(question_name="returned", question_text=f"The sender sent {sent.answer(sent_q).template}; you receive three times that amount. Return an integer between 0 and the amount you received.", min_value=0, max_value=30, include_comment=False)
    returned = builder.step("return", Survey([returned_q]), assigned_to=role("trustee"), after=sent, answer_bounds={returned_q: (0, sent.answer("sent").value * 3)})
    balances = builder.derive("balances", sender=10 - sent.answer("sent").value + returned.answer("returned").value, trustee=sent.answer("sent").value * 3 - returned.answer("returned").value)
    settle_q = QuestionFreeText(question_name="settlement", question_text=f"Report authoritative balances: sender={balances.field('sender').template}, trustee={balances.field('trustee').template}.")
    builder.step("settle", Survey([settle_q]), assigned_to=role("settler"), after=returned)
    return GalleryCase("trust-game", "Trust game", "investment → multiplied transfer → return", builder.compile(), (), _game_agents("sender", "trustee", "settler"), trust_game_case,
        ("The trustee question has a static maximum of 30 rather than 3 × the realized transfer.", "Derived balances are authoritative but not privately projected."),
        ("max_value=expression", "balance.for_participant(role)"))


def prisoners_dilemma_case() -> GalleryCase:
    builder = Workflow("Prisoner's dilemma", metadata={"matching": match(role("player"), size=2).to_dict()})
    choice_q = QuestionMultipleChoice(question_name="action", question_text="Privately choose an action.", question_options=["Cooperate", "Defect"])
    choices = builder.step("choose", Survey([choice_q]), assigned_to=role("player"), visible_to=role("settler"))
    payoffs = builder.derive("payoffs", by_participant=choices.submissions.payoff_matrix("action", {"CC": (3, 3), "CD": (0, 5), "DC": (5, 0), "DD": (1, 1)}, action_codes={"Cooperate": "C", "Defect": "D"}))
    settle_q = QuestionFreeText(question_name="settlement", question_text=f"Report these authoritative participant payoffs: {payoffs.field('by_participant').template}.")
    settled = builder.step("settle", Survey([settle_q]), assigned_to=role("settler"), after=choices)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative private payoff is {payoffs.field('by_participant').for_participant()} tokens.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Choose independently to maximize payoff.") for i in range(1, 3))
    return GalleryCase("prisoners-dilemma", "Prisoner's dilemma", "sealed simultaneous actions → matrix settlement", builder.compile(), (), players + _game_agents("settler"), prisoners_dilemma_case,
        ("Matching partitions a roster but a higher-level runner must still launch each pair.", "Payoff notices are survey tasks rather than ledger credits."),
        ("run_for_each(match(...))", "credit(payoff)"))


def beauty_contest_case() -> GalleryCase:
    builder = Workflow("Two-thirds beauty contest", metadata={"target_multiplier": 2 / 3})
    number_q = QuestionNumerical(question_name="number", question_text="Choose a number from 0 to 100. The winner is closest to two-thirds of the group mean.", min_value=0, max_value=100, include_comment=False)
    choices = builder.step("choose", Survey([number_q]), assigned_to=role("player"), visible_to=role("analyst"))
    stats = builder.derive("target", mean=choices.outputs(number_q).mean(), target=choices.outputs(number_q).mean() * (2 / 3))
    winners = builder.derive("ranking", winners=choices.submissions.closest_to("number", stats.field("target").expression, ties="all"))
    result_q = QuestionFreeText(question_name="result", question_text=f"Authoritative mean={stats.field('mean').template}, target={stats.field('target').template}, and winner list={winners.field('winners').template}. Report them exactly.")
    builder.step("rank", Survey([result_q]), assigned_to=role("analyst"), after=choices)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction=f"You are level-{i-1} strategic reasoner.") for i in range(1, 7))
    return GalleryCase("beauty-contest", "Two-thirds beauty contest", "simultaneous numbers → mean → nearest winner", builder.compile(), (), players + _game_agents("analyst"), beauty_contest_case,
        ("Ranking is authoritative, but prizes are not ledger operations.", "Winner notices still require another explicit fan-out step."),
        ("credit(winners, prize)", "notify_each(winners)"))


def dictator_case() -> GalleryCase:
    builder = Workflow("Dictator game", metadata={"endowment": 10})
    transfer_q = QuestionNumerical(question_name="transfer", question_text="You control 10 tokens. Give the recipient an integer from 0 to 10.", min_value=0, max_value=10, include_comment=False)
    allocation = builder.step("allocate", Survey([transfer_q]), assigned_to=role("dictator"))
    balances = builder.derive("balances", dictator=10 - allocation.answer("transfer").value, recipient=allocation.answer("transfer").value)
    dictator_notice = QuestionFreeText(question_name="acknowledgement", question_text=f"Your authoritative final balance is {balances.field('dictator').template} tokens. Acknowledge it.")
    recipient_notice = QuestionFreeText(question_name="acknowledgement", question_text=f"The dictator transferred you {balances.field('recipient').template} tokens. Acknowledge it.")
    builder.step("dictator-notice", Survey([dictator_notice]), assigned_to=role("dictator"), after=allocation)
    builder.step("recipient-notice", Survey([recipient_notice]), assigned_to=role("recipient"), after=allocation)
    return GalleryCase("dictator", "Dictator game", "unilateral allocation → private notices", builder.compile(), (), _game_agents("dictator", "recipient"), dictator_case,
        ("A passive recipient must answer a survey merely to receive a result.", "Balances are computed but are not durable token-ledger entries."),
        ("notify(role, payload)", "credit(participant, amount)"))


def first_price_auction_case() -> GalleryCase:
    builder = Workflow("First-price sealed-bid auction", metadata={"prize": "one indivisible item"})
    bid_q = QuestionNumerical(question_name="bid", question_text="Privately submit an integer bid from 0 to 100 for the item. The highest bidder wins and pays their bid.", min_value=0, max_value=100, include_comment=False)
    bids = builder.step("sealed-bid", Survey([bid_q]), assigned_to=role("bidder"), visible_to=role("auctioneer"))
    highest = builder.derive("auction", highest_bid=bids.outputs("bid").maximum())
    winners = builder.derive("ranking", winners=bids.submissions.closest_to("bid", highest.field("highest_bid").expression, ties="all"))
    result_q = QuestionFreeText(question_name="result", question_text=f"Announce the authoritative highest bid {highest.field('highest_bid').template} and tied winner list {winners.field('winners').template}. Do not invent a tie-break.")
    builder.step("settle", Survey([result_q]), assigned_to=role("auctioneer"), after=bids)
    bidders = tuple(Agent(name=f"bidder-{i}@simulated.email", traits={"role": "bidder", "private_value": 20 + 13 * i}, instruction="Bid strategically. Your private value is in your traits; do not bid above it.") for i in range(1, 6))
    return GalleryCase("first-price-auction", "First-price sealed-bid auction", "sealed bids → maximum → identity-aware winners", builder.compile(), (), bidders + _game_agents("auctioneer"), first_price_auction_case,
        ("closest_to(maximum) is an indirect spelling of argmax.", "Tie resolution and private-value utility require additional operators."),
        ("submissions.argmax_by('bid')", "tie_break(strategy='seeded-random')", "auction(first_price=True)"))


def jury_vote_case() -> GalleryCase:
    builder = Workflow("Seven-person jury vote", metadata={"threshold": "simple majority"})
    vote_q = QuestionMultipleChoice(question_name="verdict", question_text="Vote independently based on the evidence: Guilty or Not guilty.", question_options=["Guilty", "Not guilty"])
    votes = builder.step("secret-ballot", Survey([vote_q]), assigned_to=role("juror"), visible_to=role("clerk"))
    guilty_q = QuestionFreeText(question_name="verdict", question_text="The authoritative majority verdict is Guilty. Record it.")
    acquit_q = QuestionFreeText(question_name="verdict", question_text="The authoritative majority verdict is Not guilty. Record it.")
    builder.step("guilty-verdict", Survey([guilty_q]), assigned_to=role("clerk"), after=votes, when=votes.outputs("verdict").majority_is("Guilty"))
    builder.step("not-guilty-verdict", Survey([acquit_q]), assigned_to=role("clerk"), after=votes, when=not_(votes.outputs("verdict").majority_is("Guilty")))
    jurors = tuple(Agent(name=f"juror-{i}@simulated.email", traits={"role": "juror", "evidence_signal": "inculpatory" if i <= 4 else "exculpatory"}, instruction="Vote from your private evidence signal and reasonable doubt standard.") for i in range(1, 8))
    return GalleryCase("jury-vote", "Seven-person jury vote", "sealed ballots → mutually exclusive verdict", builder.compile(), (), jurors + _game_agents("clerk"), jury_vote_case,
        ("Vote counts cannot be injected into the verdict as derived data.", "The majority helper does not generalize visibly to 2/3 or unanimity."),
        ("outputs.count_value('Guilty')", "threshold(value, at_least=...)"))


def market_entry_case() -> GalleryCase:
    builder = Workflow("Market-entry game", metadata={"capacity": 2, "entry_cost": 4, "market_revenue": 12})
    choice_q = QuestionMultipleChoice(question_name="decision", question_text="Choose Enter or Stay out. Entrants split 12 revenue equally and each pays a cost of 4.", question_options=["Enter", "Stay out"])
    decisions = builder.step("entry-decision", Survey([choice_q]), assigned_to=role("firm"), visible_to=role("operator"))
    settlement_q = QuestionFreeText(question_name="settlement", question_text=f"Settle the market from these identity-preserving submissions: {decisions.submissions.template}. Count entrants; each entrant earns 12 divided by entrant count minus 4, while firms staying out earn 0.")
    builder.step("settle", Survey([settlement_q]), assigned_to=role("operator"), after=decisions)
    firms = tuple(Agent(name=f"firm-{i}@simulated.email", traits={"role": "firm"}, instruction="Choose strategically, anticipating congestion from five other firms.") for i in range(1, 7))
    return GalleryCase("market-entry", "Market-entry game", "simultaneous entry → congestion settlement", builder.compile(), (), firms + _game_agents("operator"), market_entry_case,
        ("Entrant counting and participant-wise payoff mapping are still prompt instructions.", "An LLM, rather than the coordinator, performs authoritative arithmetic."),
        ("submissions.count_where(...) ", "submissions.map_payoff(...) ", "lookup_table(...)"))


def battle_of_sexes_case() -> GalleryCase:
    builder = Workflow("Battle of the Sexes", metadata={"source": "Handbook chapter 3"})
    choice_q = QuestionMultipleChoice(question_name="action", question_text="Choose independently: Opera or Football. You prefer coordinating, but player 1 prefers Opera and player 2 prefers Football.", question_options=["Opera", "Football"])
    choices = builder.step("choose", Survey([choice_q]), assigned_to=role("player"), visible_to=role("settler"))
    payoffs = builder.derive("payoffs", by_participant=choices.submissions.payoff_matrix("action", {"OO": (2, 1), "OF": (0, 0), "FO": (0, 0), "FF": (1, 2)}, action_codes={"Opera": "O", "Football": "F"}))
    settle_q = QuestionFreeText(question_name="result", question_text=f"Record the authoritative participant payoffs {payoffs.field('by_participant').template}.")
    settled = builder.step("settle", Survey([settle_q]), assigned_to=role("settler"), after=choices)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your private payoff is {payoffs.field('by_participant').for_participant()} tokens. Acknowledge it.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction=f"You are player {i}; reason strategically and choose independently.") for i in range(1, 3))
    return GalleryCase("battle-of-sexes", "Battle of the Sexes", "asymmetric coordination matrix", builder.compile(), (), players + _game_agents("settler"), battle_of_sexes_case,
        ("Normal-form games repeat choice, settlement, and notification boilerplate.",),
        ("normal_form_game(actions=..., payoffs=...)",))


def chicken_case() -> GalleryCase:
    builder = Workflow("Chicken", metadata={"source": "Handbook chapters 2-3"})
    choice_q = QuestionMultipleChoice(question_name="action", question_text="Choose independently: Swerve or Straight. Mutual Straight is disastrous; Straight against Swerve pays best.", question_options=["Swerve", "Straight"])
    choices = builder.step("choose", Survey([choice_q]), assigned_to=role("player"), visible_to=role("settler"))
    payoffs = builder.derive("payoffs", by_participant=choices.submissions.payoff_matrix("action", {"WW": (2, 2), "WT": (1, 3), "TW": (3, 1), "TT": (0, 0)}, action_codes={"Swerve": "W", "Straight": "T"}))
    settle_q = QuestionFreeText(question_name="result", question_text=f"Record the authoritative participant payoffs {payoffs.field('by_participant').template}.")
    settled = builder.step("settle", Survey([settle_q]), assigned_to=role("settler"), after=choices)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your private payoff is {payoffs.field('by_participant').for_participant()} tokens. Acknowledge it.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Reason strategically and choose independently.") for i in range(1, 3))
    return GalleryCase("chicken", "Chicken", "anti-coordination matrix", builder.compile(), (), players + _game_agents("settler"), chicken_case,
        ("Normal-form games repeat choice, settlement, and notification boilerplate.",),
        ("normal_form_game(actions=..., payoffs=...)",))


def cases() -> list[GalleryCase]:
    return [
        brainstorm_case(),
        blind_review_case(),
        escalation_case(),
        editorial_case(),
        procurement_case(),
        moderation_case(),
        translation_case(),
        delphi_case(),
        peer_prediction_case(),
        public_goods_case(),
        mixed_research_case(),
        ultimatum_case(),
        trust_game_case(),
        prisoners_dilemma_case(),
        beauty_contest_case(),
        dictator_case(),
        first_price_auction_case(),
        jury_vote_case(),
        market_entry_case(),
        battle_of_sexes_case(),
        chicken_case(),
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
    instance_id = coordinator.launch(case.agents, instance_id=case.demo_instance_id)
    simulation = WorkflowSimulation(
        coordinator,
        {agent.name: agent for agent in case.agents},
        answerer,
        execution_plan=case.execution_plan,
        answerers={"human": answerer, "llm": answerer, "scripted": answerer},
    )
    simulation.run(
        instance_id,
        resume=True,
        retry_policy=RetryPolicy(max_attempts=3, lease_seconds=300),
    )
    dag = WorkflowDAGVisualization(coordinator, instance_id).save(root / "dag.html")
    return {
        "case": case,
        "store": store,
        "instance_id": instance_id,
        "simulation": simulation,
        "dag": dag,
    }


def describe_run(
    case: GalleryCase, store: SQLiteWorkflowStore, instance_id: str
) -> str:
    """Build an evidence-based prose summary from the persisted run."""
    items = store.items(instance_id)
    by_step = []
    for step in case.workflow.steps:
        step_items = [item for item in items if item["step_name"] == step.name]
        counts = Counter(item["status"] for item in step_items)
        statuses = ", ".join(
            f"{count} {status}" for status, count in sorted(counts.items())
        )
        by_step.append(f"{step.name}: {statuses}")
    completed = sum(item["status"] == "completed" for item in items)
    summary = (
        f"The saved run finished {completed} of {len(items)} work items. "
        + " Step outcomes were "
        + "; ".join(by_step)
        + "."
    )
    if case.slug == "public-goods":
        rounds = []
        for step in case.workflow.steps:
            values = [
                answer["contribution"]
                for item in items
                if item["step_name"] == step.name
                and (answer := store.item_answers(item["id"]))
            ]
            if values:
                rounds.append(f"{step.name} contributions were {values}")
        summary += " " + "; ".join(rounds) + "."
    elif case.slug == "peer-prediction":
        reports = [
            store.item_answers(item["id"])
            for item in items
            if item["step_name"] == "sealed-report"
        ]
        red = sum(report["reported_signal"] == "Red" for report in reports if report)
        forecasts = [report["predicted_red_percent"] for report in reports if report]
        summary += (
            f" {red} of {len(reports)} informants reported Red; forecasts of the Red "
            f"share were {forecasts}. The scorer completed, but its displayed working "
            "contains inconsistent peer-outcome arithmetic."
        )
    elif case.slug == "delphi":
        rounds = []
        for round_number in range(1, 4):
            estimates = [
                answer["estimate"]
                for item in items
                if item["step_name"] == f"round-{round_number}"
                and (answer := store.item_answers(item["id"]))
            ]
            if estimates:
                numeric = [float(value) for value in estimates]
                rounds.append(
                    f"round {round_number} estimates ranged from {min(numeric):g} "
                    f"to {max(numeric):g} ({max(numeric) - min(numeric):g} points)"
                )
        summary += " " + "; ".join(rounds) + "."
        round_3_statuses = {
            item["status"] for item in items if item["step_name"] == "round-3"
        }
        if round_3_statuses == {"skipped"}:
            summary += (
                " The deterministic convergence gate skipped round 3. The LLM's "
                "final report incorrectly says round 3 was required and its round-2 "
                "mean is also inaccurate, demonstrating why both values should be "
                "computed and injected."
            )
    elif case.slug == "mixed-research":
        coding = [
            store.item_answers(item["id"])
            for item in items
            if item["step_name"] == "independent-coding"
        ]
        themes = [answer["dominant_theme"] for answer in coding if answer]
        valences = [answer["overall_valence"] for answer in coding if answer]
        adjudication = next(
            (item for item in items if item["step_name"] == "human-adjudication"),
            None,
        )
        summary += (
            f" Coder themes were {themes} and valences were {valences}; the "
            f"conditional human-adjudication item was {adjudication['status']}. "
            "For this rehearsal, the execution plan deliberately mapped both human "
            "and LLM channels to LLM answerers; production can bind the human channel "
            "to Humanize without changing the workflow graph."
        )
    elif case.slug == "ultimatum":
        offer = store.step_answers(instance_id, "offer")[0]["offer"]
        accepted = store.step_answers(instance_id, "respond")[0]["accept"]
        summary += f" The proposer offered {offer} of 10 tokens and the responder answered {accepted}."
    elif case.slug == "trust-game":
        sent = store.step_answers(instance_id, "send")[0]["sent"]
        returned = store.step_answers(instance_id, "return")[0]["returned"]
        summary += f" The sender invested {sent}; the trustee returned {returned} from the tripled transfer."
    elif case.slug == "prisoners-dilemma":
        actions = [answer["action"] for answer in store.step_answers(instance_id, "choose")]
        summary += f" The sealed actions were {actions}."
    elif case.slug == "beauty-contest":
        numbers = [float(answer["number"]) for answer in store.step_answers(instance_id, "choose")]
        target = sum(numbers) / len(numbers) * 2 / 3
        summary += f" Choices were {numbers}; the engine-computable two-thirds-mean target was {target:g}."
    elif case.slug == "dictator":
        transfer = store.step_answers(instance_id, "allocate")[0]["transfer"]
        summary += f" The dictator transferred {transfer} of 10 tokens to the recipient."
    elif case.slug == "first-price-auction":
        bids = [float(answer["bid"]) for answer in store.step_answers(instance_id, "sealed-bid")]
        summary += f" Sealed bids were {bids}; the authoritative winning bid was {max(bids):g}."
    elif case.slug == "jury-vote":
        votes = [answer["verdict"] for answer in store.step_answers(instance_id, "secret-ballot")]
        summary += f" Ballots were {votes}; Guilty received {votes.count('Guilty')} of {len(votes)} votes."
    elif case.slug == "market-entry":
        decisions = [answer["decision"] for answer in store.step_answers(instance_id, "entry-decision")]
        summary += f" Decisions were {decisions}; {decisions.count('Enter')} of {len(decisions)} firms entered."
    elif case.slug in {"battle-of-sexes", "chicken"}:
        actions = [answer["action"] for answer in store.step_answers(instance_id, "choose")]
        summary += f" The two sealed actions were {actions}."
    return summary


def build_gallery(runs: list[dict], output: Path) -> Path:
    output = output.resolve()
    sections = []
    contents = "".join(
        f'<a href="#{escape(run["case"].slug, quote=True)}"><span>{index:02d}</span>{escape(run["case"].title)}</a>'
        for index, run in enumerate(runs, start=1)
    )
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
        source = highlight_python(inspect.getsource(case.builder))
        relative_dag = run["dag"].relative_to(output.parent)
        narrative = CASE_NARRATIVES[case.slug]
        happened = describe_run(case, store, instance_id)
        sections.append(
            f"""<section class="case" id="{escape(case.slug, quote=True)}"><div class="case-head"><div><span class="pattern">{escape(case.pattern)}</span><h2>{escape(case.title)}</h2></div><div class="case-actions"><a href="#top">Back to top</a></div></div><div class="writeup"><article><h3>What we built</h3><p>{escape(narrative.built)}</p></article><article><h3>What happened</h3><p>{escape(happened)}</p></article><article><h3>What we learned</h3><p>{escape(narrative.learned)}</p></article></div><iframe src="{escape(str(relative_dag), quote=True)}" loading="lazy"></iframe><div class="analysis"><div><h3>Observed responses</h3><table>{response_html}</table></div><div><h3>Language pressure and risks</h3><ul>{awkward}</ul><h3>Candidate concepts</h3><ul>{helpers}</ul></div></div><details class="code"><summary><span>Code</span><small>Python used to define this example</small></summary>{source}</details></section>"""
        )
    output.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>Workflow language stress gallery</title><style>html{{scroll-behavior:smooth;scroll-padding-top:16px}}body{{margin:0;background:#eef1f5;color:#172033;font:14px/1.5 system-ui,sans-serif}}header{{padding:38px;max-width:1400px;margin:auto}}header h1{{margin:0}}header p{{max-width:850px;color:#5d6878}}.toc{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:8px;margin-top:24px}}.toc a{{display:flex;gap:10px;align-items:center;padding:10px 12px;border:1px solid #d7dde6;border-radius:9px;background:white;color:#172033;text-decoration:none}}.toc a:hover{{border-color:#7c3aed;box-shadow:0 2px 8px #7c3aed20}}.toc span{{color:#7c3aed;font:700 11px ui-monospace,monospace}}.case{{scroll-margin-top:16px;margin:0 auto 34px;max-width:1400px;background:white;border:1px solid #d7dde6;border-radius:14px;overflow:hidden;box-shadow:0 5px 18px #18212f12}}.case-head{{display:flex;justify-content:space-between;align-items:center;padding:20px 24px}}.case-actions{{display:flex;gap:12px;align-items:center}}.case-actions a{{color:#6d28d9;font-size:12px;text-decoration:none}}h2{{margin:3px 0 0}}.pattern{{color:#6d28d9;font-size:11px;font-weight:800;text-transform:uppercase}}.writeup{{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:#dde2ea;border-top:1px solid #dde2ea}}.writeup article{{background:#f8fafc;padding:18px 22px}}.writeup h3{{margin:0 0 6px;color:#6d28d9;text-transform:uppercase;letter-spacing:.05em;font-size:10px}}.writeup p{{margin:0;color:#435067;font-size:13px}}iframe{{display:block;width:100%;height:760px;border:0;border-top:1px solid #dde2ea;border-bottom:1px solid #dde2ea}}.analysis{{display:grid;grid-template-columns:1fr 1fr;gap:28px;padding:22px}}h3{{font-size:13px}}.analysis table{{width:100%;border-collapse:collapse}}.analysis td{{border-top:1px solid #e5e7eb;padding:8px;vertical-align:top}}pre{{white-space:pre-wrap;margin:0;font:11px/1.4 ui-monospace,monospace}}code{{color:#6d28d9}}details.code{{border-top:1px solid #d7dde6;background:#0d1117}}details.code>summary{{display:flex;align-items:baseline;gap:12px;padding:15px 22px;cursor:pointer;list-style:none;background:#171d27;color:#f0f6fc}}details.code>summary::-webkit-details-marker{{display:none}}details.code>summary:after{{content:'＋';margin-left:auto;color:#8b949e}}details.code[open]>summary:after{{content:'−'}}details.code>summary span{{font-weight:750}}details.code>summary small{{color:#8b949e}}.highlight{{max-height:620px;overflow:auto;padding:16px 0;background:#0d1117}}.highlight pre{{white-space:pre;margin:0;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace}}.highlight .linenos{{padding-right:12px;color:#6e7681;user-select:none}}{CODE_FORMATTER.get_style_defs(".highlight")}@media(max-width:800px){{.analysis,.writeup{{grid-template-columns:1fr}}}}</style></head><body><header id="top"><h1>Workflow language stress gallery</h1><p>{len(runs)} workflows executed with simulated respondents. Each case now explains the mechanism, reports what occurred in the persisted run, and turns the observed friction into concrete language-design lessons.</p><nav class="toc" aria-label="Workflow table of contents">{contents}</nav></header>{"".join(sections)}</body></html>""",
        encoding="utf-8",
    )
    return output.resolve()


def run_gallery(
    output_dir: Path,
    model_name: str = "gpt-4o-mini",
    *,
    service_name: str = "openai",
    disable_remote_inference: bool = False,
) -> Path:
    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%d-%H%M%S")
    root = output_dir / "workflow_gallery_artifacts" / run_id
    root.mkdir(parents=True, exist_ok=False)
    answerer = EDSLAgentAnswerer(
        Model(model_name, service_name=service_name),
        run_options={"disable_remote_inference": disable_remote_inference},
    )
    runs = []
    for case in cases():
        print(f"Running {case.slug}...", flush=True)
        runs.append(run_case(case, root / case.slug, answerer))
    return build_gallery(runs, output_dir / "workflow_stress_gallery.html")


if __name__ == "__main__":
    print(run_gallery(Path(__file__).parent))
