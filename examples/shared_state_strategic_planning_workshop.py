"""A strategic-planning workshop that funds a portfolio under a fixed budget."""

from itertools import combinations
from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    Model,
    QuestionDict,
    QuestionFreeText,
    QuestionMatrix,
    QuestionMultipleChoice,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedLog, SharedState


BUDGET = 100


def executives() -> AgentList:
    specs = [
        ("Maya", "CEO", "P1", "company strategy and durable differentiation"),
        (
            "Eli",
            "Engineering VP",
            "P2",
            "reliability, platform leverage, and execution capacity",
        ),
        (
            "Sofia",
            "Sales VP",
            "P3",
            "revenue growth, customer commitments, and market access",
        ),
        (
            "Priya",
            "Product VP",
            "P4",
            "customer value, adoption, and coherent product direction",
        ),
        (
            "Noah",
            "Finance VP",
            "P5",
            "capital efficiency, risk, and measurable returns",
        ),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "role": role,
                    "proposal_id": proposal_id,
                    "priority": priority,
                },
            )
            for name, role, proposal_id, priority in specs
        ]
    )


def proposal_survey(state: SharedState) -> Survey:
    title = QuestionFreeText(
        question_name="initiative_title",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}, focused on "
            "{{ agent.priority }}. Propose one distinctive strategic initiative for "
            "the next year. Give only a concrete title of at most 10 words."
        ),
    )
    cost = QuestionNumerical(
        question_name="initial_cost",
        question_text=(
            "Estimate the initiative's required budget units from 20 to 60. The "
            f"company has {BUDGET} units total for all initiatives."
        ),
        min_value=20,
        max_value=60,
    )
    case = QuestionDict(
        question_name="initiative_case",
        question_text=(
            "Build a concise business case for {{ initiative_title.answer }} costing "
            "{{ initial_cost.answer }} units. Use at most 35 words per field."
        ),
        answer_keys=["outcome", "metric", "largest_risk", "dependency"],
        value_types=["str", "str", "str", "str"],
        value_descriptions=[
            "Expected strategic outcome",
            "One measurable success metric",
            "Largest execution or market risk",
            "Important dependency, or none",
        ],
    )
    return Survey(
        [
            title,
            cost,
            case,
            state.proposals.append(
                proposal_id="{{ agent.proposal_id }}",
                sponsor="{{ agent.name }}",
                title=title,
                cost=cost,
                business_case=case,
            ),
        ]
    )


def challenge_survey(state: SharedState) -> Survey:
    proposal_ids = [entry["proposal_id"] for entry in proposal_entries(state)]
    target = QuestionMultipleChoice(
        question_name="challenge_target",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Review the proposals and "
            "public challenges so far:\n{{ shared_state.proposals.entries }}\n"
            "{{ shared_state.challenges.entries }}\n\nSelect another sponsor's proposal "
            "whose assumptions most need scrutiny."
        ),
        question_options=proposal_ids,
    )
    challenge = QuestionFreeText(
        question_name="strategic_challenge",
        question_text=(
            "Challenge one specific assumption in {{ challenge_target.answer }}. "
            "Explain the decision-relevant risk or opportunity cost in at most 55 words."
        ),
    )
    return Survey(
        [
            target,
            challenge,
            state.challenges.append(
                challenger="{{ agent.name }}", target=target, challenge=challenge
            ),
        ]
    )


def revision_survey(state: SharedState) -> Survey:
    cost = QuestionNumerical(
        question_name="revised_cost",
        question_text=(
            "You are {{ agent.name }} revising {{ agent.proposal_id }}. Review all "
            "proposals and challenges:\n{{ shared_state.proposals.entries }}\n"
            "{{ shared_state.challenges.entries }}\n\nSubmit a defensible revised cost "
            "from 20 to 60 units."
        ),
        min_value=20,
        max_value=60,
    )
    revision = QuestionDict(
        question_name="revised_case",
        question_text=(
            "Revise your initiative after the challenges. In at most 40 words per "
            "field, state the refined outcome, metric, and concrete risk mitigation."
        ),
        answer_keys=["outcome", "metric", "risk_mitigation"],
        value_types=["str", "str", "str"],
        value_descriptions=[
            "Refined outcome",
            "Measurable success metric",
            "Response to the most important challenge",
        ],
    )
    return Survey(
        [
            cost,
            revision,
            state.revisions.append(
                proposal_id="{{ agent.proposal_id }}",
                sponsor="{{ agent.name }}",
                cost=cost,
                revised_case=revision,
            ),
        ]
    )


