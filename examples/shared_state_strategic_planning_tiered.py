"""Tiered strategic planning with feasible-package deliberation and selection."""

from itertools import product
from pathlib import Path

from edsl import (
    Model,
    QuestionDict,
    QuestionFreeText,
    QuestionMatrix,
    QuestionNumerical,
    QuestionRank,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedLog, SharedState

from shared_state_strategic_planning_workshop import (
    BUDGET,
    challenge_survey,
    executives,
    proposal_entries,
    proposal_survey,
    require_count,
)


TIERS = ("minimum", "target", "expanded")


def tier_survey(state: SharedState) -> Survey:
    minimum_cost = QuestionNumerical(
        question_name="minimum_cost",
        question_text=(
            "You are {{ agent.name }}. Review your proposal and all challenges:\n"
            "{{ shared_state.proposals.entries }}\n{{ shared_state.challenges.entries }}\n\n"
            "Set a minimum viable cost from 10 to 25 units."
        ),
        min_value=10,
        max_value=25,
    )
    minimum_outcome = QuestionFreeText(
        question_name="minimum_outcome",
        question_text="State the concrete deliverable at minimum funding in at most 30 words.",
    )
    target_cost = QuestionNumerical(
        question_name="target_cost",
        question_text="Set a target cost from 26 to 40 units.",
        min_value=26,
        max_value=40,
    )
    target_outcome = QuestionFreeText(
        question_name="target_outcome",
        question_text=(
            "State the additional measurable outcome delivered at target funding, "
            "beyond the minimum tier, in at most 30 words."
        ),
    )
    expanded_cost = QuestionNumerical(
        question_name="expanded_cost",
        question_text="Set an expanded cost from 41 to 60 units.",
        min_value=41,
        max_value=60,
    )
    expanded_outcome = QuestionFreeText(
        question_name="expanded_outcome",
        question_text=(
            "State the additional outcome delivered at expanded funding, beyond the "
            "target tier, in at most 30 words."
        ),
    )
    controls = QuestionDict(
        question_name="tier_controls",
        question_text=(
            "Provide one metric shared across tiers, the largest risk, its mitigation, "
            "and any hard dependency. Keep each field under 30 words."
        ),
        answer_keys=["metric", "risk", "mitigation", "dependency"],
        value_types=["str", "str", "str", "str"],
        value_descriptions=[
            "Measurable success metric",
            "Largest risk",
            "Concrete mitigation",
            "Hard dependency or none",
        ],
    )
    return Survey(
        [
            minimum_cost,
            minimum_outcome,
            target_cost,
            target_outcome,
            expanded_cost,
            expanded_outcome,
            controls,
            state.tiers.append(
                proposal_id="{{ agent.proposal_id }}",
                sponsor="{{ agent.name }}",
                minimum_cost=minimum_cost,
                minimum_outcome=minimum_outcome,
                target_cost=target_cost,
                target_outcome=target_outcome,
                expanded_cost=expanded_cost,
                expanded_outcome=expanded_outcome,
                controls=controls,
            ),
        ]
    )


def tier_entries(state: SharedState) -> dict[str, dict]:
    return {
        entry["proposal_id"]: entry for entry in state.read().state["tiers"]["entries"]
    }


def tier_options(state: SharedState) -> list[dict]:
    proposals = {entry["proposal_id"]: entry for entry in proposal_entries(state)}
    options = []
    for proposal_id, tier_plan in sorted(tier_entries(state).items()):
        for tier in TIERS:
            options.append(
                {
                    "id": f"{proposal_id}-{tier}",
                    "proposal_id": proposal_id,
                    "tier": tier,
                    "title": proposals[proposal_id]["title"],
                    "sponsor": proposals[proposal_id]["sponsor"],
                    "cost": tier_plan[f"{tier}_cost"],
                    "outcome": tier_plan[f"{tier}_outcome"],
                }
            )
    return options


def tier_voting_survey(state: SharedState, options: list[dict]) -> Survey:
    proposal_ids = sorted({option["proposal_id"] for option in options})
    slate = "\n".join(
        f"{option['id']}: {option['title']} — {option['cost']} units; {option['outcome']}"
        for option in options
    )
    vote = QuestionMatrix(
        question_name="tier_votes",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Rate the value-for-cost "
            "of each initiative after comparing its three funding tiers. The total "
            f"portfolio budget is {BUDGET}.\n\n{slate}"
        ),
        question_items=proposal_ids,
        question_options=["high", "medium", "low"],
        randomize_items=True,
    )
    return Survey([vote, state.tier_votes.append(voter="{{ agent.name }}", votes=vote)])


