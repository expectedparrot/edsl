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
