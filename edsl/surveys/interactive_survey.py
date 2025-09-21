from __future__ import annotations
from typing import Any, Dict, Optional, Union


class InteractiveSurvey:
    """Run a `Survey` interactively in the terminal using Rich.

    This helper presents one item at a time (instructions and questions),
    respects survey rules/skip-logic via `Survey.next_question_with_instructions`,
    collects user input for questions, and returns a dictionary mapping
    `question_name` to the entered answer.

    Notes:
        - Only basic free-text entry is implemented. For other question types,
          the user's input is collected as a string. If a question has
          `question_options`, those are displayed for reference.
        - Internally, navigation uses an answers dict whose keys are of the form
          "<question_name>.answer" (as expected by rules). The returned mapping
          to the caller is simplified to `{question_name: answer}`.
        - Requires the `rich` package. If not available, an ImportError is raised
          on run().
    """

    def __init__(self, survey: "Survey", clear_between_items: bool = True) -> None:
        from .survey import Survey  # local import for type checking

        if not isinstance(survey, Survey):  # defensive but helpful for users
            raise TypeError("InteractiveSurvey expects a Survey instance")
        self.survey = survey
        self.clear_between_items = clear_between_items

        # Public result: question_name -> raw entered answer
        self.answers: Dict[str, Any] = {}

        # Internal dict used for rule evaluation: "q.answer" -> answer
        self._rule_answers: Dict[str, Any] = {}

    # Notebook detection and widget path
    def _in_notebook(self) -> bool:
        try:
            from IPython import get_ipython  # type: ignore

            ip = get_ipython()
            if ip is None:
                return False
            # ZMQInteractiveShell is used by Jupyter
            return ip.__class__.__name__ == "ZMQInteractiveShell"
        except Exception:
            return False

    def _can_use_widget(self) -> bool:
        if not self._in_notebook():
            return False
        try:
            # Verify widget infra is available
            from ..widgets.survey_widget import SurveyWidget  # noqa: F401
            from IPython.display import display  # noqa: F401

            return True
        except Exception:
            return False

    def _run_in_notebook_blocking(self) -> Dict[str, Any]:
        """Display anywidget SurveyWidget and block until completion, then return answers.

        Falls back to terminal mode on any error.
        """
        try:
            from ..widgets.survey_widget import SurveyWidget
            from IPython.display import display
            import asyncio

            widget = SurveyWidget(self.survey)
            display(widget)

            # Await completion using IPython's asyncio runner if available.
            from IPython import get_ipython  # type: ignore

            ip = get_ipython()
            runner = getattr(getattr(ip, "kernel", None), "_asyncio_runner", None)

            async def _wait_until_complete():
                # Wait until the widget reports completion, yielding control to the event loop.
                while not bool(getattr(widget, "is_complete", False)):
                    await asyncio.sleep(0.05)

            if runner is not None and hasattr(runner, "run"):
                # Run the coroutine in the kernel's event loop from sync code
                runner.run(_wait_until_complete())
            else:
                # As a fallback, try to use the current event loop directly if possible
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Cannot block properly without runner; raise to inform environment limitations
                        raise RuntimeError(
                            "Notebook detected but cannot block until widget completes (no IPython asyncio runner). "
                            "Please update ipykernel/JupyterLab or use the non-blocking widget and read answers later."
                        )
                    else:
                        loop.run_until_complete(_wait_until_complete())
                except Exception:
                    raise

            answers = dict(getattr(widget, "answers", {}))
            # Mirror internal bookkeeping used by terminal mode
            self.answers = answers
            self._rule_answers = {f"{k}.answer": v for k, v in answers.items()}
            return answers
        except KeyboardInterrupt:
            # Allow user to interrupt; return whatever answers collected so far
            return dict(getattr(self, "answers", {}))
        except Exception:
            # If anything goes wrong, fall back to terminal mode
            return self._run_in_terminal()

    # Terminal (Rich) path split into its own helper so we can fall back cleanly
    def _run_in_terminal(self) -> Dict[str, Any]:
        # Ensure we can import Rich only at runtime
        self._ensure_rich()
        console = self._get_console()

        current_item: Optional[Union["QuestionBase", "Instruction"]] = None

        while True:
            next_item = self.survey.next_question_with_instructions(current_item, self._rule_answers)

            # End of survey
            from .base import EndOfSurvey

            if next_item is EndOfSurvey:
                break

            # Instruction (has text but not question_name)
            if hasattr(next_item, "text") and not hasattr(next_item, "question_name"):
                self._print_instruction(console, next_item)
                current_item = next_item
                continue

            # Question
            if hasattr(next_item, "question_name"):
                answer = self._ask_question(console, next_item)
                qname = next_item.question_name

                # Record answers both for return value and for rule evaluation
                self.answers[qname] = answer
                self._rule_answers[f"{qname}.answer"] = answer

                current_item = next_item
                continue

            # If we get here, something unexpected was returned
            raise RuntimeError("Survey returned an unexpected item during interactive run")

        # Final clear and summary
        if self.clear_between_items:
            console.clear()
        if self.answers:
            from rich.panel import Panel
            from rich.table import Table

            table = Table(show_header=True, header_style="bold green")
            table.add_column("Question Name", style="cyan")
            table.add_column("Answer")
            for qn, ans in self.answers.items():
                table.add_row(qn, str(ans))
            console.print(Panel.fit(table, title="Survey Complete", border_style="green"))
            console.print("Press Enter to finish…", style="dim")
            try:
                console.input("")
            except KeyboardInterrupt:
                pass

        return self.answers

    def _ensure_rich(self):
        try:
            from rich.console import Console  # noqa: F401
            from rich.panel import Panel  # noqa: F401
            from rich.markdown import Markdown  # noqa: F401
        except Exception as e:
            raise ImportError(
                "InteractiveSurvey requires the 'rich' package. Install with: pip install rich"
            ) from e

    def _get_console(self):
        from rich.console import Console
        import sys

        return Console(file=sys.stdout)

    def _print_instruction(self, console, instruction) -> None:
        from rich.panel import Panel
        from rich.markdown import Markdown

        text = getattr(instruction, "text", "")
        if self.clear_between_items:
            console.clear()
        console.print(Panel.fit(Markdown(text or ""), title="Instruction", border_style="cyan"))
        console.print("Press Enter to continue…", style="dim")
        try:
            console.input("")
        except KeyboardInterrupt:
            raise SystemExit(0)

    def _ask_question(self, console, question: "QuestionBase") -> Any:
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        # Clear if desired, then render question
        if self.clear_between_items:
            console.clear()

        # Build a header panel with the question text
        question_text = getattr(question, "question_text", "")
        console.print(Panel.fit(question_text, title=f"{question.question_name}", border_style="magenta"))

        # If options exist, show them (and provide numeric selection UX)
        if getattr(question, "question_type", None) == "multiple_choice" and hasattr(question, "question_options") and getattr(question, "question_options"):
            options = list(getattr(question, "question_options"))
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("#", justify="right")
            table.add_column("Option", justify="left")
            for idx, option in enumerate(options, start=1):
                table.add_row(str(idx), str(option))
            console.print(table)

            use_code = bool(getattr(question, "use_code", False))
            console.print(
                "Type the option number or the option text exactly, then press Enter:",
                style="dim",
            )

            while True:
                try:
                    raw = console.input("")
                except KeyboardInterrupt:
                    raise SystemExit(0)

                raw_stripped = raw.strip()
                candidate = None

                # Try numeric selection (1-based display)
                if raw_stripped.isdigit():
                    idx = int(raw_stripped)
                    if 1 <= idx <= len(options):
                        zero_based = idx - 1
                        candidate = zero_based if use_code else options[zero_based]
                    else:
                        candidate = None

                # If not numeric or out-of-range, try to match text
                if candidate is None and raw_stripped:
                    # Exact match first
                    exact_matches = [opt for opt in options if str(opt) == raw_stripped]
                    if len(exact_matches) == 1:
                        candidate = (
                            options.index(exact_matches[0]) if use_code else exact_matches[0]
                        )
                    else:
                        # Case-insensitive unique match
                        lowered = raw_stripped.lower()
                        ci_matches = [opt for opt in options if str(opt).lower() == lowered]
                        if len(ci_matches) == 1:
                            candidate = (
                                options.index(ci_matches[0]) if use_code else ci_matches[0]
                            )
                        else:
                            # Unique prefix match
                            prefix_matches = [
                                opt for opt in options if str(opt).lower().startswith(lowered)
                            ]
                            if len(prefix_matches) == 1:
                                candidate = (
                                    options.index(prefix_matches[0]) if use_code else prefix_matches[0]
                                )

                # If still None, and permissive MC, pass raw text through
                if candidate is None and bool(getattr(question, "permissive", False)):
                    candidate = raw

                # Validate via question's built-in validator
                try:
                    validated = question._validate_answer({"answer": candidate})
                    return validated.get("answer", candidate)
                except Exception as e:
                    error_message = Text(str(e), style="bold red")
                    console.print(Panel.fit(error_message, title="Invalid Response", border_style="red"))
                    console.print("Please try again.", style="dim")
                    continue

        # Default: free-text or other types without explicit UI. Single-line input with validation for free-text.
        if getattr(question, "question_type", None) == "file_upload":
            console.print("Enter a file path and press Enter:", style="dim")
            while True:
                try:
                    path = console.input("")
                except KeyboardInterrupt:
                    raise SystemExit(0)

                try:
                    validated = question._validate_answer({"answer": path})
                    return validated.get("answer", path)
                except Exception as e:
                    error_message = Text(str(e), style="bold red")
                    console.print(Panel.fit(error_message, title="Invalid File", border_style="red"))
                    console.print("Please enter a valid, existing file path.", style="dim")
                    continue

        console.print("Enter your response and press Enter:", style="dim")
        while True:
            try:
                response = console.input("")
            except KeyboardInterrupt:
                raise SystemExit(0)

            # Validate free-text questions using the question's built-in validator
            if getattr(question, "question_type", None) == "free_text":
                try:
                    validated = question._validate_answer({"answer": response})
                    return validated.get("answer", response)
                except Exception as e:
                    error_message = Text(str(e), style="bold red")
                    console.print(Panel.fit(error_message, title="Invalid Response", border_style="red"))
                    console.print("Please try again.", style="dim")
                    continue

            # For other types, return raw input (no validation layer wired here yet)
            return response

    def run(self) -> Dict[str, Any]:
        """Run the interactive survey and return `{question_name: answer}` mapping.

        Returns:
            dict[str, Any]: Mapping from question name to user-entered answer.
        """
        # Prefer notebook widget experience when available
        if self._can_use_widget():
            return self._run_in_notebook_blocking()
        # Fallback to terminal (Rich) experience
        return self._run_in_terminal()


__all__ = ["InteractiveSurvey"]


