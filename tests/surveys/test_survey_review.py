import base64

import pytest

from edsl import Survey
from edsl.surveys.survey_review import render_review_question_html


_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _screenshots(tmp_path, count):
    paths = []
    for index in range(count):
        path = tmp_path / f"question_{index}.png"
        path.write_bytes(_ONE_PIXEL_PNG)
        paths.append(path)
    return paths


def test_create_review_survey_from_existing_screenshots(tmp_path):
    source = Survey.example()
    review, scenario = source.create_review_survey(
        screenshot_paths=_screenshots(tmp_path, len(source.questions))
    )

    assert review.question_names[0] == "reviewer_name"
    assert len(review.questions) == 1 + 2 * len(source.questions)
    assert set(scenario.keys()) == {
        f"review_screenshot_{index}" for index in range(len(source.questions))
    }
    for index in range(len(source.questions)):
        assert (
            f"{{{{ review_screenshot_{index} }}}}"
            in review.questions[1 + 2 * index].question_text
        )
        assert (
            f"{{{{ review_screenshot_{index} }}}}"
            in review.questions[2 + 2 * index].question_text
        )


def test_create_review_survey_validates_screenshot_count(tmp_path):
    with pytest.raises(ValueError, match="Expected 3 screenshot paths"):
        Survey.example().create_review_survey(screenshot_paths=_screenshots(tmp_path, 2))


def test_create_review_survey_rejects_empty_survey():
    with pytest.raises(ValueError, match="empty survey"):
        Survey([]).create_review_survey(screenshot_paths=[])


def test_create_review_survey_customizes_questions(tmp_path):
    source = Survey.example()
    review, scenario = source.create_review_survey(
        screenshot_paths=_screenshots(tmp_path, len(source.questions)),
        reviewer_question_text=None,
        approval_options=("Approve", "Revise"),
        review_question_text="Check #{question_number} ({question_name})\n{screenshot}",
        feedback_question_text="Propose a revision:\n{screenshot}",
        question_name_prefix="qa",
        screenshot_key_prefix="card",
    )

    assert len(review.questions) == 2 * len(source.questions)
    assert review.question_names[:2] == ["qa_0", "qa_feedback_0"]
    assert review.questions[0].question_options == ["Approve", "Revise"]
    assert "Check #1 (q0)" in review.questions[0].question_text
    assert set(scenario.keys()) == {"card_0", "card_1", "card_2"}


def test_render_review_question_html_uses_native_question_renderer():
    question = Survey.example().questions[0]
    html = render_review_question_html(question, 0, 3)
    assert "Question 1 of 3" in html
    assert question.question_text in html
    assert 'class="survey_question"' in html


# --- Fix: screenshots must not silently drop unresolved placeholders ---------


def test_render_flags_unresolved_placeholder_when_no_scenario():
    from edsl.questions import QuestionFreeText

    q = QuestionFreeText(
        question_name="pay",
        question_text="How much would you pay for {{ product }}?",
    )
    html = render_review_question_html(q, 0, 1)
    # The placeholder is named in a visible warning, not silently dropped.
    assert 'class="review-warning"' in html
    assert "product" in html


def test_render_resolves_placeholder_with_scenario_and_omits_warning():
    from edsl.questions import QuestionFreeText

    q = QuestionFreeText(
        question_name="pay",
        question_text="How much would you pay for {{ product }}?",
    )
    html = render_review_question_html(q, 0, 1, scenario={"product": "a bicycle"})
    assert "a bicycle" in html
    # Fully resolved -> no warning banner.
    assert 'class="review-warning"' not in html


def test_render_without_placeholders_has_no_warning():
    question = Survey.example().questions[0]
    html = render_review_question_html(question, 0, 3)
    assert 'class="review-warning"' not in html


# --- Fix: auto-capture must work when an asyncio event loop is running --------


def test_capture_runs_in_worker_thread_under_running_loop(monkeypatch):
    import asyncio
    import threading

    from edsl.surveys import survey_review

    recorded = {}

    def fake_sync(survey, output_dir, scenario=None):
        recorded["thread"] = threading.current_thread().name
        recorded["is_main"] = threading.current_thread() is threading.main_thread()
        return ["sentinel"]

    monkeypatch.setattr(survey_review, "_capture_review_screenshots_sync", fake_sync)

    async def run_inside_loop():
        # Mirrors a Jupyter cell: a loop is already running in this thread.
        return survey_review.capture_review_screenshots(Survey.example(), "/tmp/unused")

    result = asyncio.run(run_inside_loop())
    assert result == ["sentinel"]
    # The sync Playwright work was pushed off the loop thread.
    assert recorded["is_main"] is False


def test_capture_runs_directly_without_running_loop(monkeypatch):
    import threading

    from edsl.surveys import survey_review

    recorded = {}

    def fake_sync(survey, output_dir, scenario=None):
        recorded["is_main"] = threading.current_thread() is threading.main_thread()
        return ["sentinel"]

    monkeypatch.setattr(survey_review, "_capture_review_screenshots_sync", fake_sync)
    result = survey_review.capture_review_screenshots(Survey.example(), "/tmp/unused")
    assert result == ["sentinel"]
    # No running loop -> no thread hop needed.
    assert recorded["is_main"] is True
