"""Live capacity-constrained coalition formation with private preferences."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMultipleChoice,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedCoalitionPool, SharedState


COALITIONS = {
    "Growth": {
        "platform": "maximize adoption through an ambitious public launch",
        "capacity": 2,
    },
    "Safety": {
        "platform": "delay launch until reliability and safeguards improve",
        "capacity": 2,
    },
    "Bridge": {
        "platform": "run a limited pilot with staged safety checkpoints",
        "capacity": 2,
    },
}


def participants() -> AgentList:
    specs = [
        ("Amina", 0, "Growth > Bridge > Safety", "rapid adoption"),
        ("Ben", 1, "Growth > Bridge > Safety", "commercial momentum"),
        ("Clara", 2, "Growth > Bridge > Safety", "market leadership"),
        ("Diego", 3, "Safety > Bridge > Growth", "system reliability"),
        ("Elena", 4, "Safety > Bridge > Growth", "public accountability"),
        ("Farah", 5, "Safety > Bridge > Growth", "risk reduction"),
        ("Gus", 6, "Bridge > Growth > Safety", "pragmatic compromise"),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "seat": seat,
                    "private_ranking": ranking,
                    "motivation": motivation,
                },
            )
            for name, seat, ranking, motivation in specs
        ]
    )


def build_survey(state: SharedState) -> Survey:
    choice = QuestionMultipleChoice(
        question_name="coalition_choice",
        question_text=(
            "Round {{ run.round }} of 2. You are {{ agent.name }} and prioritize "
            "{{ agent.motivation }}. Your private ranking is "
            "{{ agent.private_ranking }}.\n\n"
            "Current coalition state: {{ shared_state.coalitions.coalitions }}\n"
            "Your membership: {{ shared_state.coalitions.your_membership }}\n"
            "Your previous request: {{ shared_state.coalitions.your_last_request }}\n"
            "Recent requests: {{ shared_state.coalitions.recent_requests }}\n\n"
            "Choose the coalition you now want to join. A full coalition rejects "
            "the request atomically and leaves your existing membership unchanged. "
            "Respond strategically to remaining capacity and prior rejections."
        ),
        question_options=list(COALITIONS),
    )
    return Survey([choice, state.coalitions.request(choice)])


def run_simulation(
    log_path: str | Path = "coalition-formation.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "launch-coalitions",
        FileStateStore(log_path),
        coalitions=SharedCoalitionPool(COALITIONS),
    )
    schedule = InterviewSchedule.rounds(
        count=2,
        within_round="serial",
        state_visibility="live",
        order_by="seat",
        round_order="rotate",
    )
    (
        build_survey(state)
        .by(participants())
        .by(Model(model_name))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    state.close()
    return state


if __name__ == "__main__":
    print(run_simulation().render_markdown())
