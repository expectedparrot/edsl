"""Run concurrent abstract screening and a separate adjudication phase."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionFreeText,
    QuestionMultipleChoice,
    Survey,
)
from edsl.sharedstate import SharedState, SharedStateMap, current

from examples.shared_state_dsl.shared_review_screening import DECISIONS, SPEC


HERE = Path(__file__).resolve().parent


def build_workflow():
    states = SharedStateMap(
        SharedState(review=SPEC), state_id=f"systematic-review-{uuid4()}"
    )
    review = states.by("school-attendance-review").review

    decision = QuestionMultipleChoice(
        question_name="screening_decision",
        question_text=(
            "Your authoritative assignment is shown below. Screen only this abstract. "
            "Include randomized or controlled quasi-experimental evaluations of an "
            "intervention intended to improve student attendance. Exclude qualitative "
            "studies and studies without student attendance outcomes. Choose uncertain "
            "when the design cannot be determined.\n\nYour assignment:\n"
            "{{ shared_state.review.my_claim }}"
        ),
        question_options=list(DECISIONS),
    )
    reason = QuestionFreeText(
        question_name="screening_reason",
        question_text=(
            "You selected {{ screening_decision.answer }} for this assignment: "
            "{{ shared_state.review.my_claim }}. Briefly justify the decision "
            "using concrete details from that abstract; do not assume facts not stated."
        ),
    )
    screening_survey = Survey([
        review.claim(reviewer=current.agent.name),
        review.read(),
        decision,
        reason,
        review.review(
            reviewer=current.agent.name,
            decision=decision.answer,
            reason=reason.answer,
        ),
    ])
    reviewers = AgentList([
        Agent(name=f"Reviewer {index}", traits={"carefulness": level})
        for index, level in enumerate(
            ("strict", "balanced", "inclusive", "strict", "balanced", "inclusive"),
            start=1,
        )
    ])
    screening_schedule = InterviewSchedule.rounds(
        count=1, within_round="concurrent", state_visibility="live"
    )

    final_decision = QuestionMultipleChoice(
        question_name="final_decision",
        question_text=(
            "Adjudicate paper {{ agent.paper_id }} under the same inclusion rule. "
            "Use only review records whose paper field is {{ agent.paper_id }}. If the "
            "two reviewers agree, preserve that agreement; do not invent disagreement, "
            "rebuttals, or additional reviewers. Relevant reviews: "
            "{{ shared_state.review.relevant_reviews }}"
        ),
        question_options=list(DECISIONS),
    )
    final_reason = QuestionFreeText(
        question_name="final_reason",
        question_text=(
            "The relevant reviews are {{ shared_state.review.relevant_reviews }}. "
            "Explain your {{ final_decision.answer }} disposition using only these "
            "records. If they agree, explicitly say there was no disagreement."
        ),
    )
    adjudication_survey = Survey([
        review.read(),
        final_decision,
        final_reason,
        review.adjudicate(
            paper=current.agent.paper_id,
            adjudicator=current.agent.name,
            decision=final_decision.answer,
            reason=final_reason.answer,
        ),
    ])
    adjudicators = AgentList([
        Agent(name=f"Adjudicator {paper}", traits={"paper_id": paper})
        for paper in ("P1", "P2", "P3")
    ])
    adjudication_schedule = InterviewSchedule.rounds(
        count=1, within_round="concurrent", state_visibility="snapshot"
    )
    return (
        screening_survey,
        reviewers,
        screening_schedule,
        adjudication_survey,
        adjudicators,
        adjudication_schedule,
    )


def main() -> None:
    (
        screening_survey,
        reviewers,
        screening_schedule,
        adjudication_survey,
        adjudicators,
        adjudication_schedule,
    ) = build_workflow()
    model = Model(
        "gemini-2.5-flash",
        service_name="google",
        maxOutputTokens=2_048,
        thinking_budget=0,
    )
    run_options = {
        "cache": False,
        "disable_remote_cache": True,
        "disable_remote_inference": True,
        "max_concurrency": 6,
        "stop_on_exceptions": True,
    }
    screening = screening_survey.by(reviewers).by(model).run(
        interview_schedule=screening_schedule, **run_options
    )
    adjudication = adjudication_survey.by(adjudicators).by(model).run(
        interview_schedule=adjudication_schedule, **run_options
    )
    screening.save(HERE / "systematic_review_screening_results.ep", allow_new_commit=True)
    adjudication.save(
        HERE / "systematic_review_adjudication_results.ep", allow_new_commit=True
    )
    artifact = {
        "screening_answers": [result.answer for result in screening],
        "adjudication_answers": [result.answer for result in adjudication],
        "screening_state": screening.shared_state,
        "adjudication_state": adjudication.shared_state,
    }
    (HERE / "systematic_review_results.json").write_text(
        json.dumps(artifact, indent=2, default=str) + "\n"
    )
    print(
        json.dumps(
            {
                "screening_rows": len(screening),
                "adjudication_rows": len(adjudication),
                "artifact": str(HERE / "systematic_review_results.json"),
            }
        )
    )


if __name__ == "__main__":
    main()
