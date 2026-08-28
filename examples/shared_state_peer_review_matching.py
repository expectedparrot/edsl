"""Assign reviewers to papers using private rankings and deterministic priority."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionRank, Survey
from edsl.sharedstate import FileStateStore, SharedMatchPool, SharedState


PAPERS = {
    "P1": "Causal inference for marketplace experiments",
    "P2": "Privacy-preserving language-model evaluation",
    "P3": "Behavioral dynamics in repeated public-goods games",
}


def reviewers() -> AgentList:
    specs = [
        ("Rina", 1, "causal inference and field experiments", "P1"),
        ("Omar", 2, "privacy, security, and model evaluation", "P2"),
        ("Lin", 3, "behavioral economics and repeated games", "P3"),
        ("Mateo", 4, "experimental design and applied statistics", "P2"),
        ("Grace", 5, "machine learning evaluation and governance", "P1"),
        ("Tariq", 6, "game theory and computational social science", "P3"),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "review_order": order,
                    "expertise": expertise,
                    "conflict": conflict,
                },
            )
            for name, order, expertise, conflict in specs
        ]
    )


def build_survey(state: SharedState) -> Survey:
    paper_list = "\n".join(f"{key}: {title}" for key, title in PAPERS.items())
    ranking = QuestionRank(
        question_name="paper_ranking",
        question_text=(
            "You are reviewer {{ agent.name }} with expertise in "
            "{{ agent.expertise }}. You have a conflict with {{ agent.conflict }} "
            "and must rank it last.\n\n"
            f"Papers:\n{paper_list}\n\n"
            "Rank all paper IDs from best to worst review fit. Prefer papers where "
            "your expertise adds the most value, subject to the conflict rule."
        ),
        question_options=list(PAPERS),
    )
    return Survey(
        [
            ranking,
            state.assignments.collect(
                ranking,
                claimant="{{ agent.name }}",
                priority="{{ agent.review_order }}",
            ),
        ]
    )


def run_matching(
    log_path: str | Path = "peer-review-matching.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "peer-review-panel",
        FileStateStore(log_path),
        assignments=SharedMatchPool(list(PAPERS), capacity=2),
    )
    (
        build_survey(state)
        .by(reviewers())
        .by(Model(model_name))
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    state.close()
    return state


if __name__ == "__main__":
    print(run_matching().render_markdown())
