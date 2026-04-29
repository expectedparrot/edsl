from __future__ import annotations
from typing import Any, Dict, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey
    from ..questions.question_base import QuestionBase
    from ..instructions.instruction import Instruction


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

    # Terminal (Rich) path split into its own helper so we can fall back cleanly
    def _run_in_terminal(self) -> Dict[str, Any]:
        # Ensure we can import Rich only at runtime
        self._ensure_rich()
        console = self._get_console()

        current_item: Optional[Union["QuestionBase", "Instruction"]] = None

        while True:
            next_item = self.survey.next_question_with_instructions(
                current_item, self._rule_answers
            )

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
            raise RuntimeError(
                "Survey returned an unexpected item during interactive run"
            )

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
            console.print(
                Panel.fit(table, title="Survey Complete", border_style="green")
            )
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
        console.print(
            Panel.fit(Markdown(text or ""), title="Instruction", border_style="cyan")
        )
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
        console.print(
            Panel.fit(
                question_text, title=f"{question.question_name}", border_style="magenta"
            )
        )

        # Checkbox (multi-select) with friendly numeric/text entry and iterative selection
        if (
            getattr(question, "question_type", None) == "checkbox"
            and hasattr(question, "question_options")
            and getattr(question, "question_options")
        ):
            options = list(getattr(question, "question_options"))
            table = Table(show_header=True, header_style="bold blue")
            table.add_column("#", justify="right")
            table.add_column("Option", justify="left")
            for idx, option in enumerate(options, start=1):
                table.add_row(str(idx), str(option))
            console.print(table)

            use_code = bool(getattr(question, "use_code", False))

            # Guidance and controls
            console.print(
                "Select one or more options by number or text. Examples: '1,3,5' or 'Apple, Banana'.",
                style="dim",
            )
            console.print(
                "Commands: 'done' to finish, 'quit' to finish, 'clear' to reset, 'all' for all options.",
                style="dim",
            )

            selected: list[Any] = []

            def _display_selected():
                if not selected:
                    console.print("Currently selected: (none)", style="dim")
                else:
                    console.print(f"Currently selected: {selected}", style="dim")

            def _add_choice(token: str) -> bool:
                """Try to add a single token to selection. Returns True if something was added."""
                nonlocal selected
                t = token.strip()
                if not t:
                    return False

                candidate = None
                # Numeric 1-based index
                if t.isdigit():
                    idx = int(t)
                    if 1 <= idx <= len(options):
                        zero = idx - 1
                        candidate = zero if use_code else options[zero]
                if candidate is None:
                    # Try exact, case-insensitive, then unique prefix
                    exact = [opt for opt in options if str(opt) == t]
                    if len(exact) == 1:
                        candidate = options.index(exact[0]) if use_code else exact[0]
                    else:
                        lowered = t.lower()
                        ci = [opt for opt in options if str(opt).lower() == lowered]
                        if len(ci) == 1:
                            candidate = options.index(ci[0]) if use_code else ci[0]
                        else:
                            prefix = [
                                opt
                                for opt in options
                                if str(opt).lower().startswith(lowered)
                            ]
                            if len(prefix) == 1:
                                candidate = (
                                    options.index(prefix[0]) if use_code else prefix[0]
                                )

                if candidate is None:
                    return False

                # Avoid duplicates
                if candidate not in selected:
                    selected.append(candidate)
                    return True
                return False

            _display_selected()
            while True:
                try:
                    raw = console.input("")
                except KeyboardInterrupt:
                    raise SystemExit(0)

                entry = raw.strip()
                if entry.lower() in {"done", "quit", "q"}:
                    # Attempt validation and finish
                    try:
                        validated = question._validate_answer({"answer": selected})
                        return validated.get("answer", selected)
                    except Exception as e:
                        error_message = Text(str(e), style="bold red")
                        console.print(
                            Panel.fit(
                                error_message,
                                title="Invalid Selection",
                                border_style="red",
                            )
                        )
                        console.print("Please adjust your selections.", style="dim")
                        continue
                if entry.lower() == "clear":
                    selected = []
                    _display_selected()
                    continue
                if entry.lower() == "all":
                    selected = list(range(len(options))) if use_code else list(options)
                    _display_selected()
                    continue

                tokens = (
                    [t for t in entry.split(",") if t.strip()]
                    if "," in entry
                    else [entry]
                )
                added_any = False
                for t in tokens:
                    added_any = _add_choice(t) or added_any

                if not added_any:
                    console.print(
                        "No matching option found. Try numbers or exact/unique text.",
                        style="dim",
                    )
                    continue

                _display_selected()
                # Soft validate on every update; show constraint errors early but keep editing
                try:
                    question._validate_answer({"answer": selected})
                except Exception as e:
                    console.print(Text(str(e), style="yellow"))
                # Loop until user types 'done'/'quit'

        # If options exist, show them (and provide numeric selection UX)
        if (
            getattr(question, "question_type", None) == "multiple_choice"
            and hasattr(question, "question_options")
            and getattr(question, "question_options")
        ):
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
                            options.index(exact_matches[0])
                            if use_code
                            else exact_matches[0]
                        )
                    else:
                        # Case-insensitive unique match
                        lowered = raw_stripped.lower()
                        ci_matches = [
                            opt for opt in options if str(opt).lower() == lowered
                        ]
                        if len(ci_matches) == 1:
                            candidate = (
                                options.index(ci_matches[0])
                                if use_code
                                else ci_matches[0]
                            )
                        else:
                            # Unique prefix match
                            prefix_matches = [
                                opt
                                for opt in options
                                if str(opt).lower().startswith(lowered)
                            ]
                            if len(prefix_matches) == 1:
                                candidate = (
                                    options.index(prefix_matches[0])
                                    if use_code
                                    else prefix_matches[0]
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
                    console.print(
                        Panel.fit(
                            error_message, title="Invalid Response", border_style="red"
                        )
                    )
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
                    console.print(
                        Panel.fit(
                            error_message, title="Invalid File", border_style="red"
                        )
                    )
                    console.print(
                        "Please enter a valid, existing file path.", style="dim"
                    )
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
                    console.print(
                        Panel.fit(
                            error_message, title="Invalid Response", border_style="red"
                        )
                    )
                    console.print("Please try again.", style="dim")
                    continue

            # For other types, return raw input (no validation layer wired here yet)
            return response

    def run(self) -> Dict[str, Any]:
        """Run the interactive survey and return `{question_name: answer}` mapping.

        Returns:
            dict[str, Any]: Mapping from question name to user-entered answer.
        """
        return self._run_in_terminal()


__all__ = ["InteractiveSurvey"]
