"""Rumor diffusion over a network using a viewer-filtered SharedLog."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionFreeText, Survey
from edsl.sharedstate import FileStateStore, SharedLog, SharedState
from edsl.sharedstate.steps import StepContext


def network_agents() -> AgentList:
    return AgentList(
        [
            Agent(
                name="Alice",
                traits={
                    "neighbors": ["Ben", "Cara"],
                    "disposition": "excitable early adopter who readily shares interesting workplace news",
                },
            ),
            Agent(
                name="Ben",
                traits={
                    "neighbors": ["Alice", "Dina"],
                    "disposition": "careful skeptic who flags uncertainty and dislikes overclaiming",
                },
            ),
            Agent(
                name="Cara",
                traits={
                    "neighbors": ["Alice", "Eli"],
                    "disposition": "social connector who retells stories vividly and confidently",
                },
            ),
            Agent(
                name="Dina",
                traits={
                    "neighbors": ["Ben", "Eli"],
                    "disposition": "detail-oriented analyst who distinguishes evidence from hearsay",
                },
            ),
            Agent(
                name="Eli",
                traits={
                    "neighbors": ["Cara", "Dina"],
                    "disposition": "optimistic colleague inclined to interpret ambiguous news positively",
                },
            ),
        ]
    )


def build_survey(state: SharedState) -> Survey:
    message = QuestionFreeText(
        question_name="network_message",
        question_text=(
            "Round {{ agent.diffusion_round }} of a workplace information-sharing "
            "simulation. You are {{ agent.name }}, a {{ agent.disposition }}. Your "
            "network neighbors are {{ agent.neighbors }}.\n\n"
            "Messages visible to you:\n{{ shared_state.messages.entries }}\n\n"
            "Send one concise message to your neighbors describing what you currently "
            "believe is happening. Preserve caveats you consider important, but retell "
            "the information naturally in your own voice. If you have no credible new "
            "information, say so. Do not mention this is a simulation."
        ),
    )
    return Survey(
        [
            message,
            state.messages.append(
                sender="{{ agent.name }}",
                recipients="{{ agent.neighbors }}",
                round="{{ agent.diffusion_round }}",
                message=message,
            ),
        ]
    )


def seed_rumor(state: SharedState) -> None:
    state.messages.append(
        sender="System",
        recipients=["Alice"],
        round=0,
        message=(
            "A friend in HR says leadership may announce a four-day workweek next "
            "month, but they did not see an official memo."
        ),
    ).execute(StepContext({}, "seed"))


def run_diffusion(
    log_path: str | Path = "rumor-diffusion.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "workplace-network",
        FileStateStore(log_path),
        messages=SharedLog(visible_to="recipients"),
    )
    seed_rumor(state)
    agents = network_agents()
    model = Model(model_name)
    for round_number in range(1, 4):
        round_agents = agents.duplicate()
        for agent in round_agents:
            agent.traits["diffusion_round"] = round_number
        (
            build_survey(state)
            .by(round_agents)
            .by(model)
            .run(
                interview_schedule="serial",
                disable_remote_inference=True,
                disable_remote_cache=True,
                cache=False,
                stop_on_exceptions=True,
            )
        )
    return state


if __name__ == "__main__":
    result = run_diffusion()
    print(result.render_markdown())
