"""Distributed incident investigation followed by commander synthesis."""

from pathlib import Path

from edsl import Agent, AgentList, Model, QuestionFreeText, Survey
from edsl.sharedstate import FileStateStore, SharedLog, SharedState, SharedWorkPool


TASKS = [
    {
        "id": "metrics",
        "area": "service metrics",
        "evidence": "Latency rose immediately after API release 4.8; CPU stayed normal.",
    },
    {
        "id": "deploy",
        "area": "deployment history",
        "evidence": "Release 4.8 changed retry defaults from 2 attempts to 8.",
    },
    {
        "id": "database",
        "area": "database behavior",
        "evidence": "Write locks spiked, but slow-query volume did not change.",
    },
    {
        "id": "traffic",
        "area": "traffic and dependencies",
        "evidence": "A payment dependency began returning transient 503s at 09:02.",
    },
]


def responders():
    specs = [
        ("Ari", "site reliability engineer"),
        ("Bo", "backend engineer"),
        ("Cy", "database specialist"),
        ("Dee", "dependency operations lead"),
    ]
    return AgentList([Agent(name=name, traits={"role": role}) for name, role in specs])


def investigation_survey(state):
    report = QuestionFreeText(
        question_name="investigation",
        question_text=(
            "You are {{ agent.name }}, the {{ agent.role }}, responding to an outage. "
            "Users see intermittent checkout timeouts.\n\n"
            "Your atomically assigned investigation: {{ shared_state.work.claimed }}\n"
            "Evidence posted so far: {{ shared_state.evidence.entries }}\n\n"
            "Analyze only your assigned evidence. Report observation, likely causal "
            "implication, confidence, and one recommended action. Clearly separate "
            "observed facts from inference."
        ),
    )
    return Survey(
        [
            state.work.claim_before(report),
            report,
            state.work.complete(report),
            state.evidence.append(
                sender="{{ agent.name }}",
                kind="investigation",
                report=report,
            ),
        ]
    )


def commander_survey(state):
    resolution = QuestionFreeText(
        question_name="resolution",
        question_text=(
            "You are incident commander Morgan. Checkout has intermittent timeouts.\n\n"
            "All investigation reports: {{ shared_state.evidence.entries }}\n\n"
            "Synthesize a root-cause hypothesis, immediate mitigation, verification "
            "step, and confidence. Call out any unresolved uncertainty."
        ),
    )
    return Survey(
        [
            resolution,
            state.evidence.append(
                sender="Morgan", kind="commander_resolution", report=resolution
            ),
        ]
    )


def run_simulation(
    log_path: str | Path = "incident-response.jsonl",
    model_name="gemini-2.5-flash",
):
    state = SharedState(
        "checkout-incident",
        FileStateStore(log_path),
        work=SharedWorkPool(TASKS),
        evidence=SharedLog(),
    )
    model = Model(model_name)
    (
        investigation_survey(state)
        .by(responders())
        .by(model)
        .run(
            interview_schedule="concurrent",
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    (
        commander_survey(state)
        .by(Agent(name="Morgan", traits={"role": "incident commander"}))
        .by(model)
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
    print(run_simulation().render_markdown())
