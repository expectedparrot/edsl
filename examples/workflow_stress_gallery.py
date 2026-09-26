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
    QuestionRank,
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
    seeded_uniform,
    seeded_integer,
    join_by_participant,
    lookup,
    choose,
    if_,
    join_any,
    not_,
    quorum,
    role,
    human,
    llm,
    match,
    ChoiceTable,
    StrategyTable,
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
    "minimum-effort": CaseNarrative(
        "Six players privately choose effort from one through seven. The workflow computes the group minimum, which raises everyone's return, while effort above that minimum is individually costly.",
        "The group minimum and every individual payoff are now authoritative: a symbolic per-submission binding maps the same serialized expression over all identities. Delivery and ledger posting, rather than arithmetic, are the remaining gaps.",
    ),
    "threshold-public-good": CaseNarrative(
        "Six players contribute from ten-token endowments toward a thirty-token provision point. The workflow computes total contributions, contributor count, provision status, and the resulting public return.",
        "Serializable reductions determine provision, and the generic submission map computes every private balance without Python callbacks. Optional rebate treatments and passive payment delivery remain useful additions.",
    ),
    "second-price-auction": CaseNarrative(
        "Five private-value bidders submit sealed bids. The workflow identifies the highest bidder but charges the second-highest bid, implementing the defining Vickrey payment rule.",
        "The new order-statistic operator makes the payment authoritative and generalizes to third-price auctions. Seeded tie-breaking and participant-specific utility remain unresolved.",
    ),
    "best-shot": CaseNarrative(
        "Six players privately choose costly contributions, but the public benefit is determined only by the largest contribution—the group's best shot—rather than by their sum.",
        "Maximum, sum, contributor count, and identity-keyed net payoffs are all authoritative. The same generic map expression used here also settles minimum-effort and threshold public-good games.",
    ),
    "impunity": CaseNarrative(
        "An allocator proposes a split and keeps their allocation regardless of the recipient's response. The recipient may reject, but rejection destroys only the recipient's proposed share.",
        "Piecewise expressions represent the asymmetric rejection rule cleanly and distinguish impunity from ultimatum without a new operator. Repeated settlement and notice boilerplate suggests a reusable allocation-game helper.",
    ),
    "third-price-auction": CaseNarrative(
        "Five private-value bidders submit sealed bids; the highest bidder wins but pays the third-highest bid, a mechanism used to test bidding behavior beyond standard first- and second-price formats.",
        "The generic one-based order-statistic operator handles third-price settlement without special auction code. Ties and winner-specific utility remain common unresolved concerns across auction formats.",
    ),
    "schelling-claims": CaseNarrative(
        "Two players independently claim part of a one-hundred-token prize without communicating. Both claims are honored when their sum is feasible; otherwise both players receive zero.",
        "A sum, feasibility comparison, conditional, and identity-preserving map express the complete settlement without a game-specific operator. The result is a compact demonstration of compositional payoff logic.",
    ),
    "commons-dilemma": CaseNarrative(
        "Eight participants independently conserve or exploit a shared resource. At most two exploiters preserve the resource; exploitation has a private premium, while overuse sharply lowers everyone's return.",
        "Counts, nested conditionals, and a symbolic own-action binding produce all participant payoffs. The remaining limitation is that the fixed survival threshold is metadata rather than a reusable capacity abstraction.",
    ),
    "median-effort": CaseNarrative(
        "Seven players choose actions from one through seven and are rewarded for proximity to the group median, creating an order-statistic coordination target rather than a minimum-effort target.",
        "Median plus symbolic absolute distance produces authoritative identity-keyed payoffs. This validates that the generic map supports nonlinear unary operations rather than only linear payoff formulas.",
    ),
    "allais": CaseNarrative(
        "A decision maker completes the two canonical common-consequence lottery choices. A separate analyst receives an authoritative classification of the resulting choice pattern.",
        "Linked choices and deterministic classification fit the workflow model, but typed lottery objects and incentive-compatible random implementation are absent, leaving probability descriptions embedded in prose.",
    ),
    "ellsberg": CaseNarrative(
        "A decision maker chooses between known and ambiguous urn bets in two linked decisions. The workflow classifies whether the pair displays the standard ambiguity-averse Ellsberg pattern.",
        "The classification is serializable, but urn composition and ambiguous events are plain text. A typed lottery/urn resource would support validation, display, and eventual random resolution.",
    ),
    "preference-reversal": CaseNarrative(
        "A participant first chooses between a high-probability modest-prize lottery and a low-probability large-prize lottery, then independently states selling prices for both.",
        "The workflow can flag whether choice and valuation rankings conflict. It cannot yet randomize which elicitation becomes payoff-relevant or apply a reusable incentive-compatible valuation mechanism.",
    ),
    "bdm-valuation": CaseNarrative(
        "A participant states a minimum selling price. The workflow draws a stable random offer and authoritatively determines whether the item is sold and at what price.",
        "A generic seeded draw plus ordinary comparisons and conditionals implement BDM without a named executor. The awkward part is presentation: typed monetary units and a reusable mechanism component would prevent scale and inequality mistakes.",
    ),
    "binary-lottery": CaseNarrative(
        "A participant chooses a safe payment or a risky binary lottery; one stable draw resolves the selected option and the workflow records the authoritative payoff.",
        "The same random primitive used for BDM resolves a lottery cleanly. Probabilities and prizes are still duplicated between prose and expressions, strongly supporting a typed Lottery value object.",
    ),
    "probability-calibration": CaseNarrative(
        "A forecaster reports a probability for a binary event. A stable draw realizes the event and a deterministic quadratic score rewards calibrated probability reports.",
        "Arithmetic composition is enough for a Brier-style score, but the verbose formula is easy to mis-scale. Named, serializable scoring-rule constructors should compile to these primitive expressions.",
    ),
    "bayesian-updating": CaseNarrative(
        "A participant states a prior, receives a randomly generated diagnostic signal, and then reports a posterior probability before an analyst sees the benchmark.",
        "Staged revelation works with a derived random signal. Conditional Bayes arithmetic is cumbersome and experiment parameters are repeated, suggesting declared parameters and a small library of audited formula constructors.",
    ),
    "intertemporal-choice": CaseNarrative(
        "A participant makes an immediate-versus-delayed monetary choice and then a second delayed-versus-more-delayed choice; the workflow classifies the pattern.",
        "Sequential elicitation and classification need no special engine feature. Dates, delays, and amounts remain prose, so a typed dated-payment option would make equivalence and schedule validation possible.",
    ),
    "holt-laury": CaseNarrative(
        "A participant answers every row of a ten-row Holt–Laury lottery list, the contract validates a monotone A-to-B pattern, and one row is selected reproducibly for payment.",
        "The structured choice table preserves every decision and rejects multiple switching at submission time. Lottery outcomes inside each row still need typed representations and resolution.",
    ),
    "time-price-list": CaseNarrative(
        "A participant answers every row of an immediate-versus-delayed payment list, while a stable integer draw chooses the payoff-relevant row.",
        "The same serialized choice-table contract serves risk and time tasks, confirming it is a general primitive. Actual delayed fulfillment remains outside the coordinator.",
    ),
    "dictator-strategy-method": CaseNarrative(
        "A dictator states transfers for three possible recipient endowments before a stable draw reveals which contingency determines the implemented allocation.",
        "Contingent plans can be represented as several named answers, but selecting the realized answer requires a verbose conditional tree. Structured strategy tables and keyed lookup expressions would help.",
    ),
    "public-goods-punishment": CaseNarrative(
        "Four players contribute simultaneously, observe the group result, then independently buy punishment points before the workflow settles contribution and punishment costs.",
        "Two-stage group interaction composes from ordinary fan-out and aggregation. Target-specific sanctions require matrices or keyed allocations, which the current scalar punishment question deliberately exposes as missing.",
    ),
    "volunteers-dilemma": CaseNarrative(
        "Six players independently choose whether to incur the cost of volunteering; everyone benefits if at least one volunteer exists, while volunteers bear an individual cost.",
        "Count, conditional provision, and identity-preserving payoff mapping express the mechanism completely. This is strong evidence that threshold games need no game-specific runtime support.",
    ),
    "cournot": CaseNarrative(
        "Five firms simultaneously choose quantities; the workflow computes inverse-demand price and every firm's profit from its own quantity and the market total.",
        "Parameters, sum, and identity-preserving mapping provide complete authoritative settlement. Repeated Cournot now mainly needs convenient history views rather than a market-specific executor.",
    ),
    "monopoly": CaseNarrative(
        "A monopolist selects one of several posted prices and a serialized demand schedule determines quantity, revenue, cost, and profit.",
        "The general lookup operator cleanly represents a discrete demand curve. Continuous curves would benefit from reusable piecewise or interpolation expressions.",
    ),
    "schelling-ranking": CaseNarrative(
        "Three participants independently rank A, B, and C; the workflow tests whether their complete rankings coincide before announcing coordination.",
        "A generic all-equal reduction works for structured list values. Converting the agreed ranking into identity-specific rank prizes still needs list-position or inverse-ranking helpers.",
    ),
    "curse-of-knowledge": CaseNarrative(
        "An uninformed judge answers a factual question, while an informed predictor is shown the truth and predicts the uninformed answer before comparison.",
        "Asymmetric information and counterfactual prediction fit ordinary visibility rules. Cohort-level versions need deterministic matching between informed predictors and uninformed observations.",
    ),
    "sequential-search": CaseNarrative(
        "A searcher receives reproducible offers sequentially, may accept either of the first two, and otherwise receives the final offer after paying accumulated search costs.",
        "Conditional branching works, but settlement exposed that conditionals must evaluate lazily when an unchosen branch references a skipped step. The evaluator now has that general short-circuit behavior.",
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


def minimum_effort_case() -> GalleryCase:
    builder = Workflow("Minimum-effort coordination", metadata={"effort_range": [1, 7], "payoff": "2 * group_minimum - own_effort", "source_pages": "209-218"})
    effort_q = QuestionNumerical(question_name="effort", question_text="Privately choose an integer effort from 1 to 7. Group productivity depends on the minimum effort, but effort above the minimum is costly to you.", min_value=1, max_value=7, include_comment=False)
    efforts = builder.step("choose-effort", Survey([effort_q]), assigned_to=role("player"), visible_to=role("analyst"))
    outcome = builder.derive("outcome", minimum=efforts.outputs("effort").minimum(), mean=efforts.outputs("effort").mean())
    own = efforts.submissions.each("effort")
    payoffs = builder.derive("payoffs", by_participant=own.map(2 * outcome.field("minimum").expression - own.value))
    report_q = QuestionFreeText(question_name="result", question_text=f"Report the authoritative group minimum {outcome.field('minimum').template} and mean {outcome.field('mean').template}. Explain that individual payoff also depends on excess effort, without recomputing these statistics.")
    settled = builder.step("settle", Survey([report_q]), assigned_to=role("analyst"), after=efforts)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative payoff is {payoffs.field('by_participant').for_participant()} tokens. Acknowledge it.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Balance payoff-dominant coordination against the risk that another player chooses low effort.") for i in range(1, 7))
    return GalleryCase("minimum-effort", "Minimum-effort coordination", "parallel effort -> group minimum", builder.compile(), (), players + _game_agents("analyst"), minimum_effort_case,
        ("Payoff notices remain survey-shaped acknowledgements rather than passive notifications or ledger credits.",),
        ("notify_each(payoffs)", "credit_each(payoffs)"))


def threshold_public_good_case() -> GalleryCase:
    builder = Workflow("Threshold public good", metadata={"endowment": 10, "provision_point": 30, "public_return": 60})
    contribution_q = QuestionNumerical(question_name="contribution", question_text="You have 10 tokens. Contribute an integer from 0 to 10. If the group contributes at least 30 total, a 60-token public return is created.", min_value=0, max_value=10, include_comment=False)
    contributions = builder.step("contribute", Survey([contribution_q]), assigned_to=role("player"), visible_to=role("analyst"))
    total = contributions.outputs("contribution").sum()
    provided = total.compare_at_least(30)
    outcome = builder.derive("outcome", total=total, contributors=6 - contributions.outputs("contribution").count_value(0), provided=provided, public_return=choose(provided, 60, 0))
    own = contributions.submissions.each("contribution")
    payoffs = builder.derive("payoffs", by_participant=own.map(10 - own.value + outcome.field("public_return").expression / 6))
    report_q = QuestionFreeText(question_name="result", question_text=f"Report authoritative total contributions={outcome.field('total').template}, contributors={outcome.field('contributors').template}, provision={outcome.field('provided').template}, and public return={outcome.field('public_return').template}.")
    settled = builder.step("settle", Survey([report_q]), assigned_to=role("analyst"), after=contributions)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative balance is {payoffs.field('by_participant').for_participant()} tokens. Acknowledge it.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Choose strategically, balancing private tokens against the risk that the provision point is missed.") for i in range(1, 7))
    return GalleryCase("threshold-public-good", "Threshold public good", "contributions -> provision point -> return", builder.compile(), (), players + _game_agents("analyst"), threshold_public_good_case,
        ("Contributor count is written as roster size minus zero contributions.", "The example has no rebate-on-failure treatment."),
        ("outputs.count_where(predicate)", "rebate_if_unprovided(...)", "credit_each(payoffs)"))


def second_price_auction_case() -> GalleryCase:
    builder = Workflow("Second-price sealed-bid auction", metadata={"source_pages": "503-512"})
    bid_q = QuestionNumerical(question_name="bid", question_text="Privately bid an integer from 0 to 100. The highest bidder wins and pays the second-highest bid.", min_value=0, max_value=100, include_comment=False)
    bids = builder.step("sealed-bid", Survey([bid_q]), assigned_to=role("bidder"), visible_to=role("auctioneer"))
    auction = builder.derive("auction", highest_bid=bids.outputs("bid").maximum(), price=bids.outputs("bid").nth_largest(2))
    winners = builder.derive("ranking", winners=bids.submissions.closest_to("bid", auction.field("highest_bid").expression, ties="all"))
    result_q = QuestionFreeText(question_name="result", question_text=f"Announce authoritative winner list={winners.field('winners').template}, highest bid={auction.field('highest_bid').template}, and second-price payment={auction.field('price').template}. Do not alter ties.")
    builder.step("settle", Survey([result_q]), assigned_to=role("auctioneer"), after=bids)
    bidders = tuple(Agent(name=f"bidder-{i}@simulated.email", traits={"role": "bidder", "private_value": 15 + 14 * i}, instruction="This is a Vickrey auction. Bid according to your private value in your traits.") for i in range(1, 6))
    return GalleryCase("second-price-auction", "Second-price sealed-bid auction", "sealed bids -> top two -> Vickrey payment", builder.compile(), (), bidders + _game_agents("auctioneer"), second_price_auction_case,
        ("A tie at the highest bid produces multiple winners for one indivisible item.", "Winner utility is not yet projected as value minus price."),
        ("tie_break(strategy='seeded-random')", "private_value.for_participant()", "credit(winner, value-price)"))


def best_shot_case() -> GalleryCase:
    builder = Workflow("Best-shot public good", metadata={"endowment": 10, "benefit_multiplier": 2})
    contribution_q = QuestionNumerical(question_name="contribution", question_text="Choose a costly contribution from 0 to 10. Everyone receives twice the largest contribution in the group; you additionally pay your own contribution.", min_value=0, max_value=10, include_comment=False)
    contributions = builder.step("contribute", Survey([contribution_q]), assigned_to=role("player"), visible_to=role("analyst"))
    outcome = builder.derive("outcome", best_shot=contributions.outputs("contribution").maximum(), total_cost=contributions.outputs("contribution").sum(), contributors=6 - contributions.outputs("contribution").count_value(0))
    own = contributions.submissions.each("contribution")
    payoffs = builder.derive("payoffs", by_participant=own.map(2 * outcome.field("best_shot").expression - own.value))
    result_q = QuestionFreeText(question_name="result", question_text=f"Report authoritative best shot={outcome.field('best_shot').template}, total contribution cost={outcome.field('total_cost').template}, and contributor count={outcome.field('contributors').template}. The common gross benefit is twice the best shot.")
    settled = builder.step("settle", Survey([result_q]), assigned_to=role("analyst"), after=contributions)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative payoff is {payoffs.field('by_participant').for_participant()} tokens. Acknowledge it.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Choose strategically in a best-shot public-good game, anticipating that only the maximum contribution affects the shared benefit.") for i in range(1, 7))
    return GalleryCase("best-shot", "Best-shot public good", "parallel contributions -> maximum benefit", builder.compile(), (), players + _game_agents("analyst"), best_shot_case,
        ("Payoff notices remain survey-shaped acknowledgements rather than passive notifications or ledger credits.",),
        ("notify_each(payoffs)", "credit_each(payoffs)"))


def impunity_case() -> GalleryCase:
    builder = Workflow("Impunity game", metadata={"endowment": 10})
    offer_q = QuestionNumerical(question_name="offer", question_text="Allocate 0 to 10 tokens to the recipient. You keep the remainder regardless of whether the recipient accepts.", min_value=0, max_value=10, include_comment=False)
    offer = builder.step("allocate", Survey([offer_q]), assigned_to=role("allocator"))
    response_q = QuestionYesNo(question_name="accept", question_text=f"The allocator offered you {offer.answer('offer').template} tokens. Accept? Rejecting gives you zero but does not change the allocator's payoff.")
    response = builder.step("respond", Survey([response_q]), assigned_to=role("recipient"), after=offer)
    accepted = response.answer("accept").value.compare_equals("Yes")
    payoffs = builder.derive("payoffs", allocator=10 - offer.answer("offer").value, recipient=choose(accepted, offer.answer("offer").value, 0))
    allocator_notice = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative payoff is {payoffs.field('allocator').template}. Acknowledge it.")
    recipient_notice = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative payoff is {payoffs.field('recipient').template}. Acknowledge it.")
    builder.step("allocator-notice", Survey([allocator_notice]), assigned_to=role("allocator"), after=response)
    builder.step("recipient-notice", Survey([recipient_notice]), assigned_to=role("recipient"), after=response)
    return GalleryCase("impunity", "Impunity game", "allocation -> costless-to-allocator rejection", builder.compile(), (), _game_agents("allocator", "recipient"), impunity_case,
        ("Allocation games repeat nearly identical private-notice steps.",),
        ("allocation_game(rejection_effect=...)", "notify_each(payoffs)"))


def third_price_auction_case() -> GalleryCase:
    builder = Workflow("Third-price sealed-bid auction", metadata={"source_pages": "504, 515-517"})
    bid_q = QuestionNumerical(question_name="bid", question_text="Privately bid an integer from 0 to 100. The highest bidder wins and pays the third-highest bid.", min_value=0, max_value=100, include_comment=False)
    bids = builder.step("sealed-bid", Survey([bid_q]), assigned_to=role("bidder"), visible_to=role("auctioneer"))
    auction = builder.derive("auction", highest_bid=bids.outputs("bid").maximum(), price=bids.outputs("bid").nth_largest(3))
    winners = builder.derive("ranking", winners=bids.submissions.closest_to("bid", auction.field("highest_bid").expression, ties="all"))
    result_q = QuestionFreeText(question_name="result", question_text=f"Announce authoritative winner list={winners.field('winners').template}, highest bid={auction.field('highest_bid').template}, and third-price payment={auction.field('price').template}.")
    builder.step("settle", Survey([result_q]), assigned_to=role("auctioneer"), after=bids)
    bidders = tuple(Agent(name=f"bidder-{i}@simulated.email", traits={"role": "bidder", "private_value": 18 + 13 * i}, instruction="Bid strategically in a third-price auction using the private value in your traits.") for i in range(1, 6))
    return GalleryCase("third-price-auction", "Third-price sealed-bid auction", "sealed bids -> third order statistic", builder.compile(), (), bidders + _game_agents("auctioneer"), third_price_auction_case,
        ("Highest-bid ties remain unresolved for an indivisible item.", "Bidder utility cannot yet combine a private trait with a derived payment."),
        ("tie_break(strategy='seeded-random')", "trait('private_value')", "credit(winner, value-price)"))


def schelling_claims_case() -> GalleryCase:
    builder = Workflow("Schelling tacit claims", metadata={"prize": 100, "source_page": 12})
    claim_q = QuestionNumerical(question_name="claim", question_text="Without communicating, claim an integer amount from a 100-token prize. If the two claims total at most 100, each receives their claim; otherwise both receive zero.", min_value=0, max_value=100, include_comment=False)
    claims = builder.step("claim", Survey([claim_q]), assigned_to=role("player"), visible_to=role("settler"))
    total = claims.outputs("claim").sum()
    feasible = total.compare_at_most(100)
    own = claims.submissions.each("claim")
    outcome = builder.derive("outcome", total=total, feasible=feasible, payoffs=own.map(choose(feasible, own.value, 0)))
    settle_q = QuestionFreeText(question_name="result", question_text=f"Record authoritative total claims={outcome.field('total').template} and feasibility={outcome.field('feasible').template}.")
    settled = builder.step("settle", Survey([settle_q]), assigned_to=role("settler"), after=claims)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative payoff is {outcome.field('payoffs').for_participant()} tokens. Acknowledge it.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Choose a tacit claim strategically without communication.") for i in range(1, 3))
    return GalleryCase("schelling-claims", "Schelling tacit claims", "sealed claims -> feasibility -> mapped payoff", builder.compile(), (), players + _game_agents("settler"), schelling_claims_case,
        ("The fixed prize appears in the question, metadata, and expression.",),
        ("workflow.parameter('prize')", "credit_each(payoffs)"))


def commons_dilemma_case() -> GalleryCase:
    builder = Workflow("Commons dilemma", metadata={"capacity": 2})
    action_q = QuestionMultipleChoice(question_name="action", question_text="Choose privately whether to Conserve or Exploit. The commons survives if at most two of eight participants exploit it. Exploitation pays a private premium but risks collapse.", question_options=["Conserve", "Exploit"])
    actions = builder.step("choose", Survey([action_q]), assigned_to=role("player"), visible_to=role("analyst"))
    exploiters = actions.outputs("action").count_value("Exploit")
    survives = exploiters.compare_at_most(2)
    own = actions.submissions.each("action")
    exploits = own.value.compare_equals("Exploit")
    outcome = builder.derive("outcome", exploiters=exploiters, survives=survives, payoffs=own.map(choose(survives, choose(exploits, 9, 6), choose(exploits, 3, 2))))
    settle_q = QuestionFreeText(question_name="result", question_text=f"Record authoritative exploiter count={outcome.field('exploiters').template}, survival={outcome.field('survives').template}, and participant payoffs={outcome.field('payoffs').template}.")
    settled = builder.step("settle", Survey([settle_q]), assigned_to=role("analyst"), after=actions)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative payoff is {outcome.field('payoffs').for_participant()} tokens. Acknowledge it.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Balance the private exploitation premium against the shared risk of commons collapse.") for i in range(1, 9))
    return GalleryCase("commons-dilemma", "Commons dilemma", "parallel use decisions -> capacity -> mapped payoff", builder.compile(), (), players + _game_agents("analyst"), commons_dilemma_case,
        ("Capacity is duplicated in prose and the expression.", "This one-shot version does not model resource stock across rounds."),
        ("workflow.parameter('capacity')", "durable resource stock"))


def median_effort_case() -> GalleryCase:
    builder = Workflow("Median-action coordination", metadata={"action_range": [1, 7], "base_payoff": 10})
    action_q = QuestionNumerical(question_name="action", question_text="Choose an integer from 1 through 7. Your payoff is 10 minus your absolute distance from the group median.", min_value=1, max_value=7, include_comment=False)
    actions = builder.step("choose", Survey([action_q]), assigned_to=role("player"), visible_to=role("analyst"))
    median = actions.outputs("action").median()
    own = actions.submissions.each("action")
    outcome = builder.derive("outcome", median=median, payoffs=own.map(10 - (own.value - median).absolute()))
    settle_q = QuestionFreeText(question_name="result", question_text=f"Record authoritative median={outcome.field('median').template} and identity-keyed payoffs={outcome.field('payoffs').template}.")
    settled = builder.step("settle", Survey([settle_q]), assigned_to=role("analyst"), after=actions)
    notice_q = QuestionFreeText(question_name="payoff", question_text=f"Your authoritative payoff is {outcome.field('payoffs').for_participant()} tokens. Acknowledge it.")
    builder.step("payoff-notice", Survey([notice_q]), assigned_to=role("player"), after=settled)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Choose strategically to coordinate near the group median.") for i in range(1, 8))
    return GalleryCase("median-effort", "Median-action coordination", "parallel actions -> median -> distance payoff", builder.compile(), (), players + _game_agents("analyst"), median_effort_case,
        ("Base payoff and action bounds are repeated as literals.",),
        ("workflow.parameter('base_payoff')", "credit_each(payoffs)"))


def allais_case() -> GalleryCase:
    builder = Workflow("Allais common-consequence choices", metadata={"source_pages": "619-643"})
    first_q = QuestionMultipleChoice(question_name="first_choice", question_text="Choose one lottery. A: receive $1 million for certain. B: 10% chance of $5 million, 89% chance of $1 million, and 1% chance of $0.", question_options=["A: certain $1m", "B: three-outcome lottery"])
    first = builder.step("first-choice", Survey([first_q]), assigned_to=role("decision-maker"))
    second_q = QuestionMultipleChoice(question_name="second_choice", question_text="Now choose one lottery. C: 11% chance of $1 million and 89% chance of $0. D: 10% chance of $5 million and 90% chance of $0.", question_options=["C: 11% of $1m", "D: 10% of $5m"])
    second = builder.step("second-choice", Survey([second_q]), assigned_to=role("decision-maker"), after=first)
    chose_a = first.answer("first_choice").value.compare_equals("A: certain $1m")
    chose_d = second.answer("second_choice").value.compare_equals("D: 10% of $5m")
    classification = builder.derive("classification", pattern=choose(chose_a, choose(chose_d, "common-consequence reversal pattern", "certainty-oriented consistent pattern"), choose(chose_d, "risk-oriented consistent pattern", "opposite reversal pattern")))
    report_q = QuestionFreeText(question_name="result", question_text=f"Record the authoritative choice-pattern classification: {classification.field('pattern').template}.")
    builder.step("classify", Survey([report_q]), assigned_to=role("analyst"), after=second)
    return GalleryCase("allais", "Allais common-consequence choices", "linked lottery choices -> deterministic pattern", builder.compile(), (), _game_agents("decision-maker", "analyst"), allais_case,
        ("Lottery probabilities and prizes are embedded in prose.", "A nested choose expression is needed to classify a two-answer pattern."),
        ("Lottery(outcomes=...)", "choice_pattern({...})", "randomly_pay_one(choice_steps)"))


def ellsberg_case() -> GalleryCase:
    builder = Workflow("Ellsberg ambiguity choices", metadata={"urn": "30 red; 60 split unknown between black and yellow", "source_pages": "644-649"})
    first_q = QuestionMultipleChoice(question_name="first_bet", question_text="An urn has 30 red balls and 60 balls split in an unknown proportion between black and yellow. Choose a bet paying $100 on Red or a bet paying $100 on Black.", question_options=["Red", "Black"])
    first = builder.step("single-color-bet", Survey([first_q]), assigned_to=role("decision-maker"))
    second_q = QuestionMultipleChoice(question_name="second_bet", question_text="Using the same urn, choose a bet paying $100 on Red or Yellow, or a bet paying $100 on Black or Yellow.", question_options=["Red or Yellow", "Black or Yellow"])
    second = builder.step("two-color-bet", Survey([second_q]), assigned_to=role("decision-maker"), after=first)
    chose_red = first.answer("first_bet").value.compare_equals("Red")
    chose_black_yellow = second.answer("second_bet").value.compare_equals("Black or Yellow")
    classification = builder.derive("classification", pattern=choose(chose_red, choose(chose_black_yellow, "standard ambiguity-averse Ellsberg pattern", "known-red preference only"), choose(chose_black_yellow, "ambiguous-black preference only", "reverse Ellsberg pattern")))
    report_q = QuestionFreeText(question_name="result", question_text=f"Record the authoritative choice-pattern classification: {classification.field('pattern').template}.")
    builder.step("classify", Survey([report_q]), assigned_to=role("analyst"), after=second)
    return GalleryCase("ellsberg", "Ellsberg ambiguity choices", "known versus ambiguous bets -> pattern", builder.compile(), (), _game_agents("decision-maker", "analyst"), ellsberg_case,
        ("The urn and winning events are unvalidated prose.", "Pattern classification repeats nested conditionals."),
        ("Urn(known=..., ambiguous=...)", "Bet(event=..., prize=...)", "choice_pattern({...})"))


def preference_reversal_case() -> GalleryCase:
    builder = Workflow("Preference-reversal task", metadata={"source_pages": "657-665"})
    choice_q = QuestionMultipleChoice(question_name="preferred", question_text="Choose one lottery. P-bet: 90% chance of $10. Dollar-bet: 10% chance of $80.", question_options=["P-bet", "Dollar-bet"])
    choice = builder.step("choose-lottery", Survey([choice_q]), assigned_to=role("decision-maker"))
    prices = Survey([
        QuestionNumerical(question_name="p_price", question_text="State your minimum selling price from $0 to $10 for the P-bet.", min_value=0, max_value=10, include_comment=False),
        QuestionNumerical(question_name="dollar_price", question_text="State your minimum selling price from $0 to $80 for the Dollar-bet.", min_value=0, max_value=80, include_comment=False),
    ])
    valuation = builder.step("value-lotteries", prices, assigned_to=role("decision-maker"), after=choice)
    chose_p = choice.answer("preferred").value.compare_equals("P-bet")
    dollar_at_least_p = valuation.answer("dollar_price").value.compare_at_least(valuation.answer("p_price").value)
    classification = builder.derive("classification", pattern=choose(chose_p, choose(dollar_at_least_p, "choice-price preference reversal", "choice and price rankings agree"), choose(dollar_at_least_p, "choice and price rankings agree", "reverse choice-price reversal")))
    report_q = QuestionFreeText(question_name="result", question_text=f"Record the authoritative classification: {classification.field('pattern').template}.")
    builder.step("classify", Survey([report_q]), assigned_to=role("analyst"), after=valuation)
    return GalleryCase("preference-reversal", "Preference-reversal task", "choice -> valuations -> consistency test", builder.compile(), (), _game_agents("decision-maker", "analyst"), preference_reversal_case,
        ("Selling prices are elicited directly rather than through BDM.", "Ties are treated as Dollar-bet valued at least as highly."),
        ("BDM(valuation, random_price)", "strictly_greater_than", "randomly_pay_one(step)"))


def bdm_valuation_case() -> GalleryCase:
    builder = Workflow("BDM valuation", metadata={"mechanism": "Becker-DeGroot-Marschak"})
    value_q = QuestionNumerical(question_name="reservation_price", question_text="You own a voucher. State the minimum price from $0 to $20 at which you would sell it.", min_value=0, max_value=20, include_comment=False)
    value = builder.step("state-value", Survey([value_q]), assigned_to=role("decision-maker"))
    offer = seeded_uniform(0, 20, key="bdm-offer")
    sold = offer.compare_at_least(value.answer("reservation_price").value)
    outcome = builder.derive("outcome", random_offer=offer, sold=sold, cash_payment=choose(sold, offer, 0))
    report_q = QuestionFreeText(question_name="result", question_text=f"Record the authoritative random offer {outcome.field('random_offer').template}, sale decision {outcome.field('sold').template}, and cash payment {outcome.field('cash_payment').template}.")
    builder.step("settle", Survey([report_q]), assigned_to=role("analyst"), after=value)
    return GalleryCase("bdm-valuation", "BDM valuation", "stated value -> random offer -> incentive-compatible settlement", builder.compile(), (), _game_agents("decision-maker", "analyst"), bdm_valuation_case,
        ("Currency and range appear in both question text and expression bounds.", "The economically important weak inequality is handwritten."),
        ("Money(amount, currency)", "bdm(reservation_price, offer)", "workflow.parameter('offer_range')"))


def binary_lottery_case() -> GalleryCase:
    builder = Workflow("Binary lottery choice")
    q = QuestionMultipleChoice(question_name="choice", question_text="Choose: Safe pays $4 for certain; Risky pays $10 with probability 0.5 and $0 otherwise.", question_options=["Safe", "Risky"])
    choice_step = builder.step("choose", Survey([q]), assigned_to=role("decision-maker"))
    draw = seeded_uniform(key="lottery-resolution")
    chose_risky = choice_step.answer("choice").value.compare_equals("Risky")
    risky_payoff = choose(draw.compare_at_most(0.5), 10, 0)
    outcome = builder.derive("outcome", draw=draw, payoff=choose(chose_risky, risky_payoff, 4))
    report_q = QuestionFreeText(question_name="result", question_text=f"Record draw={outcome.field('draw').template} and authoritative payoff={outcome.field('payoff').template}.")
    builder.step("resolve", Survey([report_q]), assigned_to=role("analyst"), after=choice_step)
    return GalleryCase("binary-lottery", "Binary lottery choice", "choice -> seeded draw -> monetary resolution", builder.compile(), (), _game_agents("decision-maker", "analyst"), binary_lottery_case,
        ("The lottery is duplicated in prose and payoff logic.",),
        ("Lottery.binary(probability, high, low)", "resolve(choice, draw)", "Money"))


def probability_calibration_case() -> GalleryCase:
    builder = Workflow("Probability calibration")
    q = QuestionNumerical(question_name="forecast", question_text="An event has a stated base rate of 60%. Report your probability from 0 to 100 that it occurs.", min_value=0, max_value=100, include_comment=False)
    forecast = builder.step("forecast", Survey([q]), assigned_to=role("forecaster"))
    draw = seeded_uniform(key="event")
    occurred = draw.compare_at_most(0.6)
    realized_percent = choose(occurred, 100, 0)
    error = forecast.answer("forecast").value - realized_percent
    outcome = builder.derive("score", draw=draw, occurred=occurred, quadratic_score=100 - error * error / 100)
    report_q = QuestionFreeText(question_name="result", question_text=f"Record occurred={outcome.field('occurred').template} and authoritative quadratic score={outcome.field('quadratic_score').template}.")
    builder.step("score", Survey([report_q]), assigned_to=role("analyst"), after=forecast)
    return GalleryCase("probability-calibration", "Probability calibration", "forecast -> realized event -> proper score", builder.compile(), (), _game_agents("forecaster", "analyst"), probability_calibration_case,
        ("The 0-100 scaling convention is implicit.", "The scoring formula is easy to transcribe incorrectly."),
        ("Probability(scale='percent')", "brier_score(report, outcome)", "Bernoulli(probability)"))


def bayesian_updating_case() -> GalleryCase:
    builder = Workflow("Bayesian updating")
    prior_q = QuestionNumerical(question_name="prior", question_text="Before a diagnostic signal, report P(disease) from 0 to 100. The stated base rate is 20%.", min_value=0, max_value=100, include_comment=False)
    prior = builder.step("prior", Survey([prior_q]), assigned_to=role("decision-maker"))
    draw = seeded_uniform(key="diagnostic-signal")
    positive = draw.compare_at_most(0.26)  # .8*.2 + .125*.8
    signal = builder.derive("signal", value=choose(positive, "Positive", "Negative"))
    posterior_q = QuestionNumerical(question_name="posterior", question_text=f"The diagnostic signal is {signal.field('value').template}. Sensitivity is 80%, false-positive rate is 12.5%, and base rate is 20%. Report P(disease) from 0 to 100.", min_value=0, max_value=100, include_comment=False)
    posterior = builder.step("posterior", Survey([posterior_q]), assigned_to=role("decision-maker"), after=prior)
    benchmark = choose(positive, 100 * (0.8 * 0.2) / 0.26, 100 * (0.2 * 0.2) / 0.74)
    outcome = builder.derive("assessment", benchmark=benchmark, absolute_error=(posterior.answer("posterior").value - benchmark).absolute())
    report_q = QuestionFreeText(question_name="result", question_text=f"Record benchmark posterior={outcome.field('benchmark').template} and absolute error={outcome.field('absolute_error').template}.")
    builder.step("assess", Survey([report_q]), assigned_to=role("analyst"), after=posterior)
    return GalleryCase("bayesian-updating", "Bayesian updating", "prior -> private diagnostic signal -> posterior", builder.compile(), (), _game_agents("decision-maker", "analyst"), bayesian_updating_case,
        ("Signal-generation and Bayes formulas repeat treatment parameters.", "The prior report is observational rather than used by the benchmark."),
        ("DiagnosticTest(sensitivity, specificity, prevalence)", "bayes_posterior(signal)", "workflow.parameter(...)"))


def intertemporal_choice_case() -> GalleryCase:
    builder = Workflow("Intertemporal choice")
    q1 = QuestionMultipleChoice(question_name="choice", question_text="Choose one payment: $10 today or $12 in 30 days.", question_options=["$10 today", "$12 in 30 days"])
    first = builder.step("near-term-choice", Survey([q1]), assigned_to=role("decision-maker"))
    q2 = QuestionMultipleChoice(question_name="choice", question_text="Choose one payment: $10 in 365 days or $12 in 395 days.", question_options=["$10 in 365 days", "$12 in 395 days"])
    second = builder.step("future-choice", Survey([q2]), assigned_to=role("decision-maker"), after=first)
    immediate = first.answer("choice").value.compare_equals("$10 today")
    delayed_later = second.answer("choice").value.compare_equals("$12 in 395 days")
    outcome = builder.derive("classification", pattern=choose(immediate, choose(delayed_later, "present-biased reversal", "earlier-payment pattern"), choose(delayed_later, "later-payment pattern", "reverse inconsistency")))
    report_q = QuestionFreeText(question_name="result", question_text=f"Record authoritative classification={outcome.field('pattern').template}.")
    builder.step("classify", Survey([report_q]), assigned_to=role("analyst"), after=second)
    return GalleryCase("intertemporal-choice", "Intertemporal choice", "dated payment choices -> consistency classification", builder.compile(), (), _game_agents("decision-maker", "analyst"), intertemporal_choice_case,
        ("Amounts and dates are embedded in labels.",),
        ("DatedPayment(amount, date)", "discount_rate(choice)", "choice_pattern({...})"))


def holt_laury_case() -> GalleryCase:
    builder = Workflow("Holt-Laury risk list")
    table = ChoiceTable("choices", "For every row choose A ($2.00/$1.60) or B ($3.85/$0.10). The chance of the high payoff is row number times 10 percent.", [str(i) for i in range(1, 11)], ["A", "B"], require_monotone=True)
    choice = builder.structured_step("risk-list", table, assigned_to=role("decision-maker"))
    paid_row = seeded_integer(1, 10, key="paid-risk-row")
    selected = choice.answer("choices").value.item(paid_row)
    outcome = builder.derive("selection", paid_row=paid_row, selected_option=selected)
    report_q = QuestionFreeText(question_name="result", question_text=f"Record paid row={outcome.field('paid_row').template} and selected option={outcome.field('selected_option').template}.")
    builder.step("select-row", Survey([report_q]), assigned_to=role("analyst"), after=choice)
    return GalleryCase("holt-laury", "Holt–Laury risk list", "choice list -> random paid row -> selected lottery", builder.compile(), (), _game_agents("decision-maker", "analyst"), holt_laury_case,
        ("Lottery rows exist only in prose and the selected lottery is not yet resolved.",),
        ("Lottery.resolve()", "typed row payloads"))


def time_price_list_case() -> GalleryCase:
    builder = Workflow("Time-preference price list")
    table = ChoiceTable("choices", "For every row choose $10 today or the delayed payment in 30 days. Delayed amounts rise from $10.50 in row 1 by $0.50 per row.", [str(i) for i in range(1, 11)], ["$10 today", "Delayed"], require_monotone=True)
    choice = builder.structured_step("time-list", table, assigned_to=role("decision-maker"))
    paid_row = seeded_integer(1, 10, key="paid-time-row")
    payment = choice.answer("choices").value.item(paid_row)
    outcome = builder.derive("selection", paid_row=paid_row, payment=payment)
    report_q = QuestionFreeText(question_name="result", question_text=f"Record paid row={outcome.field('paid_row').template} and selected payment={outcome.field('payment').template}.")
    builder.step("select-row", Survey([report_q]), assigned_to=role("analyst"), after=choice)
    return GalleryCase("time-price-list", "Time-preference multiple price list", "dated choice list -> random paid row", builder.compile(), (), _game_agents("decision-maker", "analyst"), time_price_list_case,
        ("The row-to-amount schedule is encoded only in prose.", "There is no fulfillment record for delayed payment."),
        ("DatedPayment", "FulfillmentSchedule", "typed row payloads"))


def dictator_strategy_method_case() -> GalleryCase:
    builder = Workflow("Dictator strategy method")
    plan = StrategyTable("transfers", "For each possible recipient endowment, choose how many of your 10 tokens to transfer.", ["0", "5", "10"], list(range(11)))
    strategy = builder.structured_step("strategy", plan, assigned_to=role("dictator"))
    contingency = seeded_integer(0, 2, key="recipient-endowment")
    transfer = strategy.answer("transfers").value.item(contingency * 5)
    outcome = builder.derive("outcome", recipient_endowment=contingency * 5, transfer=transfer, dictator_payoff=10 - transfer, recipient_payoff=contingency * 5 + transfer)
    report_q = QuestionFreeText(question_name="result", question_text=f"Record endowment={outcome.field('recipient_endowment').template}, transfer={outcome.field('transfer').template}, and payoffs dictator={outcome.field('dictator_payoff').template}, recipient={outcome.field('recipient_payoff').template}.")
    builder.step("implement", Survey([report_q]), assigned_to=role("analyst"), after=strategy)
    return GalleryCase("dictator-strategy-method", "Dictator strategy method", "contingent transfer plan -> random contingency", builder.compile(), (), _game_agents("dictator", "analyst"), dictator_strategy_method_case,
        ("All rows share one option set; richer contingent plans may require row-specific response schemas.",),
        ("row-specific table options", "ContingentPlan"))


def public_goods_punishment_case() -> GalleryCase:
    builder = Workflow("Public goods with punishment")
    cq = QuestionNumerical(question_name="contribution", question_text="You have 10 tokens. Privately contribute 0-10. Each contributed token produces 0.4 tokens for every group member.", min_value=0, max_value=10, include_comment=False)
    contribute = builder.step("contribute", Survey([cq]), assigned_to=role("player"), visible_to=(role("player"), role("analyst")))
    total = contribute.outputs("contribution").sum()
    group = builder.derive("group", total_contribution=total)
    pq = QuestionNumerical(question_name="punishment_points", question_text=f"The group contributed {group.field('total_contribution').template}. Buy 0-3 total punishment points at a cost of 1 token each. (This simplified stress test does not yet support target-specific allocations.)", min_value=0, max_value=3, include_comment=False)
    punish = builder.step("punish", Survey([pq]), assigned_to=role("player"), after=contribute, visible_to=role("analyst"))
    total_punishment = punish.outputs("punishment_points").sum()
    history = join_by_participant(contribution=contribute.submissions, punishment=punish.submissions)
    public_return = 0.4 * total
    payoffs = history.map(10 - history.value("contribution", "contribution") + public_return - history.value("punishment", "punishment_points"))
    outcome = builder.derive("outcome", total_contribution=total, public_return=public_return, punishment_points=total_punishment, payoffs=payoffs)
    report_q = QuestionFreeText(question_name="result", question_text=f"Record total contribution={outcome.field('total_contribution').template}, equal public return={outcome.field('public_return').template}, punishment points purchased={outcome.field('punishment_points').template}, and identity-keyed payoffs={outcome.field('payoffs').template}.")
    builder.step("settle", Survey([report_q]), assigned_to=role("analyst"), after=punish)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Choose strategically in a public-goods game with a later punishment stage.") for i in range(1, 5))
    return GalleryCase("public-goods-punishment", "Public goods with punishment", "contributions -> observed outcome -> punishment stage", builder.compile(), (), players + _game_agents("analyst"), public_goods_punishment_case,
        ("Punishment is scalar because target-by-target allocation lacks a structured response.",),
        ("AllocationVector(targets, budget)", "step.output_table", "sanction_matrix"))


def volunteers_dilemma_case() -> GalleryCase:
    builder = Workflow("Volunteer's dilemma")
    benefit = builder.parameter("benefit", 10, unit="tokens")
    volunteer_cost = builder.parameter("volunteer_cost", 4, unit="tokens")
    q = QuestionMultipleChoice(question_name="action", question_text="Choose privately. If anyone volunteers, all receive benefit 10; each volunteer pays cost 4. If nobody volunteers, all receive 0.", question_options=["Volunteer", "Do not volunteer"])
    actions = builder.step("choose", Survey([q]), assigned_to=role("player"), visible_to=role("analyst"))
    volunteers = actions.outputs("action").count_value("Volunteer")
    provided = volunteers.compare_at_least(1)
    own = actions.submissions.each("action")
    payoff = choose(provided, benefit - choose(own.value.compare_equals("Volunteer"), volunteer_cost, 0), 0)
    outcome = builder.derive("outcome", volunteer_count=volunteers, provided=provided, payoffs=own.map(payoff))
    report_q = QuestionFreeText(question_name="result", question_text=f"Record volunteers={outcome.field('volunteer_count').template}, provision={outcome.field('provided').template}, and payoffs={outcome.field('payoffs').template}.")
    builder.step("settle", Survey([report_q]), assigned_to=role("analyst"), after=actions)
    players = tuple(Agent(name=f"player-{i}@simulated.email", traits={"role": "player"}, instruction="Choose strategically in the volunteer's dilemma.") for i in range(1, 7))
    return GalleryCase("volunteers-dilemma", "Volunteer's dilemma", "parallel volunteering -> threshold benefit -> mapped cost", builder.compile(), (), players + _game_agents("analyst"), volunteers_dilemma_case,
        ("Benefit and cost parameters are authoritative metadata and expressions, but prompt rendering does not yet consume parameter units automatically.",),
        ("parameter.template", "credit_each(payoffs)"))


def cournot_case() -> GalleryCase:
    builder = Workflow("Cournot oligopoly")
    demand_intercept = builder.parameter("demand_intercept", 100)
    marginal_cost = builder.parameter("marginal_cost", 10)
    q = QuestionNumerical(question_name="quantity", question_text="Choose a quantity from 0 to 25. Market price is max(0, 100 minus total industry quantity); marginal cost is 10.", min_value=0, max_value=25, include_comment=False)
    quantities = builder.step("choose-quantity", Survey([q]), assigned_to=role("firm"), visible_to=role("analyst"))
    total = quantities.outputs("quantity").sum()
    price = choose(demand_intercept.compare_at_least(total), demand_intercept - total, 0)
    own = quantities.submissions.each("quantity")
    profits = own.map((price - marginal_cost) * own.value)
    outcome = builder.derive("market", total_quantity=total, price=price, profits=profits)
    report = QuestionFreeText(question_name="result", question_text=f"Record total quantity={outcome.field('total_quantity').template}, price={outcome.field('price').template}, and firm profits={outcome.field('profits').template}.")
    builder.step("settle", Survey([report]), assigned_to=role("analyst"), after=quantities)
    firms = tuple(Agent(name=f"firm-{i}@simulated.email", traits={"role": "firm"}, instruction="Choose quantity strategically as a Cournot competitor.") for i in range(1, 6))
    return GalleryCase("cournot", "Cournot quantity competition", "parallel quantities -> inverse demand -> mapped profits", builder.compile(), (), firms + _game_agents("analyst"), cournot_case,
        ("The prompt manually repeats parameter values.", "The nonnegative price floor is a hand-built conditional."),
        ("parameter.template", "maximum(expression, 0)", "history.lag()"))


def monopoly_case() -> GalleryCase:
    builder = Workflow("Experimental monopoly")
    q = QuestionMultipleChoice(question_name="price", question_text="Choose a posted price. Demand is 8 units at 2, 6 at 4, 4 at 6, 2 at 8, and 0 at 10. Unit cost is 1.", question_options=[2, 4, 6, 8, 10])
    decision = builder.step("set-price", Survey([q]), assigned_to=role("monopolist"))
    price = decision.answer("price").value
    quantity = lookup({2: 8, 4: 6, 6: 4, 8: 2, 10: 0}, price)
    outcome = builder.derive("market", price=price, quantity=quantity, profit=(price - 1) * quantity)
    report = QuestionFreeText(question_name="result", question_text=f"Record price={outcome.field('price').template}, quantity={outcome.field('quantity').template}, and profit={outcome.field('profit').template}.")
    builder.step("settle", Survey([report]), assigned_to=role("analyst"), after=decision)
    return GalleryCase("monopoly", "Experimental monopoly", "posted price -> demand lookup -> profit", builder.compile(), (), _game_agents("monopolist", "analyst"), monopoly_case,
        ("Demand is duplicated between prose and lookup data.",),
        ("DemandSchedule.render()", "piecewise_linear", "Money"))


def schelling_ranking_case() -> GalleryCase:
    builder = Workflow("Schelling tacit ranking")
    q = QuestionRank(question_name="ranking", question_text="Without communicating, rank A, B, and C in the order you expect everyone else to choose.", question_options=["A", "B", "C"], num_selections=3, use_code=False, include_comment=False)
    rankings = builder.step("rank", Survey([q]), assigned_to=role("player"), visible_to=role("analyst"))
    outcome = builder.derive("outcome", coordinated=rankings.outputs("ranking").all_equal())
    report = QuestionFreeText(question_name="result", question_text=f"Record whether every complete ranking matched: {outcome.field('coordinated').template}. Rankings: {rankings.outputs('ranking').template}.")
    builder.step("settle", Survey([report]), assigned_to=role("analyst"), after=rankings)
    players = tuple(Agent(name=f"player-{label}@simulated.email", traits={"role": "player"}, instruction="Seek a salient common ranking without communication.") for label in "ABC")
    return GalleryCase("schelling-ranking", "Schelling tacit ranking", "parallel rankings -> structural equality -> coordination", builder.compile(), (), players + _game_agents("analyst"), schelling_ranking_case,
        ("Rank-dependent prizes require finding each participant label's position in the agreed list.",),
        ("list.index(value)", "invert_ranking", "rank_payoffs"))


def curse_of_knowledge_case() -> GalleryCase:
    builder = Workflow("Curse of knowledge")
    baseline_q = QuestionMultipleChoice(question_name="guess", question_text="Without looking anything up: which city is farther north, Rome or New York?", question_options=["Rome", "New York"])
    baseline = builder.step("uninformed-guess", Survey([baseline_q]), assigned_to=role("uninformed"), visible_to=role("analyst"))
    predict_q = QuestionMultipleChoice(question_name="prediction", question_text="The correct answer is Rome. Predict which answer the uninformed participant gave.", question_options=["Rome", "New York"])
    prediction = builder.step("informed-prediction", Survey([predict_q]), assigned_to=role("informed"), after=baseline, visible_to=role("analyst"))
    matched = prediction.answer("prediction").value.compare_equals(baseline.answer("guess").value)
    outcome = builder.derive("outcome", prediction_matched=matched)
    report = QuestionFreeText(question_name="result", question_text=f"Record whether the informed prediction matched the uninformed response: {outcome.field('prediction_matched').template}.")
    builder.step("score", Survey([report]), assigned_to=role("analyst"), after=prediction)
    return GalleryCase("curse-of-knowledge", "Curse-of-knowledge task", "uninformed response -> truth reveal -> informed prediction", builder.compile(), (), _game_agents("uninformed", "informed", "analyst"), curse_of_knowledge_case,
        ("The truth is repeated as prompt text rather than a typed information release.",),
        ("InformationPacket", "reveal_to(role)", "match_predictions"))


def sequential_search_case() -> GalleryCase:
    builder = Workflow("Sequential search")
    offer1 = builder.derive("offer1", value=seeded_integer(5, 20, key="offer-1"))
    q1 = QuestionYesNo(question_name="accept", question_text=f"Offer 1 pays {offer1.field('value').template}. Accept it, or pay 1 token to search again?")
    first = builder.step("offer-1", Survey([q1]), assigned_to=role("searcher"))
    offer2 = builder.derive("offer2", value=seeded_integer(5, 20, key="offer-2"))
    q2 = QuestionYesNo(question_name="accept", question_text=f"After one search cost, offer 2 pays {offer2.field('value').template}. Accept it, or pay another token for a final draw?")
    second = builder.step("offer-2", Survey([q2]), assigned_to=role("searcher"), after=first, when=first.answer("accept").equals("No"))
    offer3 = builder.derive("offer3", value=seeded_integer(5, 20, key="offer-3"))
    q3 = QuestionFreeText(question_name="acknowledge", question_text=f"The final mandatory offer is {offer3.field('value').template}. Acknowledge receipt.")
    third = builder.step("offer-3", Survey([q3]), assigned_to=role("searcher"), after=second, when=second.answer("accept").equals("No"))
    accepted_first = first.answer("accept").value.compare_equals("Yes")
    accepted_second = second.answer("accept").value.compare_equals("Yes")
    payoff = choose(accepted_first, offer1.field("value").expression, choose(accepted_second, offer2.field("value").expression - 1, offer3.field("value").expression - 2))
    outcome = builder.derive("outcome", payoff=payoff)
    report = QuestionFreeText(question_name="result", question_text=f"Record authoritative net payoff={outcome.field('payoff').template}.")
    builder.step("settle", Survey([report]), assigned_to=role("analyst"), after_settled=third)
    return GalleryCase("sequential-search", "Sequential search task", "offer -> accept or costly continuation -> terminal payoff", builder.compile(), (), _game_agents("searcher", "analyst"), sequential_search_case,
        ("Offer stages are manually unrolled.", "The final settlement join depends on skipped-step propagation."),
        ("search_until(accept, cost, max_draws)", "on_termination", "OfferStream"))


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
        minimum_effort_case(),
        threshold_public_good_case(),
        second_price_auction_case(),
        best_shot_case(),
        impunity_case(),
        third_price_auction_case(),
        schelling_claims_case(),
        commons_dilemma_case(),
        median_effort_case(),
        allais_case(),
        ellsberg_case(),
        preference_reversal_case(),
        bdm_valuation_case(),
        binary_lottery_case(),
        probability_calibration_case(),
        bayesian_updating_case(),
        intertemporal_choice_case(),
        holt_laury_case(),
        time_price_list_case(),
        dictator_strategy_method_case(),
        public_goods_punishment_case(),
        volunteers_dilemma_case(),
        cournot_case(),
        monopoly_case(),
        schelling_ranking_case(),
        curse_of_knowledge_case(),
        sequential_search_case(),
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
    elif case.slug == "minimum-effort":
        efforts = [float(answer["effort"]) for answer in store.step_answers(instance_id, "choose-effort")]
        summary += f" Efforts were {efforts}; the authoritative group minimum was {min(efforts):g}."
    elif case.slug == "threshold-public-good":
        contributions = [float(answer["contribution"]) for answer in store.step_answers(instance_id, "contribute")]
        summary += f" Contributions were {contributions}; their total was {sum(contributions):g}, so provision was {sum(contributions) >= 30}."
    elif case.slug == "second-price-auction":
        bids = sorted((float(answer["bid"]) for answer in store.step_answers(instance_id, "sealed-bid")), reverse=True)
        summary += f" Descending bids were {bids}; the authoritative second-price payment was {bids[1]:g}."
    elif case.slug == "best-shot":
        contributions = [float(answer["contribution"]) for answer in store.step_answers(instance_id, "contribute")]
        summary += f" Contributions were {contributions}; the best shot was {max(contributions):g} and total cost was {sum(contributions):g}."
    elif case.slug == "impunity":
        offer = store.step_answers(instance_id, "allocate")[0]["offer"]
        accepted = store.step_answers(instance_id, "respond")[0]["accept"]
        summary += f" The allocator offered {offer} and the recipient answered {accepted}; the allocator's payoff was unaffected by that response."
    elif case.slug == "third-price-auction":
        bids = sorted((float(answer["bid"]) for answer in store.step_answers(instance_id, "sealed-bid")), reverse=True)
        summary += f" Descending bids were {bids}; the authoritative third-price payment was {bids[2]:g}."
    elif case.slug == "schelling-claims":
        claims = [float(answer["claim"]) for answer in store.step_answers(instance_id, "claim")]
        summary += f" Claims were {claims}; total claims were {sum(claims):g}, so feasibility was {sum(claims) <= 100}."
    elif case.slug == "commons-dilemma":
        actions = [answer["action"] for answer in store.step_answers(instance_id, "choose")]
        summary += f" Actions were {actions}; {actions.count('Exploit')} participants exploited and commons survival was {actions.count('Exploit') <= 2}."
    elif case.slug == "median-effort":
        actions = sorted(float(answer["action"]) for answer in store.step_answers(instance_id, "choose"))
        summary += f" Sorted actions were {actions}; the authoritative median was {actions[len(actions) // 2]:g}."
    elif case.slug == "allais":
        first = store.step_answers(instance_id, "first-choice")[0]["first_choice"]
        second = store.step_answers(instance_id, "second-choice")[0]["second_choice"]
        summary += f" The decision maker chose {first!r}, then {second!r}."
    elif case.slug == "ellsberg":
        first = store.step_answers(instance_id, "single-color-bet")[0]["first_bet"]
        second = store.step_answers(instance_id, "two-color-bet")[0]["second_bet"]
        summary += f" The decision maker chose {first!r}, then {second!r}."
    elif case.slug == "preference-reversal":
        choice = store.step_answers(instance_id, "choose-lottery")[0]["preferred"]
        prices = store.step_answers(instance_id, "value-lotteries")[0]
        summary += f" The participant chose {choice} and priced P at {prices['p_price']} versus Dollar at {prices['dollar_price']}."
    elif case.slug == "bdm-valuation":
        report = store.step_answers(instance_id, "state-value")[0]["reservation_price"]
        derived = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["outcome"]
        summary += f" The participant reported {report}; the stable offer was {derived['random_offer']:.2f}, so sold={derived['sold']}."
    elif case.slug == "binary-lottery":
        choice = store.step_answers(instance_id, "choose")[0]["choice"]
        derived = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["outcome"]
        summary += f" The participant chose {choice}; draw={derived['draw']:.3f} produced payoff={derived['payoff']}."
    elif case.slug == "probability-calibration":
        forecast = store.step_answers(instance_id, "forecast")[0]["forecast"]
        derived = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["score"]
        summary += f" The forecast was {forecast}%; occurred={derived['occurred']}; quadratic score={derived['quadratic_score']:.2f}."
    elif case.slug == "bayesian-updating":
        prior = store.step_answers(instance_id, "prior")[0]["prior"]
        posterior = store.step_answers(instance_id, "posterior")[0]["posterior"]
        derived = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)
        summary += f" Prior={prior}%, signal={derived['signal']['value']}, posterior={posterior}%, benchmark={derived['assessment']['benchmark']:.2f}%."
    elif case.slug == "intertemporal-choice":
        first = store.step_answers(instance_id, "near-term-choice")[0]["choice"]
        second = store.step_answers(instance_id, "future-choice")[0]["choice"]
        pattern = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["classification"]["pattern"]
        summary += f" Choices were {first!r} and {second!r}; classification={pattern}."
    elif case.slug in {"holt-laury", "time-price-list"}:
        step = "risk-list" if case.slug == "holt-laury" else "time-list"
        choices = store.step_answers(instance_id, step)[0]["choices"]
        selection = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["selection"]
        summary += f" The complete row choices were {choices}; row {selection['paid_row']} was selected, implementing {selection.get('selected_option', selection.get('payment'))}."
    elif case.slug == "dictator-strategy-method":
        strategy = store.step_answers(instance_id, "strategy")[0]["transfers"]
        outcome = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["outcome"]
        summary += f" The contingent transfers were {strategy}; the realized recipient endowment was {outcome['recipient_endowment']} and transfer was {outcome['transfer']}."
    elif case.slug == "public-goods-punishment":
        contributions = [answer["contribution"] for answer in store.step_answers(instance_id, "contribute")]
        punishments = [answer["punishment_points"] for answer in store.step_answers(instance_id, "punish")]
        summary += f" Contributions were {contributions}; subsequent punishment purchases were {punishments}."
    elif case.slug == "volunteers-dilemma":
        actions = [answer["action"] for answer in store.step_answers(instance_id, "choose")]
        outcome = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["outcome"]
        summary += f" Actions were {actions}; {outcome['volunteer_count']} volunteered and provision={outcome['provided']}."
    elif case.slug == "cournot":
        quantities = [answer["quantity"] for answer in store.step_answers(instance_id, "choose-quantity")]
        market = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["market"]
        summary += f" Firm quantities were {quantities}; total={market['total_quantity']}, price={market['price']}, profits={market['profits']}."
    elif case.slug == "monopoly":
        market = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["market"]
        summary += f" The monopolist chose price {market['price']}; demand was {market['quantity']} and profit was {market['profit']}."
    elif case.slug == "schelling-ranking":
        rankings = [answer["ranking"] for answer in store.step_answers(instance_id, "rank")]
        coordinated = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)["outcome"]["coordinated"]
        summary += f" Rankings were {rankings}; complete coordination={coordinated}."
    elif case.slug == "curse-of-knowledge":
        guess = store.step_answers(instance_id, "uninformed-guess")[0]["guess"]
        prediction = store.step_answers(instance_id, "informed-prediction")[0]["prediction"]
        summary += f" The uninformed answer was {guess}; the informed participant predicted {prediction}."
    elif case.slug == "sequential-search":
        derived = WorkflowCoordinator(case.workflow, store)._evaluate_derived(instance_id)
        decisions = {step: store.step_answers(instance_id, step) for step in ("offer-1", "offer-2", "offer-3")}
        summary += f" Search decisions were {decisions}; authoritative net payoff={derived['outcome']['payoff']}."
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
