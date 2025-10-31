from __future__ import annotations

from typing import Any


class AnswersCollector:
    @staticmethod
    def collect_interactively(app: Any) -> dict:
        if app.initial_survey is None:
            raise ValueError(
                "Cannot collect answers interactively without an initial_survey."
            )

        answers = None
        # Prefer Textual TUI if installed
        try:
            from ..surveys.textual_interactive_survey import run_textual_survey  # type: ignore

            answers = run_textual_survey(app.initial_survey, title=app.application_name)
        except Exception:
            # Fallback to existing Rich-based flow
            try:
                from ..surveys import InteractiveSurvey  # type: ignore

                answers = InteractiveSurvey(app.initial_survey).run()
            except Exception as e:
                raise e

        # Normalize file uploads to FileStore
        try:
            for question_name, answer in list(answers.items()):
                q = app.initial_survey[question_name]
                if q.question_type == "file_upload":
                    from ..scenarios import FileStore  # type: ignore

                    answers[question_name] = FileStore(path=answer)
        except Exception:
            # Best-effort normalization; keep raw answers if anything goes wrong
            pass

        return answers or {}
