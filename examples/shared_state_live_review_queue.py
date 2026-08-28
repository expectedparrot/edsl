"""Concurrent reviewers atomically claim distinct papers before prompt rendering."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionDict, Survey
from edsl.sharedstate import FileStateStore, SharedState, SharedWorkPool


PAPERS = [
    {
        "id": "paper-causal",
        "title": "Adaptive stopping in online field experiments",
        "abstract": "A sequential testing method for marketplace experiments with delayed outcomes.",
    },
    {
        "id": "paper-privacy",
        "title": "Private evaluation of language models",
        "abstract": "A framework for releasing benchmark aggregates under differential privacy.",
    },
    {
        "id": "paper-games",
        "title": "Cooperation under imperfect monitoring",
        "abstract": "Laboratory evidence from repeated public-goods games with noisy signals.",
    },
    {
        "id": "paper-agents",
        "title": "Auditing tool-using agents",
        "abstract": "Methods for reconstructing state reads, tool calls, and causal action traces.",
    },
]


def reviewers() -> AgentList:
    return AgentList(
        [
            Agent(name="Rina", traits={"expertise": "causal inference"}),
            Agent(name="Omar", traits={"expertise": "privacy and security"}),
            Agent(name="Lin", traits={"expertise": "behavioral economics"}),
            Agent(name="Grace", traits={"expertise": "AI evaluation"}),
        ]
    )


def build_survey(state: SharedState) -> Survey:
    review = QuestionDict(
        question_name="review",
        question_text=(
            "You are {{ agent.name }}, an expert in {{ agent.expertise }}. You have "
            "atomically claimed this paper:\n{{ shared_state.work.claimed }}\n\n"
            "Review only that paper. Give a recommendation and a concise rationale "
            "that identifies one strength and one concern."
        ),
        answer_keys=["recommendation", "rationale"],
        value_types=["str", "str"],
        value_descriptions=[
            "One of accept, revise, or reject",
            "A concise review with one strength and one concern",
        ],
    )
    claim = state.work.claim_before(review)
    return Survey([claim, review, state.work.complete(review)])


def run_queue(
    log_path: str | Path = "live-review-queue.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "live-review-queue",
        FileStateStore(log_path),
        work=SharedWorkPool(PAPERS),
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
    return state


if __name__ == "__main__":
    print(run_queue().render_markdown())
