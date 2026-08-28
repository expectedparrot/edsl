"""Anonymous Delphi forecasting with facilitator feedback and convergence stopping."""

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
from edsl.sharedstate import FileStateStore, SharedDelphiPanel, SharedLog, SharedState


QUESTION = (
    "What is the probability that the enterprise permissions product will launch "
    "by September 30 with all committed security and compliance requirements?"
)
MAX_ROUNDS = 5


def experts() -> AgentList:
    specs = [
        ("Amara", "program director", 68, "cross-team milestones and dependency risk"),
        (
            "Ben",
            "staff engineer",
            46,
            "technical scope, integration work, and reliability",
        ),
        (
            "Carmen",
            "enterprise sales lead",
            80,
            "customer commitments and commercial urgency",
        ),
        (
            "Dev",
            "security lead",
            37,
            "threat modeling, audit findings, and approval gates",
        ),
        (
            "Elise",
            "finance partner",
            56,
            "staffing capacity, historical delivery rates, and cost risk",
        ),
        (
            "Farid",
            "customer-success lead",
            64,
            "implementation readiness and customer acceptance",
        ),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "role": role,
                    "private_estimate": estimate,
                    "evidence_lens": evidence_lens,
                },
            )
            for name, role, estimate, evidence_lens in specs
        ]
    )


def expert_survey(state: SharedState, round_number: int) -> Survey:
    estimate = QuestionNumerical(
        question_name="delphi_estimate",
        question_text=(
            f"Delphi round {round_number} of at most {MAX_ROUNDS}. You are an anonymous "
            "{{ agent.role }} focused on {{ agent.evidence_lens }}.\n\n"
            f"Forecast question: {QUESTION}\n\nYour private starting evidence implies "
            "{{ agent.private_estimate }}%. Prior-round anonymous panel statistics and "
            "rationales:\n{{ shared_state.panel }}\n\nFacilitator summaries from "
            "completed rounds:\n{{ shared_state.feedback.entries }}\n\nGive your independent "
            "best estimate from 0 to 100. Revise only when the anonymous evidence is "
            "persuasive; do not move merely to agree with the group."
        ),
        min_value=0,
        max_value=100,
    )
    confidence = QuestionNumerical(
        question_name="delphi_confidence",
        question_text=(
            "You estimated {{ delphi_estimate.answer }}%. Rate confidence from 0 to "
            "100 based on evidence quality, not closeness to consensus."
        ),
        min_value=0,
        max_value=100,
    )
    rationale = QuestionFreeText(
        question_name="delphi_rationale",
        question_text=(
            "Explain the two most decision-relevant reasons for your estimate and one "
            "fact that would materially change it. Do not identify yourself. At most "
            "85 words."
        ),
    )
    return Survey(
        [
            estimate,
            confidence,
            rationale,
            state.panel.submit(
                estimate,
                confidence,
                rationale,
                round_number=round_number,
            ),
        ]
    )


def facilitator_survey(state: SharedState, round_number: int) -> Survey:
    feedback = QuestionFreeText(
        question_name="anonymous_feedback",
        question_text=(
            f"You are the neutral facilitator after Delphi round {round_number}. The "
            "panel view contains no expert names. Synthesize rather than advocate.\n\n"
            f"Forecast question: {QUESTION}\n\nAnonymous panel:\n"
            "{{ shared_state.panel }}\n\nReturn at most 140 words with four labeled "
            "sections: CONSENSUS, HIGHER, LOWER, and UNRESOLVED. Preserve minority "
            "arguments and never identify or infer an expert."
        ),
    )
    return Survey(
        [feedback, state.feedback.append(round=round_number, feedback=feedback)]
    )


def round_complete(state: SharedState, round_number: int) -> bool:
    return any(
        summary["round"] == round_number and summary["complete"]
        for summary in state.read().state["panel"]["rounds"]
    )


def feedback_complete(state: SharedState, round_number: int) -> bool:
    return any(
        entry["round"] == round_number
        for entry in state.read().state["feedback"]["entries"]
    )


def final_report(state: SharedState) -> dict:
    panel = state.read().state["panel"]
    rounds = [item for item in panel["rounds"] if item["complete"]]
    first, final = rounds[0], rounds[-1]
    return {
        "rounds_completed": len(rounds),
        "converged": panel["converged"],
        "initial_median": first["median"],
        "final_median": final["median"],
        "initial_range": first["range"],
        "final_range": final["range"],
        "final_weighted_mean": final["confidence_weighted_mean"],
        "final_anonymous_estimates": sorted(
            item["estimate"] for item in final["anonymous_rationales"]
        ),
    }


def run_delphi(
    log_path: str | Path = "delphi-enterprise-launch.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, dict]:
    panelists = experts()
    state = SharedState(
        "enterprise-launch-delphi",
        FileStateStore(log_path),
        panel=SharedDelphiPanel(
            panel_size=len(panelists),
            range_threshold=18,
            median_shift_threshold=4,
            min_rounds=2,
        ),
        feedback=SharedLog(),
    )
    model = Model(model_name)
    options = {
        "disable_remote_inference": True,
        "disable_remote_cache": True,
        "cache": False,
        "stop_on_exceptions": True,
    }
    facilitator = Agent(name="Anonymous Delphi facilitator")
    for round_number in range(1, MAX_ROUNDS + 1):
        if not round_complete(state, round_number):
            expert_survey(state, round_number).by(panelists).by(model).run(
                interview_schedule=InterviewSchedule.rounds(
                    count=1,
                    within_round="concurrent",
                    state_visibility="snapshot",
                ),
                **options,
            )
        if not round_complete(state, round_number):
            raise RuntimeError(
                f"Delphi round {round_number} did not persist all responses"
            )
        if not feedback_complete(state, round_number):
            facilitator_survey(state, round_number).by(facilitator).by(model).run(
                **options
            )
        if not feedback_complete(state, round_number):
            raise RuntimeError(
                f"Delphi round {round_number} facilitator feedback was not persisted"
            )
        if state.read().state["panel"]["converged"]:
            break
    report = final_report(state)
    state.close()
    return state, report


if __name__ == "__main__":
    shared_state, report = run_delphi()
    print(shared_state.render_markdown())
    print(f"\nFinal Delphi report: {report}")
