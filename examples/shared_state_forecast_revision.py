"""Forecasters update private-signal estimates after seeing a live consensus."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionNumerical, Survey
from edsl.sharedstate import FileStateStore, SharedForecast, SharedState


def forecasters() -> AgentList:
    signals = [
        ("Aria", 78, "product telemetry specialist", "trusts behavioral usage data"),
        ("Basil", 64, "sales-operations analyst", "trusts customer commitments"),
        ("Chen", 42, "reliability engineer", "focuses on technical failure modes"),
        ("Dara", 28, "financial risk analyst", "uses conservative base rates"),
        (
            "Emi",
            55,
            "market researcher",
            "balances qualitative and quantitative evidence",
        ),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "private_signal": signal,
                    "expertise": expertise,
                    "method": method,
                },
            )
            for name, signal, expertise, method in signals
        ]
    )


def build_survey(state: SharedState) -> Survey:
    forecast = QuestionNumerical(
        question_name="probability",
        question_text=(
            "You are {{ agent.name }}, a {{ agent.expertise }} who {{ agent.method }}. "
            "Estimate the probability that Project Atlas will reach 100,000 weekly "
            "active users within six months. Your private evidence implies "
            "{{ agent.private_signal }}%.\n\n"
            "Forecasts visible at this moment:\n{{ shared_state.forecasts.latest }}\n"
            "Current confidence-weighted consensus: "
            "{{ shared_state.forecasts.confidence_weighted_probability }}\n\n"
            "Give your best probability from 0 to 100. Use others' forecasts as "
            "evidence, but do not discard your private signal without reason."
        ),
        min_value=0,
        max_value=100,
    )
    confidence = QuestionNumerical(
        question_name="confidence",
        question_text=(
            "You forecast {{ probability.answer }}%. Rate your confidence in that "
            "estimate from 0 to 100, considering your evidence and the visible "
            "disagreement among other forecasters."
        ),
        min_value=0,
        max_value=100,
    )
    return Survey([forecast, confidence, state.forecasts.submit(forecast, confidence)])


def run_forecasts(
    log_path: str | Path = "forecast-revision.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "atlas-forecast",
        FileStateStore(log_path),
        forecasts=SharedForecast(),
    )
    agents = forecasters()
    model = Model(model_name)
    schedule = InterviewSchedule.rounds(
        count=3, within_round="concurrent", state_visibility="snapshot"
    )
    (
        build_survey(state)
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
    print(run_forecasts().render_markdown())
