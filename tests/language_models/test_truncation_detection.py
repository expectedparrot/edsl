from edsl.language_models.raw_response_handler import (
    add_truncation_flag,
    response_was_truncated,
)
from edsl.results.result_transformer import RawModelResponseDict


def test_truncation_detection_normalizes_provider_stop_reasons():
    assert response_was_truncated(
        {"choices": [{"finish_reason": "length"}]}
    )
    assert response_was_truncated({"stop_reason": "max_tokens"})
    assert response_was_truncated(
        {"candidates": [{"finishReason": "MAX_TOKENS"}]}
    )
    assert response_was_truncated({"stopReason": "max_tokens"})
    assert response_was_truncated(
        {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}
    )


def test_truncation_detection_uses_output_usage_when_finish_reason_is_missing():
    assert response_was_truncated(
        {"usage": {"completion_tokens": 4096}}, max_tokens=4096
    )
    assert not response_was_truncated(
        {"usage": {"completion_tokens": 100}}, max_tokens=4096
    )


def test_flag_is_added_without_mutating_provider_response():
    response = {"choices": [{"finish_reason": "length"}]}
    augmented = add_truncation_flag(response, max_tokens=4096)

    assert augmented["truncated"] is True
    assert "truncated" not in response


def test_non_limit_incomplete_response_is_not_marked_truncated():
    response = {
        "status": "incomplete",
        "incomplete_details": {"reason": "content_filter"},
    }
    assert add_truncation_flag(response)["truncated"] is False


def test_truncation_flag_is_available_in_question_level_result_data():
    component = RawModelResponseDict(
        {
            "feedback_raw_model_response": {"truncated": True},
            "feedback_truncated": True,
            "truncated": True,
        }
    )
    assert component.generate_by_question_dict()["feedback"]["truncated"] is True
