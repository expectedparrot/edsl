"""Regression tests for dynamic question options in the current runner."""

from edsl.runner.service import JobService


def test_resolves_prior_answer_inside_mixed_option_list():
    options = ["cherry", "blackberry", "{{ favorite.answer }}"]

    resolved = JobService._resolve_question_options(
        options,
        {"favorite": "Other: mango"},
        scenario=None,
    )

    assert resolved == ["cherry", "blackberry", "Other: mango"]
