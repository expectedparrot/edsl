"""One-shot public goods followed by sealed peer punishment."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMatrix,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedLog, SharedState


def players():
    specs = [
        ("Avery", "conditional cooperator who punishes clear free-riding"),
        ("Blake", "self-interested optimizer who avoids costly punishment"),
        ("Casey", "strong norm enforcer focused on group welfare"),
        ("Devon", "reciprocal pragmatist who uses proportionate sanctions"),
    ]
    return AgentList([Agent(name=n, traits={"strategy": s}) for n, s in specs])


def run_simulation(
    path: str | Path = "economic-game-public-goods-punishment.jsonl",
    model_name="gemini-2.5-flash",
):
    state = SharedState(
        "public-goods-punishment",
        FileStateStore(path),
        contributions=SharedLog(),
        punishments=SharedLog(),
    )
    agents, model = players(), Model(model_name)
    contribution = QuestionNumerical(
        question_name="contribution",
        question_text=(
            "You have 20 tokens. Four simultaneous contributions are multiplied by "
            "1.6 and divided equally; unspent tokens remain yours. You are "
            "{{ agent.name }}, a {{ agent.strategy }}. Choices are sealed. Contribute 0–20."
        ),
        min_value=0,
        max_value=20,
    )
    Survey(
        [
            contribution,
            state.contributions.append(player="{{ agent.name }}", amount=contribution),
        ]
    ).by(agents).by(model).run(
        interview_schedule=InterviewSchedule.rounds(count=1, reveal="after_round"),
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )

    entries = state.read().state["contributions"]["entries"]
    slate = ", ".join(f"{item['player']}={item['amount']}" for item in entries)
    names = [agent.name for agent in agents]
    punishment = QuestionMatrix(
        question_name="punishment",
        question_text=(
            f"Contributions were {slate}. You are {{{{ agent.name }}}}, a "
            "{{ agent.strategy }}. Assign 0–3 punishment points to every player. "
            "Each point costs you 1 token and reduces the target's payoff by 3. "
            "You may assign zero to yourself and everyone else."
        ),
        question_items=names,
        question_options=["0", "1", "2", "3"],
    )
    Survey(
        [
            punishment,
            state.punishments.append(player="{{ agent.name }}", points=punishment),
        ]
    ).by(agents).by(model).run(
        interview_schedule=InterviewSchedule.rounds(count=1, reveal="after_round"),
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    state.close()
    return state


def summarize(state):
    contributions = state.read().state["contributions"]["entries"]
    punishments = state.read().state["punishments"]["entries"]
    pot = sum(item["amount"] for item in contributions)
    share = 1.6 * pot / 4
    payoff = {item["player"]: 20 - item["amount"] + share for item in contributions}
    received = {name: 0 for name in payoff}
    spent = {name: 0 for name in payoff}
    for ballot in punishments:
        for target, points in ballot["points"].items():
            value = int(points)
            spent[ballot["player"]] += value
            received[target] += value
    lines = [
        f"Group contribution: {pot}/80",
        "",
        "| Player | Contributed | Punishment spent | Received | Final payoff |",
        "|---|---:|---:|---:|---:|",
    ]
    amounts = {item["player"]: item["amount"] for item in contributions}
    for name in payoff:
        final = payoff[name] - spent[name] - 3 * received[name]
        lines.append(
            f"| {name} | {amounts[name]} | {spent[name]} | {received[name]} | {final:.1f} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    result = run_simulation()
    print(summarize(result))
