"""Repeated public-goods game using a generic shared append-only log."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionFreeText,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedLog, SharedState


ENDOWMENT = 20
MULTIPLIER = 1.6


def public_goods_agents() -> AgentList:
    return AgentList(
        [
            Agent(
                name="Avery",
                traits={
                    "strategy": "Conditional cooperator",
                    "persona": "You begin cooperatively but respond strongly to evidence of free-riding.",
                },
            ),
            Agent(
                name="Blake",
                traits={
                    "strategy": "Self-interested optimizer",
                    "persona": "You maximize your own total payoff and reason strategically about others.",
                },
            ),
            Agent(
                name="Casey",
                traits={
                    "strategy": "Group-oriented contributor",
                    "persona": "You value group welfare, fairness, and establishing cooperative norms.",
                },
            ),
            Agent(
                name="Devon",
                traits={
                    "strategy": "Reciprocal pragmatist",
                    "persona": "You match demonstrated cooperation but avoid being exploited.",
                },
            ),
        ]
    )


def build_round_survey(state: SharedState) -> Survey:
    contribution = QuestionNumerical(
        question_name="contribution",
        question_text=(
            "Round {{ run.round }} of 4 in a repeated public-goods game. "
            f"You receive {ENDOWMENT} tokens this round. Every contributed token "
            f"is multiplied by {MULTIPLIER} and divided equally among four players. "
            "Uncontributed tokens remain yours.\n\n"
            "Your strategy: {{ agent.strategy }}. {{ agent.persona }}\n\n"
            "Contribution history visible at this moment:\n"
            "{{ shared_state.contributions.entries }}\n\n"
            "Choose an integer contribution from 0 through 20."
        ),
        min_value=0,
        max_value=20,
    )
    rationale = QuestionFreeText(
        question_name="rationale",
        question_text=(
            "You chose to contribute {{ contribution.answer }} tokens in round "
            "{{ run.round }}. In one sentence, explain the strategic reason."
        ),
    )
    return Survey(
        [
            contribution,
            rationale,
            state.contributions.append(
                player="{{ agent.name }}",
                strategy="{{ agent.strategy }}",
                round="{{ run.round }}",
                amount=contribution,
                rationale=rationale,
            ),
        ]
    )


def summarize(state: SharedState) -> str:
    entries = state.read().state["contributions"]["entries"]
    by_round = {}
    payoffs = {agent.name: 0.0 for agent in public_goods_agents()}
    for entry in entries:
        by_round.setdefault(int(entry["round"]), []).append(entry)
    lines = ["# Repeated public-goods game", ""]
    for round_number, contributions in sorted(by_round.items()):
        pot = sum(entry["amount"] for entry in contributions)
        share = pot * MULTIPLIER / 4
        lines.extend(
            [
                f"## Round {round_number}",
                "",
                "| Player | Contribution | Round payoff | Rationale |",
                "|---|---:|---:|---|",
            ]
        )
        for entry in contributions:
            payoff = ENDOWMENT - entry["amount"] + share
            payoffs[entry["player"]] += payoff
            lines.append(
                f"| {entry['player']} | {entry['amount']:g} | {payoff:.1f} | "
                f"{entry['rationale']} |"
            )
        lines.extend(["", f"**Group contribution:** {pot:g}/80", ""])
    lines.extend(
        [
            "## Total payoffs",
            "",
            "| Player | Payoff |",
            "|---|---:|",
            *[
                f"| {player} | {payoff:.1f} |"
                for player, payoff in sorted(payoffs.items(), key=lambda item: -item[1])
            ],
        ]
    )
    return "\n".join(lines)


def run_public_goods(
    log_path: str | Path = "public-goods.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "public-goods-game",
        FileStateStore(log_path),
        contributions=SharedLog(),
    )
    agents = public_goods_agents()
    model = Model(model_name)
    schedule = InterviewSchedule.rounds(
        count=4, within_round="concurrent", state_visibility="snapshot"
    )
    (
        build_round_survey(state)
        .by(agents)
        .by(model)
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    return state


if __name__ == "__main__":
    print(summarize(run_public_goods()))