def voting_survey(state: SharedState) -> Survey:
    proposals = {entry["proposal_id"]: entry for entry in proposal_entries(state)}
    revisions = {entry["proposal_id"]: entry for entry in revision_entries(state)}
    slate = "\n".join(
        f"{proposal_id}: {proposal['title']} ({revisions[proposal_id]['cost']} units) — "
        f"{revisions[proposal_id]['revised_case']}"
        for proposal_id, proposal in sorted(proposals.items())
    )
    vote = QuestionMatrix(
        question_name="portfolio_votes",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Rate each revised "
            f"initiative for inclusion in a {BUDGET}-unit strategic portfolio. Judge "
            f"all proposals, including your own.\n\n{slate}"
        ),
        question_items=sorted(proposals),
        question_options=["high", "medium", "low"],
        randomize_items=True,
    )
    return Survey([vote, state.votes.append(voter="{{ agent.name }}", votes=vote)])


def proposal_entries(state: SharedState) -> list[dict]:
    return state.read().state["proposals"]["entries"]


def revision_entries(state: SharedState) -> list[dict]:
    return state.read().state["revisions"]["entries"]


def select_portfolio(state: SharedState) -> tuple[list[dict], int, int]:
    proposals = {entry["proposal_id"]: entry for entry in proposal_entries(state)}
    revisions = {entry["proposal_id"]: entry for entry in revision_entries(state)}
    weights = {"high": 2, "medium": 1, "low": 0}
    scores = {proposal_id: 0 for proposal_id in proposals}
    for entry in state.read().state["votes"]["entries"]:
        for proposal_id, vote in entry["votes"].items():
            scores[proposal_id] += weights[vote]
    feasible = []
    ids = sorted(proposals)
    for size in range(len(ids) + 1):
        for subset in combinations(ids, size):
            cost = sum(revisions[item]["cost"] for item in subset)
            if cost <= BUDGET:
                score = sum(scores[item] for item in subset)
                feasible.append((score, len(subset), -cost, subset))
    score, _, negative_cost, selected_ids = max(feasible)
    selected = [
        {
            "proposal_id": proposal_id,
            "title": proposals[proposal_id]["title"],
            "sponsor": proposals[proposal_id]["sponsor"],
            "cost": revisions[proposal_id]["cost"],
            "support_score": scores[proposal_id],
            **revisions[proposal_id]["revised_case"],
        }
        for proposal_id in selected_ids
    ]
    return selected, -negative_cost, score


def require_count(state: SharedState, primitive: str, expected: int) -> None:
    count = state.read().state[primitive]["count"]
    if count < expected:
        raise RuntimeError(
            f"{primitive} phase incomplete: expected {expected} persisted records, got {count}"
        )


def run_strategic_workshop(
    log_path: str | Path = "strategic-planning-workshop.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, list[dict], int, int]:
    state = SharedState(
        "annual-strategic-planning",
        FileStateStore(log_path),
        proposals=SharedLog(),
        challenges=SharedLog(),
        revisions=SharedLog(),
        votes=SharedLog(),
    )
    agents = executives()
    model = Model(model_name)
    options = {
        "disable_remote_inference": True,
        "disable_remote_cache": True,
        "cache": False,
        "stop_on_exceptions": True,
    }
    proposal_survey(state).by(agents).by(model).run(**options)
    require_count(state, "proposals", 5)
    challenge_survey(state).by(agents).by(model).run(
        interview_schedule="serial", **options
    )
    require_count(state, "challenges", 5)
    revision_survey(state).by(agents).by(model).run(**options)
    require_count(state, "revisions", 5)
    voting_survey(state).by(agents).by(model).run(**options)
    require_count(state, "votes", 5)
    selected, cost, score = select_portfolio(state)
    state.close()
    return state, selected, cost, score


if __name__ == "__main__":
    shared_state, portfolio, total_cost, support = run_strategic_workshop()
    print(shared_state.render_markdown())
    print(f"\nFunded portfolio ({total_cost}/{BUDGET}, support {support}):")
    for initiative in portfolio:
        print(
            f"- {initiative['proposal_id']} {initiative['title']} — "
            f"{initiative['cost']} units, support {initiative['support_score']}/10"
        )
