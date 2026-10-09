"""Read-only checks immediately before a Prolific publication request."""

import math

from .exceptions import CoopValueError


def _credits(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoopValueError(f"{label} must be a finite nonnegative number.")
    if not math.isfinite(value) or value < 0:
        raise CoopValueError(f"{label} must be a finite nonnegative number.")
    return value


def preflight(coop, human_survey_uuid, study_id, *, required_questions=None,
              expected_survey=None, required_credits=None):
    from ..surveys import Survey

    required_questions = [] if required_questions is None else required_questions
    if (not isinstance(required_questions, (list, tuple))
            or any(not isinstance(name, str) or not name.strip() for name in required_questions)):
        raise CoopValueError("required_questions must be a list of nonempty question names.")
    if expected_survey is not None and not isinstance(expected_survey, Survey):
        raise CoopValueError("expected_survey must be a Survey.")
    if required_credits is not None:
        _credits(required_credits, "Required credits")

    study = coop.get_prolific_study(human_survey_uuid, study_id)
    human_survey = coop.get_human_survey(human_survey_uuid)
    survey_uuid = human_survey.get("survey_uuid")
    if not survey_uuid:
        raise CoopValueError("The deployed human survey has no linked survey UUID.")
    survey = coop.get(survey_uuid, expected_object_type="survey")
    if not isinstance(survey, Survey):
        raise CoopValueError("The deployed object is not a Survey.")
    names = [question.question_name for question in survey.questions]
    missing = sorted(set(required_questions) - set(names))
    blockers = []
    if study.get("study_id") != study_id:
        blockers.append("The returned study ID does not match the requested study.")
    if study.get("status") != "UNPUBLISHED":
        blockers.append("The Prolific study is not an unpublished draft.")
    if missing:
        blockers.append("Deployed survey is missing required questions: " + ", ".join(missing))
    if expected_survey is not None and survey.to_dict(False) != expected_survey.to_dict(False):
        blockers.append("The deployed survey differs from the expected Survey.")

    # Only a study on Expected Parrot's account has its recruitment charged in
    # credits; on the researcher's own key, Prolific bills them directly. A draft
    # keeps the key it was created on. Without one reported, assume Expected Parrot's.
    key_source = study.get("key_source") or "ep"
    on_ep_key = key_source == "ep"

    cost = coop.calculate_prolific_study_cost(
        participant_payment_cents=study["participant_payment_cents"],
        num_participants=study["num_participants"],
        estimated_completion_time_minutes=study["estimated_completion_time_minutes"],
    )
    quote = _credits(cost["cost_credits"], "Recruitment credits")
    recruitment = quote if on_ep_key else 0
    total = recruitment if required_credits is None else required_credits
    if cost["is_underpayment"]:
        blockers.append("Participant payment is below the supported minimum.")
    if total < recruitment:
        blockers.append("Required credits are below the current recruitment quote.")
    balance = _credits(coop.get_balance()["credits"], "Balance credits")
    if balance < total:
        blockers.append(f"Insufficient credits: need {total}, have {balance}.")
    return {
        "ready": not blockers, "blockers": blockers, "study": study,
        "human_survey_uuid": human_survey_uuid, "survey_uuid": survey_uuid,
        "question_names": names, "missing_questions": missing,
        "recruitment_credits": recruitment, "required_credits": total,
        "balance_credits": balance, "key_source": key_source,
        "cost_scope": "recruitment_only" if required_credits is None else "caller_supplied_total",
    }
