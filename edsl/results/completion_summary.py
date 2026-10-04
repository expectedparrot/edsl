"""Completion counts based on answers and evidence, not merely row count."""

from ..language_models.response_metadata import response_metadata


def completion_summary(results) -> dict:
    counts = {
        "planned_interview_rows": getattr(results, "_total_results", None),
        "row_count": len(results),
        "provider_calls_attempted": 0,
        "questions_with_unknown_call_count": 0,
        "answers_produced": 0,
        "answers_validated": 0,
        "answered_interviews": 0,
        "truncated_responses": 0,
        "failed_interviews": 0,
        "placeholder_rows": 0,
        "unsuccessful_interviews": 0,
    }
    for result in results:
        answers = result.get("answer") or {}
        raw = result.get("raw_model_response") or {}
        validation = result.get("validated_dict") or {}
        failed = False
        answered = any(value is not None for value in answers.values())
        counts["answered_interviews"] += int(answered)
        evidence = False
        questions = set(answers)
        questions.update(
            key.removesuffix("_response_metadata")
            for key in raw
            if key.endswith("_response_metadata")
        )
        if not questions:
            questions.update(getattr(results.survey, "question_names", []))
        for name in questions:
            provider_response = raw.get(f"{name}_raw_model_response")
            metadata = {
                **response_metadata(provider_response),
                **(raw.get(f"{name}_response_metadata") or {}),
            }
            calls = metadata.get("provider_calls_attempted")
            if calls is None:
                counts["questions_with_unknown_call_count"] += 1
            else:
                counts["provider_calls_attempted"] += calls
            present = answers.get(name) is not None
            validated = validation.get(f"{name}_validated")
            counts["answers_produced"] += int(present)
            counts["answers_validated"] += int(present and validated is True)
            counts["truncated_responses"] += int(bool(metadata.get("truncated")))
            failed = failed or bool(metadata.get("failure")) or validated is False
            evidence = evidence or bool(metadata) or provider_response is not None
        counts["failed_interviews"] += int(failed)
        placeholder = not answered and not evidence and not result.get("prompt")
        counts["placeholder_rows"] += int(placeholder)
        counts["unsuccessful_interviews"] += int(failed or placeholder)
    # Report the known subtotal separately when old artifacts lack call evidence.
    counts["known_provider_calls_attempted"] = counts["provider_calls_attempted"]
    if counts["questions_with_unknown_call_count"]:
        counts["provider_calls_attempted"] = None
    return counts
