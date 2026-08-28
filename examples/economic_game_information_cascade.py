"""Sequential social learning with public choices and private signals."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionMultipleChoice, Survey
from edsl.sharedstate import FileStateStore, SharedLog, SharedState


TRUE_STATE = "A"


def observers():
    signals = ["B", "B", "A", "A", "A", "A"]
    return AgentList(
        [
            Agent(
                name=f"Observer-{index}",
                traits={
                    "private_signal": signal,
                    "position": index,
                    "reasoning": "Bayesian and attentive to informational redundancy",
                },
            )
            for index, signal in enumerate(signals, 1)
        ]
    )


def run_simulation(
    path: str | Path = "economic-game-information-cascade.jsonl",
    model_name="gemini-2.5-flash",
):
    state = SharedState(
        "information-cascade",
        FileStateStore(path),
        choices=SharedLog(),
    )
    choice = QuestionMultipleChoice(
        question_name="choice",
        question_text=(
            "An unknown state is equally likely to be A or B. You are "
            "{{ agent.name }}, choosing sequentially at position {{ agent.position }}. "
            "Your private signal is {{ agent.private_signal }} and independently "
            "matches the true state with probability 0.70. Prior agents' public "
            "choices are {{ shared_state.choices.entries }}. You do not observe their "
            "signals. Choose the state you believe more likely. Remember that later "
            "public choices may repeat rather than add independent information."
        ),
        question_options=["A", "B"],
    )
    survey = Survey(
        [
            choice,
            state.choices.append(
                observer="{{ agent.name }}",
                position="{{ agent.position }}",
                choice=choice,
            ),
        ]
    )
    survey.by(observers()).by(Model(model_name)).run(
        interview_schedule="serial",
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    state.close()
    return state


def summarize(state):
    entries = state.read().state["choices"]["entries"]
    lines = [
        f"True state: {TRUE_STATE}",
        "",
        "| Position | Signal | Choice | Correct |",
        "|---:|---|---|---|",
    ]
    signal_by_name = {
        agent.name: agent.traits["private_signal"] for agent in observers()
    }
    for item in entries:
        lines.append(
            f"| {item['position']} | {signal_by_name[item['observer']]} | "
            f"{item['choice']} | {'yes' if item['choice'] == TRUE_STATE else 'no'} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(summarize(run_simulation()))
