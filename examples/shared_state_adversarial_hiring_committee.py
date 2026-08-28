"""Hiring deliberation with conflicting candidates, recusal, and measured persuasion."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionFreeText, QuestionRank, Survey
from edsl.sharedstate import FileStateStore, SharedLog, SharedState


CANDIDATES = {
    "Atlas": "Exceptional technical architect; weak customer exposure and uneven cross-functional communication.",
    "Rowan": "Exceptional enterprise seller; limited technical depth and an aggressive short-term style.",
    "Morgan": "Strong, broadly acceptable general manager; few standout achievements but no major weakness.",
    "Quinn": "Exceptional operator and cost manager; cautious product instincts and limited growth experience.",
}


SPECS = [
    ("Maya", "CEO", "company-wide leadership and balanced judgment", None),
    ("Eli", "Engineering VP", "technical credibility and durable architecture", None),
    ("Sofia", "Sales VP", "commercial impact and customer trust", "Rowan"),
    ("Priya", "Product VP", "user-centered product judgment and collaboration", None),
    ("Noah", "Finance VP", "operating discipline and scalable economics", None),
]


def committee(*, voting_only: bool = False) -> AgentList:
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "role": role,
                    "priority": priority,
                    "conflict": conflict or "none",
                },
            )
            for name, role, priority, conflict in SPECS
            if not voting_only or conflict is None
        ]
    )


def ranking_survey(state: SharedState, phase: str) -> Survey:
    dossiers = "\n".join(f"{name}: {summary}" for name, summary in CANDIDATES.items())
    name = f"{phase}_ranking"
    ranking = QuestionRank(
        question_name=name,
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Your priority is "
            "{{ agent.priority }}. Your disclosed conflict is {{ agent.conflict }}. "
            f"Privately rank all candidates from strongest to weakest.\n\n{dossiers}"
        ),
        question_options=list(CANDIDATES),
    )
    log = state.initial_rankings if phase == "initial" else state.final_rankings
    return Survey(
        [
            ranking,
            log.append(reviewer="{{ agent.name }}", phase=phase, ranking=ranking),
        ]
    )


def deliberation_survey(state: SharedState) -> Survey:
    dossiers = "\n".join(f"{name}: {summary}" for name, summary in CANDIDATES.items())
    statement = QuestionFreeText(
        question_name="public_statement",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Your priority is "
            "{{ agent.priority }} and your disclosed conflict is {{ agent.conflict }}.\n\n"
            f"Candidate dossiers:\n{dossiers}\n\n"
            "Prior public statements:\n{{ shared_state.discussion.entries }}\n\n"
            "Make one concise, decision-relevant statement. If prior statements exist, "
            "explicitly challenge one claim or introduce material evidence not already "
            "raised. Do not merely agree. If you have a conflict, disclose it and avoid "
            "advocating for that candidate."
        ),
    )
    return Survey(
        [
            statement,
            state.discussion.append(speaker="{{ agent.name }}", statement=statement),
        ]
    )


def analyze(state: SharedState) -> tuple[str, dict[str, int], list[str]]:
    initial = {
        entry["reviewer"]: entry["ranking"]
        for entry in state.read().state["initial_rankings"]["entries"]
    }
    final = {
        entry["reviewer"]: entry["ranking"]
        for entry in state.read().state["final_rankings"]["entries"]
    }
    voters = set(final)
    scores = {candidate: 0 for candidate in CANDIDATES}
    for ranking in final.values():
        for index, candidate in enumerate(ranking):
            scores[candidate] += len(CANDIDATES) - index - 1
    changed = [name for name in sorted(voters) if initial[name] != final[name]]
    winner = sorted(scores, key=lambda candidate: (-scores[candidate], candidate))[0]
    return winner, scores, changed


def run_adversarial_hiring(
    log_path: str | Path = "hiring-committee-adversarial-live.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, str, dict[str, int], list[str]]:
    state = SharedState(
        "adversarial-hiring-committee",
        FileStateStore(log_path),
        initial_rankings=SharedLog(),
        discussion=SharedLog(),
        final_rankings=SharedLog(),
    )
    model = Model(model_name)
    options = {
        "disable_remote_inference": True,
        "disable_remote_cache": True,
        "cache": False,
        "stop_on_exceptions": True,
    }
    ranking_survey(state, "initial").by(committee()).by(model).run(**options)
    deliberation_survey(state).by(committee()).by(model).run(
        interview_schedule="serial", **options
    )
    ranking_survey(state, "final").by(committee(voting_only=True)).by(model).run(
        **options
    )
    winner, scores, changed = analyze(state)
    state.close()
    return state, winner, scores, changed


if __name__ == "__main__":
    shared_state, selected, tally, changed_voters = run_adversarial_hiring()
    print(shared_state.render_markdown())
    print(
        f"\nSelected: {selected}\nBorda tally: {tally}"
        f"\nVoters changing rankings: {changed_voters}"
    )