def candidate_portfolios(
    state: SharedState, options: list[dict], limit=3
) -> list[dict]:
    by_proposal = {}
    for option in options:
        by_proposal.setdefault(option["proposal_id"], []).append(option)
    weights = {"high": 2, "medium": 1, "low": 0}
    initiative_support = {proposal_id: 0 for proposal_id in by_proposal}
    for entry in state.read().state["tier_votes"]["entries"]:
        for proposal_id, vote in entry["votes"].items():
            initiative_support[proposal_id] += weights[vote]
    delivery_multiplier = {"minimum": 0.65, "target": 0.85, "expanded": 1.0}
    support = {
        option["id"]: initiative_support[option["proposal_id"]]
        * delivery_multiplier[option["tier"]]
        for option in options
    }
    candidates = []
    proposal_ids = sorted(by_proposal)
    choices = [[None, *by_proposal[proposal_id]] for proposal_id in proposal_ids]
    for selected in product(*choices):
        selected = [option for option in selected if option is not None]
        cost = sum(option["cost"] for option in selected)
        if not selected or cost > BUDGET:
            continue
        score = sum(support[option["id"]] for option in selected)
        candidates.append(
            {
                "options": selected,
                "cost": cost,
                "support": score,
                "initiative_count": len(selected),
            }
        )
    candidates.sort(
        key=lambda item: (
            -item["support"],
            -item["initiative_count"],
            item["cost"],
            [option["id"] for option in item["options"]],
        )
    )
    finalists = []
    seen = set()
    for candidate in candidates:
        signature = tuple(option["id"] for option in candidate["options"])
        if signature not in seen:
            finalists.append(candidate | {"id": f"Portfolio {len(finalists) + 1}"})
            seen.add(signature)
        if len(finalists) == limit:
            break
    return finalists


def format_portfolios(portfolios: list[dict]) -> str:
    return "\n".join(
        f"{portfolio['id']} ({portfolio['cost']}/{BUDGET}, initial support "
        f"{portfolio['support']}): "
        + "; ".join(
            f"{option['id']} {option['title']}" for option in portfolio["options"]
        )
        for portfolio in portfolios
    )


def package_discussion_survey(state: SharedState, portfolios: list[dict]) -> Survey:
    statement = QuestionFreeText(
        question_name="package_statement",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Debate the feasible "
            f"packages below, not isolated pet projects.\n\n{format_portfolios(portfolios)}\n\n"
            "Prior package discussion:\n{{ shared_state.package_discussion.entries }}\n\n"
            "Identify one cross-initiative complement, conflict, dependency, or omitted "
            "opportunity that should determine the final package. At most 60 words."
        ),
    )
    return Survey(
        [
            statement,
            state.package_discussion.append(
                speaker="{{ agent.name }}", statement=statement
            ),
        ]
    )


def package_ballot_survey(state: SharedState, portfolios: list[dict]) -> Survey:
    ballot = QuestionRank(
        question_name="package_ranking",
        question_text=(
            "Privately rank all feasible packages after reviewing the package-level "
            f"discussion.\n\n{format_portfolios(portfolios)}\n\nDiscussion:\n"
            "{{ shared_state.package_discussion.entries }}"
        ),
        question_options=[portfolio["id"] for portfolio in portfolios],
    )
    return Survey(
        [
            ballot,
            state.package_votes.append(voter="{{ agent.name }}", ranking=ballot),
        ]
    )


def select_package(state: SharedState, portfolios: list[dict]) -> tuple[dict, dict]:
    scores = {portfolio["id"]: 0 for portfolio in portfolios}
    for entry in state.read().state["package_votes"]["entries"]:
        for index, package_id in enumerate(entry["ranking"]):
            scores[package_id] += len(portfolios) - index - 1
    winner_id = sorted(scores, key=lambda item: (-scores[item], item))[0]
    return next(item for item in portfolios if item["id"] == winner_id), scores


def run_tiered_workshop(
    log_path: str | Path = "strategic-planning-tiered.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, dict, dict]:
    state = SharedState(
        "tiered-strategic-planning",
        FileStateStore(log_path),
        proposals=SharedLog(),
        challenges=SharedLog(),
        tiers=SharedLog(),
        tier_votes=SharedLog(),
        package_discussion=SharedLog(),
        package_votes=SharedLog(),
    )
    agents = executives()
    model = Model(model_name)
    run_options = {
        "disable_remote_inference": True,
        "disable_remote_cache": True,
        "cache": False,
        "stop_on_exceptions": True,
    }
    if state.read().state["proposals"]["count"] < 5:
        proposal_survey(state).by(agents).by(model).run(**run_options)
    require_count(state, "proposals", 5)
    if state.read().state["challenges"]["count"] < 5:
        challenge_survey(state).by(agents).by(model).run(
            interview_schedule="serial", **run_options
        )
    require_count(state, "challenges", 5)
    if state.read().state["tiers"]["count"] < 5:
        tier_survey(state).by(agents).by(model).run(**run_options)
    require_count(state, "tiers", 5)
    options = tier_options(state)
    if state.read().state["tier_votes"]["count"] < 5:
        tier_voting_survey(state, options).by(agents).by(model).run(**run_options)
    require_count(state, "tier_votes", 5)
    portfolios = candidate_portfolios(state, options)
    if state.read().state["package_discussion"]["count"] < 5:
        package_discussion_survey(state, portfolios).by(agents).by(model).run(
            interview_schedule="serial", **run_options
        )
    require_count(state, "package_discussion", 5)
    if state.read().state["package_votes"]["count"] < 5:
        package_ballot_survey(state, portfolios).by(agents).by(model).run(**run_options)
    require_count(state, "package_votes", 5)
    winner, scores = select_package(state, portfolios)
    state.close()
    return state, winner, scores


if __name__ == "__main__":
    shared_state, selected, tally = run_tiered_workshop()
    print(shared_state.render_markdown())
    print(f"\nSelected {selected['id']} ({selected['cost']}/{BUDGET})")
    for option in selected["options"]:
        print(f"- {option['id']}: {option['title']} — {option['outcome']}")
    print(f"Package Borda tally: {tally}")
