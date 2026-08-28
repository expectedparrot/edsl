"""LLM agents propose meeting agenda items, then vote on the shared slate."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    Model,
    QuestionFreeText,
    QuestionMatrix,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedAgenda, SharedState


def meeting_agents() -> AgentList:
    return AgentList(
        [
            Agent(
                name="Maya",
                traits={
                    "role": "CEO and meeting chair",
                    "priority": "alignment on the most consequential company decision",
                    "persona": "strategic, concise, and focused on decisions rather than updates",
                },
            ),
            Agent(
                name="Eli",
                traits={
                    "role": "engineering lead",
                    "priority": "technical reliability, delivery risks, and sustainable execution",
                    "persona": "pragmatic and specific about tradeoffs",
                },
            ),
            Agent(
                name="Sofia",
                traits={
                    "role": "sales lead",
                    "priority": "customer commitments, pipeline, and near-term revenue",
                    "persona": "customer-oriented and commercially urgent",
                },
            ),
            Agent(
                name="Noah",
                traits={
                    "role": "finance lead",
                    "priority": "runway, resource allocation, and measurable returns",
                    "persona": "analytical and disciplined about opportunity cost",
                },
            ),
            Agent(
                name="Priya",
                traits={
                    "role": "product and design lead",
                    "priority": "user needs, product quality, and a coherent roadmap",
                    "persona": "empathetic, evidence-driven, and attentive to product clarity",
                },
            ),
        ]
    )


def build_proposal_survey(state: SharedState) -> Survey:
    proposal = QuestionFreeText(
        question_name="agenda_proposal",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Your priority is "
            "{{ agent.priority }} and you are {{ agent.persona }}.\n\n"
            "Agenda items already proposed:\n{{ shared_state.agenda.proposals }}\n\n"
            "Propose one distinct agenda item for a 60-minute leadership meeting. "
            "Write a concrete decision-oriented title in at most 16 words. Do not "
            "repeat an existing item and do not include your name."
        ),
    )
    return Survey([proposal, state.agenda.propose(proposal)])


def build_voting_survey(state: SharedState) -> Survey:
    proposals = state.read().state["agenda"]["proposals"]
    item_ids = [item["id"] for item in proposals]
    slate = "\n".join(
        f"{item['id']}: {item['title']} (proposed by {item['proposer']})"
        for item in proposals
    )
    vote = QuestionMatrix(
        question_name="agenda_votes",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}. Your priority is "
            "{{ agent.priority }}.\n\n"
            f"Proposed agenda:\n{slate}\n\n"
            "Vote on every item. Vote up when it deserves scarce meeting time, "
            "neutral when useful but not essential, and down when it should be "
            "handled asynchronously. Judge all proposals, including your own."
        ),
        question_items=item_ids,
        question_options=["up", "neutral", "down"],
        randomize_items=True,
    )
    return Survey([vote, state.agenda.vote(vote)])


def run_agenda_simulation(
    log_path: str | Path = "meeting-agenda.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "leadership-meeting",
        FileStateStore(log_path),
        agenda=SharedAgenda(),
    )
    agents = meeting_agents()
    model = Model(model_name)

    # Proposals are serial so later participants can avoid duplicating earlier ideas.
    (
        build_proposal_survey(state)
        .by(agents)
        .by(model)
        .run(
            interview_schedule="serial",
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )

    # The resulting slate fixes the QuestionMatrix rows. Ballots are independent.
    (
        build_voting_survey(state)
        .by(agents)
        .by(model)
        .run(
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    return state


if __name__ == "__main__":
    print(run_agenda_simulation().render_markdown())
