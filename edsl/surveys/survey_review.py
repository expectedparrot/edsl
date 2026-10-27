"""Create visual review instruments from EDSL surveys."""

from __future__ import annotations

from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Iterable, Sequence

if TYPE_CHECKING:
    from ..scenarios import Scenario
    from .survey import Survey


def render_review_question_html(question, index: int, total: int) -> str:
    """Render one question as a self-contained HTML review card."""
    question_html = question.html()
    question_type = escape(type(question).__name__)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 32px; background: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1e293b;
    }}
    .review-card {{
      width: 560px; padding: 28px 32px; border: 1px solid #e2e8f0;
      border-radius: 12px; background: #fff;
      box-shadow: 0 1px 3px rgba(0, 0, 0, .06);
    }}
    .review-header {{
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 20px; padding-bottom: 14px; border-bottom: 1px solid #f1f5f9;
    }}
    .review-position {{
      color: #4f46e5; font-size: 12px; font-weight: 600;
      letter-spacing: .5px; text-transform: uppercase;
    }}
    .review-type {{
      padding: 3px 10px; border-radius: 12px; background: #f1f5f9;
      color: #64748b; font-size: 11px;
    }}
    .survey_question .question_text {{
      margin: 0 0 22px; font-size: 17px; font-weight: 500; line-height: 1.5;
    }}
    .survey_question label {{ line-height: 1.4; }}
    .survey_question input, .survey_question textarea, .survey_question select {{
      max-width: 100%;
    }}
  </style>
</head>
<body>
  <main class="review-card">
    <header class="review-header">
      <span class="review-position">Question {index + 1} of {total}</span>
      <span class="review-type">{question_type}</span>
    </header>
    {question_html}
  </main>
</body>
</html>"""


def capture_review_screenshots(
    survey: "Survey", output_dir: str | Path
) -> list[Path]:
    """Capture a PNG card for every question in *survey* using Playwright."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ImportError(
            "Creating review screenshots requires Playwright. Install it with "
            "`pip install playwright`, then run `playwright install chromium`, or "
            "pass screenshot_paths to create_review_survey()."
        ) from exc

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    total = len(survey.questions)

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:
            raise RuntimeError(
                "Playwright could not launch Chromium. Run "
                "`playwright install chromium`, or pass screenshot_paths to "
                "create_review_survey()."
            ) from exc
        try:
            page = browser.new_page(viewport={"width": 700, "height": 600})
            for index, question in enumerate(survey.questions):
                page.set_content(render_review_question_html(question, index, total))
                path = destination / f"question_{index}.png"
                page.locator(".review-card").screenshot(path=str(path))
                paths.append(path)
        finally:
            browser.close()
    return paths


def _validate_screenshot_paths(
    screenshot_paths: Iterable[str | Path], expected: int
) -> list[Path]:
    paths = [Path(path) for path in screenshot_paths]
    if len(paths) != expected:
        raise ValueError(
            f"Expected {expected} screenshot paths, received {len(paths)}."
        )
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Review screenshot(s) not found: {', '.join(missing)}")
    return paths


def create_review_survey(
    source_survey: "Survey",
    *,
    screenshot_paths: Sequence[str | Path] | None = None,
    output_dir: str | Path | None = None,
    reviewer_question_text: str = (
        "What is your name? (Your name will be attached to your review comments.)"
    ),
    reviewer_question_name: str = "reviewer_name",
    approval_options: Sequence[str] = ("Looks good", "Has an issue"),
    review_question_text: str | None = None,
    feedback_question_text: str | None = None,
    question_name_prefix: str = "review",
    screenshot_key_prefix: str = "review_screenshot",
) -> tuple["Survey", "Scenario"]:
    """Build a visual, question-by-question review survey.

    The returned scenario contains each screenshot as a ``FileStore``. It should be
    supplied when running or humanizing the returned survey. Set
    ``reviewer_question_text=None`` to omit the reviewer identity question. Custom
    question text may use ``{question_name}``, ``{question_number}``, and
    ``{screenshot}`` placeholders.
    """
    if not source_survey.questions:
        raise ValueError("Cannot create a review survey from an empty survey.")
    options = list(approval_options)
    if len(options) != 2 or len(set(options)) != 2:
        raise ValueError("approval_options must contain exactly two distinct values.")
    if not reviewer_question_name or not question_name_prefix or not screenshot_key_prefix:
        raise ValueError("Question names and prefixes must not be empty.")

    review_text = review_question_text or (
        "Review source question '{question_name}'. Does it look good as-is, or "
        "does it have an issue?\n\n{screenshot}"
    )
    feedback_text = feedback_question_text or (
        "Describe the specific issue and suggest how to fix it.\n\n{screenshot}"
    )

    if screenshot_paths is None:
        if output_dir is None:
            with TemporaryDirectory(prefix="edsl-survey-review-") as temporary_dir:
                paths = capture_review_screenshots(source_survey, temporary_dir)
                return _assemble_review_survey(
                    source_survey,
                    paths,
                    reviewer_question_text,
                    reviewer_question_name,
                    options,
                    review_text,
                    feedback_text,
                    question_name_prefix,
                    screenshot_key_prefix,
                )
        paths = capture_review_screenshots(source_survey, output_dir)
    else:
        paths = _validate_screenshot_paths(
            screenshot_paths, len(source_survey.questions)
        )

    return _assemble_review_survey(
        source_survey,
        paths,
        reviewer_question_text,
        reviewer_question_name,
        options,
        review_text,
        feedback_text,
        question_name_prefix,
        screenshot_key_prefix,
    )


def _assemble_review_survey(
    source_survey: "Survey",
    screenshot_paths: Sequence[Path],
    reviewer_question_text: str | None,
    reviewer_question_name: str,
    approval_options: list[str],
    review_question_text: str,
    feedback_question_text: str,
    question_name_prefix: str,
    screenshot_key_prefix: str,
):
    from ..questions import QuestionFreeText, QuestionMultipleChoice
    from ..scenarios import FileStore, Scenario
    from .survey import Survey

    questions = []
    if reviewer_question_text is not None:
        questions.append(
            QuestionFreeText(
                question_name=reviewer_question_name,
                question_text=reviewer_question_text,
            )
        )
    scenario_data = {}
    approved = approval_options[0]

    for index, (source_question, path) in enumerate(
        zip(source_survey.questions, screenshot_paths)
    ):
        screenshot_key = f"{screenshot_key_prefix}_{index}"
        scenario_data[screenshot_key] = FileStore(str(path))
        source_name = source_question.question_name
        format_values = {
            "question_name": source_name,
            "question_number": index + 1,
            "screenshot": f"{{{{ {screenshot_key} }}}}",
        }
        questions.extend(
            [
                QuestionMultipleChoice(
                    question_name=f"{question_name_prefix}_{index}",
                    question_text=review_question_text.format(**format_values),
                    question_options=approval_options,
                ),
                QuestionFreeText(
                    question_name=f"{question_name_prefix}_feedback_{index}",
                    question_text=feedback_question_text.format(**format_values),
                ),
            ]
        )

    review_survey = Survey(questions)
    for index in range(len(source_survey.questions)):
        review_survey.add_skip_rule(
            f"{question_name_prefix}_feedback_{index}",
            f"{{{{ {question_name_prefix}_{index}.answer }}}} == {approved!r}",
        )
    return review_survey, Scenario(scenario_data)
