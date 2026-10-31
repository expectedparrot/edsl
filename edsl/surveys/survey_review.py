"""Create visual review instruments from EDSL surveys."""

from __future__ import annotations

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from html import escape
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Iterable, Mapping, Optional, Sequence

if TYPE_CHECKING:
    from ..scenarios import Scenario
    from .survey import Survey


# Matches the leading variable name of a Jinja expression, e.g. ``product`` in
# ``{{ product }}`` or the root ``q0`` in ``{{ q0.answer }}``. Used only to warn
# about placeholders a static review screenshot cannot fill, never to render.
_JINJA_VAR = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)")


def _scenario_as_dict(scenario: "Scenario | Mapping | None") -> dict:
    """Coerce a Scenario/mapping to a plain dict (empty dict when None)."""
    if not scenario:
        return {}
    return dict(scenario)


def _question_template_strings(question) -> list[str]:
    """The question's author-facing templated strings (text + any options)."""
    parts = [str(getattr(question, "question_text", "") or "")]
    options = getattr(question, "question_options", None)
    if isinstance(options, (list, tuple)):
        parts.extend(str(option) for option in options)
    return parts


def _unresolved_placeholders(question, scenario: dict) -> list[str]:
    """Root variable names referenced by the question but absent from *scenario*.

    These are the placeholders that ``question.html()`` would silently render as
    empty, so the review card flags them instead of dropping them unnoticed.
    """
    provided = set(scenario)
    unresolved: list[str] = []
    for templated in _question_template_strings(question):
        for name in _JINJA_VAR.findall(templated):
            if name not in provided and name not in unresolved:
                unresolved.append(name)
    return unresolved


def render_review_question_html(
    question, index: int, total: int, scenario: "Scenario | Mapping | None" = None
) -> str:
    """Render one question as a self-contained HTML review card.

    ``scenario`` supplies values for templated placeholders (e.g. ``{{ product }}``)
    so the screenshot matches what respondents will see. Any placeholder left
    unfilled is listed in a visible warning banner rather than silently dropped.
    """
    scenario_dict = _scenario_as_dict(scenario)
    question_html = (
        question.html(scenario=scenario_dict) if scenario_dict else question.html()
    )
    question_type = escape(type(question).__name__)

    unresolved = _unresolved_placeholders(question, scenario_dict)
    warning_html = ""
    if unresolved:
        names = ", ".join(escape(name) for name in unresolved)
        warning_html = (
            '<div class="review-warning" role="alert">'
            f"⚠ Unfilled placeholder(s): <strong>{names}</strong>. "
            "This screenshot may not match what respondents see — pass "
            "<code>scenario=</code> to <code>create_review_survey()</code> to fill them."
            "</div>"
        )
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
    .review-warning {{
      margin: 0 0 18px; padding: 10px 14px; border-radius: 8px;
      background: #fef3c7; border: 1px solid #f59e0b; color: #92400e;
      font-size: 13px; line-height: 1.45;
    }}
    .review-warning code {{
      background: #fde68a; padding: 1px 4px; border-radius: 4px;
      font-family: ui-monospace, Menlo, monospace; font-size: 12px;
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
    {warning_html}
    {question_html}
  </main>
</body>
</html>"""


def _capture_review_screenshots_sync(
    survey: "Survey",
    output_dir: str | Path,
    scenario: "Scenario | Mapping | None" = None,
) -> list[Path]:
    """Capture a PNG card per question with Playwright's synchronous API.

    Must run with no asyncio event loop active in the calling thread. The public
    :func:`capture_review_screenshots` wrapper enforces that.
    """
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
                page.set_content(
                    render_review_question_html(question, index, total, scenario)
                )
                path = destination / f"question_{index}.png"
                page.locator(".review-card").screenshot(path=str(path))
                paths.append(path)
        finally:
            browser.close()
    return paths


def capture_review_screenshots(
    survey: "Survey",
    output_dir: str | Path,
    scenario: "Scenario | Mapping | None" = None,
) -> list[Path]:
    """Capture a PNG card for every question in *survey* using Playwright.

    Playwright's synchronous API cannot run inside a live asyncio event loop
    (e.g. a Jupyter/IPython kernel), where it raises
    ``"... Sync API inside the asyncio loop"``. When a running loop is detected
    the capture is dispatched to a worker thread, which has no running loop, so
    the default path works in notebooks without any caller change.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop_running = False
    else:
        loop_running = True

    if loop_running:
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                _capture_review_screenshots_sync, survey, output_dir, scenario
            ).result()
    return _capture_review_screenshots_sync(survey, output_dir, scenario)


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
    scenario: "Scenario | Mapping | None" = None,
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

    ``scenario`` supplies values for templated placeholders in the source
    questions (e.g. ``{{ product }}``) so each screenshot matches what
    respondents will see. Placeholders left unfilled are flagged on the card
    rather than silently rendered empty. It is ignored when ``screenshot_paths``
    is given, since those images are already rendered.
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
                paths = capture_review_screenshots(
                    source_survey, temporary_dir, scenario
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
        paths = capture_review_screenshots(source_survey, output_dir, scenario)
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
