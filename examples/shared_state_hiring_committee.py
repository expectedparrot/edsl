"""A multi-stage hiring committee with private reviews and a secret ballot."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionFreeText, QuestionRank, Survey
from edsl.sharedstate import FileStateStore, SharedLog, SharedState


CANDIDATES = {
    "Avery": "Product leader; strong customer discovery and cross-functional delivery.",
    "Blake": "Engineering leader; strong systems design and organizational scaling.",
    "Casey": "Commercial leader; strong enterprise sales and partnerships.",
    "Devon": "Operations leader; strong process design and financial discipline.",
}


def committee() -> AgentList:
    specs = [
        ("Maya", "CEO", "balanced leadership and company-wide judgment"),
        (
            "Eli",
            "Engineering VP",
            "technical depth and effective engineering leadership",
        ),
        ("Sofia", "Sales VP", "customer credibility and commercial impact"),
        ("Priya", "Product VP", "product judgment and user-centered execution"),
        ("Noah", "Finance VP", "operating discipline and scalable decision-making"),
    ]
    return AgentList(
        [
            Agent(name=name, traits={"role": role, "priority": priority})
            for name, role, priority in specs
        ]
    )


def private_review_survey(state: SharedState) -> Survey:
    dossiers = "\n".join(f"{name}: {summary}" for name, summary in CANDIDATES.items())
    ranking = QuestionRank(
        question_name="private_ranking",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Your hiring priority is "
            "{{ agent.priority }}. Independently rank every candidate from strongest "
            f"to weakest overall.\n\nCandidate dossiers:\n{dossiers}"
        ),
        question_options=list(CANDIDATES),
    )
    rationale = QuestionFreeText(
        question_name="private_rationale",
        question_text=(
            "Briefly explain your private ranking {{ private_ranking.answer }}. "
            "Identify the most important strength and concern in at most 70 words."
        ),
    )
    return Survey(
        [
            ranking,
            rationale,
            state.private_reviews.append(
                reviewer="{{ agent.name }}", ranking=ranking, rationale=rationale
            ),
        ]
    )


def shortlist_from_private_reviews(state: SharedState, size: int = 3) -> list[str]:
    entries = state.read().state["private_reviews"]["entries"]
    scores = {candidate: 0 for candidate in CANDIDATES}
    for entry in entries:
        for index, candidate in enumerate(entry["ranking"]):
            scores[candidate] += len(CANDIDATES) - index - 1
    return sorted(scores, key=lambda candidate: (-scores[candidate], candidate))[:size]


def deliberation_survey(state: SharedState, shortlist: list[str]) -> Survey:
    comment = QuestionFreeText(
        question_name="committee_statement",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. The anonymized scoring "
            f"shortlisted {', '.join(shortlist)}.\n\nPublic comments so far:\n"
            "{{ shared_state.public_discussion.entries }}\n\nAdd one concise public "
            "comment that responds to the discussion and identifies a decisive "
            "comparison. Do not reveal your private ranking."
        ),
    )
    return Survey(
        [
            comment,
            state.public_discussion.append(speaker="{{ agent.name }}", comment=comment),
        ]
    )


def ballot_survey(state: SharedState, shortlist: list[str]) -> Survey:
    ballot = QuestionRank(
        question_name="secret_ballot",
        question_text=(
            "After the committee discussion, privately rank the shortlisted candidates "
            "from your preferred hire to least preferred. Vote using your own judgment."
        ),
        question_options=shortlist,
    )
    return Survey(
        [
            ballot,
            state.secret_ballots.append(voter="{{ agent.name }}", ranking=ballot),
        ]
    )


def final_tally(state: SharedState, shortlist: list[str]) -> tuple[str, dict[str, int]]:
    entries = state.read().state["secret_ballots"]["entries"]
    scores = {candidate: 0 for candidate in shortlist}
    for entry in entries:
        for index, candidate in enumerate(entry["ranking"]):
            scores[candidate] += len(shortlist) - index - 1
    winner = sorted(scores, key=lambda candidate: (-scores[candidate], candidate))[0]
    return winner, scores


def run_hiring_committee(
    log_path: str | Path = "hiring-committee-live.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, list[str], str, dict[str, int]]:
    state = SharedState(
        "vp-hiring-committee",
        FileStateStore(log_path),
        private_reviews=SharedLog(),
        public_discussion=SharedLog(),
        secret_ballots=SharedLog(),
    )
    agents = committee()
    model = Model(model_name)
    run_options = {
        "disable_remote_inference": True,
        "disable_remote_cache": True,
        "cache": False,
        "stop_on_exceptions": True,
    }

    private_review_survey(state).by(agents).by(model).run(**run_options)
    shortlist = shortlist_from_private_reviews(state)
    deliberation_survey(state, shortlist).by(agents).by(model).run(
        interview_schedule="serial", **run_options
    )
    ballot_survey(state, shortlist).by(agents).by(model).run(**run_options)
    winner, scores = final_tally(state, shortlist)
    state.close()
    return state, shortlist, winner, scores


if __name__ == "__main__":
    shared_state, finalists, selected, tally = run_hiring_committee()
    print(shared_state.render_markdown())
    print(f"\nShortlist: {finalists}\nSelected: {selected}\nBorda tally: {tally}")
