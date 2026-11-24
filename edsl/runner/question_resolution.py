"""Resolve a stored question the way its prompt resolved it.

An answer must be validated against the question the model actually saw: piped
options, matrix rows and prices filled in from prior answers or the scenario,
and options and rows in the order this interview shuffled them. Both the local
executor and Coop's worker validate through ``resolve_question_for_validation``
so the two cannot drift apart.
"""

from typing import Any, Optional

from .service import JobService


def _is_template(value: Any) -> bool:
    if isinstance(value, str):
        return "{{" in value
    if isinstance(value, list):
        return any(isinstance(item, str) and "{{" in item for item in value)
    return isinstance(value, dict) and "from" in value


def _as_prices(prices: Any) -> list:
    """Coerce resolved QuestionDemand prices to floats, as the prompt does."""
    if isinstance(prices, tuple):
        prices = list(prices)
    if not isinstance(prices, list):
        raise ValueError("QuestionDemand prices must resolve to a list of numbers.")
    try:
        return [float(price) for price in prices]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "QuestionDemand prices must resolve to a list of numbers."
        ) from exc


def resolve_question_data(
    question_data: dict,
    answer_dict: dict,
    scenario: Any,
    option_permutation: Optional[list] = None,
    item_randomization_seed: Optional[int] = None,
) -> dict:
    """Return question_data with templates resolved and per-interview order applied.

    Returns question_data itself when nothing needs resolving, else a copy.
    """
    resolved = dict(question_data)
    if option_permutation is not None:
        resolved["question_options"] = option_permutation

    if _is_template(resolved.get("question_options")):
        resolved["question_options"] = JobService._resolve_question_options(
            resolved["question_options"], answer_dict, scenario
        )

    # Matrix rows are shuffled per interview whether piped or static.
    if "question_items" in resolved and (
        _is_template(resolved["question_items"]) or resolved.get("randomize_items")
    ):
        resolved["question_items"] = JobService._resolve_question_items(
            resolved, answer_dict, scenario, item_randomization_seed
        )

    if _is_template(resolved.get("prices")):
        resolved["prices"] = _as_prices(
            JobService._resolve_question_options(
                resolved["prices"], answer_dict, scenario
            )
        )

    # min_value, max_value and any other templated string field.
    for key, value in question_data.items():
        if key in ("question_options", "question_items", "prices"):
            continue
        if isinstance(value, str) and "{{" in value:
            resolved[key] = JobService._resolve_template_string(
                value, answer_dict, scenario
            )

    return resolved if resolved != question_data else question_data


def _interview_order(interview_def: Any, question_name: str) -> tuple:
    """This interview's option permutation and row seed for the question."""
    permutations = getattr(interview_def, "question_option_permutations", None) or {}
    seeds = getattr(interview_def, "question_item_randomization_seeds", None) or {}
    return permutations.get(question_name), seeds.get(question_name)


def _needs_resolution(question_data: dict, option_permutation: Any) -> bool:
    if option_permutation is not None:
        return True
    if question_data.get("randomize_items") and "question_items" in question_data:
        return True
    return any(_is_template(value) for value in question_data.values())


def resolve_question_for_validation(
    job_service: JobService, job_id: str, interview_id: str, question_data: dict
) -> dict:
    """Resolve a stored question for one interview before validating its answer."""
    interview_def = job_service._interviews.get_definition(job_id, interview_id)
    option_permutation, item_seed = _interview_order(
        interview_def, question_data.get("question_name")
    )
    if not _needs_resolution(question_data, option_permutation):
        return question_data

    answer_dict: dict = {}
    scenario = None
    if _is_template(option_permutation) or any(
        _is_template(value) for value in question_data.values()
    ):
        answers = job_service._answers.get_all_for_interview(job_id, interview_id)
        answer_dict = {a.question_name: a.answer for a in answers}
        if interview_def:
            scenario = job_service._jobs.get_scenario(job_id, interview_def.scenario_id)

    return resolve_question_data(
        question_data,
        answer_dict,
        scenario,
        option_permutation=option_permutation,
        item_randomization_seed=item_seed,
    )
