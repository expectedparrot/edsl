from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


APP_CSS = """
.container { padding: 1 2; }
#main { height: 1fr; }
#qtext { padding: 1 1; border: round $accent; }
#error { color: red; }
#actions { padding: 0 1; }
#widget { height: 1fr; }
#widget TextArea { height: 1fr; }
"""


class TextualInteractiveSurveyUnavailable(RuntimeError):
    pass


def _import_textual():
    try:
        # Lazy import to avoid hard dependency when not used
        from textual.app import App, ComposeResult  # type: ignore
        from textual.containers import Horizontal, Vertical, Container  # type: ignore
        from textual.widgets import (  # type: ignore
            Header,
            Footer,
            Button,
            Static,
            Input,
            TextArea,
            Select,
            Checkbox,
            DirectoryTree,
        )
        from textual import events  # type: ignore

        return {
            "App": App,
            "ComposeResult": ComposeResult,
            "Horizontal": Horizontal,
            "Vertical": Vertical,
            "Container": Container,
            "Header": Header,
            "Footer": Footer,
            "Button": Button,
            "Static": Static,
            "Input": Input,
            "TextArea": TextArea,
            "Select": Select,
            "Checkbox": Checkbox,
            "DirectoryTree": DirectoryTree,
            "events": events,
        }
    except (
        Exception
    ) as e:  # pragma: no cover - only triggered when textual not installed
        raise TextualInteractiveSurveyUnavailable(
            "Textual is required for TextualInteractiveSurvey. Install with: pip install textual"
        ) from e


class _QuestionViewState:
    def __init__(self, item: Any) -> None:
        self.item = item
        self.temp_value: Any = None


class TextualInteractiveSurveyApp:  # Thin wrapper to avoid importing textual at module import time
    def __init__(self, survey: Any, title: Optional[str] = None) -> None:
        self.survey = survey
        self.title = title or "E[🦜] Survey"
        self.answers: Dict[str, Any] = {}
        self._rule_answers: Dict[str, Any] = {}
        self._history: List[_QuestionViewState] = []

        # textual symbols resolved on build()
        self._sym: Optional[dict] = None
        self._app: Optional[Any] = None

    # Public API mirrors InteractiveSurvey
    def run(self) -> Dict[str, Any]:
        sym = _import_textual()
        self._sym = sym

        App = sym["App"]
        ComposeResult = sym["ComposeResult"]
        Horizontal = sym["Horizontal"]
        Vertical = sym["Vertical"]
        Container = sym["Container"]
        Header = sym["Header"]
        Button = sym["Button"]
        Static = sym["Static"]
        Input = sym["Input"]
        TextArea = sym["TextArea"]
        Select = sym["Select"]
        Checkbox = sym["Checkbox"]
        DirectoryTree = sym["DirectoryTree"]

        survey = self.survey
        answers = self.answers
        rule_answers = self._rule_answers
        history = self._history

        outer_title = self.title

        class _App(App):
            CSS = APP_CSS

            def __init__(self) -> None:
                super().__init__()
                self.current_item: Optional[Any] = None
                self.error_view: Optional[Any] = None
                self.qtext_view: Optional[Any] = None
                self.widget_region: Optional[Any] = None
                self.footer_buttons: Optional[Any] = None
                self.file_modal: Optional[Any] = None
                self.file_input: Optional[Any] = None
                self.checkbox_items: List[Tuple[str, Any]] = []

            def compose(self) -> ComposeResult:  # type: ignore[override]
                yield Header(show_clock=False)
                with Vertical(id="main", classes="container"):
                    yield Static("", id="error")
                    yield Static("", id="qtext", classes="qtext")
                    yield Container(id="widget")
                with Horizontal(id="actions"):
                    yield Button("Previous", id="prev")
                    yield Button("Next", id="next", classes="-primary")

            def on_mount(self) -> None:
                # Ensure the header shows the desired title
                try:
                    self.title = outer_title
                except Exception:
                    pass
                self.error_view = self.query_one("#error", Static)
                self.qtext_view = self.query_one("#qtext", Static)
                self.widget_region = self.query_one("#widget", Container)
                self._goto_next(None)

            # Navigation
            def _goto_next(self, current: Optional[Any]) -> None:
                from .base import EndOfSurvey  # lazy import

                next_item = survey.next_question_with_instructions(
                    current, rule_answers
                )
                if next_item is EndOfSurvey:
                    self.exit(answers)
                    return
                state = _QuestionViewState(next_item)
                history.append(state)
                self._render_item(state)

            def _goto_prev(self) -> None:
                if not history:
                    return
                last = history.pop()
                # If last was a question, remove its answer
                qname = getattr(last.item, "question_name", None)
                if qname and qname in answers:
                    answers.pop(qname, None)
                    rule_answers.pop(f"{qname}.answer", None)
                prev_item = history[-1].item if history else None
                # Re-render previous (or restart)
                if prev_item is None:
                    self._goto_next(None)
                else:
                    # Re-render previous without advancing
                    self._render_item(history[-1])

            # Rendering
            def _render_item(self, state: _QuestionViewState) -> None:
                self.error_view.update("")
                try:
                    self.widget_region.remove_children()
                except Exception:
                    self.widget_region.update("")
                item = state.item

                # Instruction-only items
                if hasattr(item, "text") and not hasattr(item, "question_name"):
                    self.qtext_view.update(str(getattr(item, "text", "")))
                    return

                # Questions
                qtext = getattr(item, "question_text", "")
                self.qtext_view.update(qtext)

                qtype = getattr(item, "question_type", None)
                if qtype == "free_text":
                    ta = TextArea()
                    ta.border_title = "Your answer"
                    self.widget_region.mount(ta)
                    ta.focus()
                    state.temp_value = ta
                elif qtype == "multiple_choice":
                    options = list(getattr(item, "question_options", []) or [])
                    select_options: List[Tuple[str, Any]] = [
                        (str(opt), idx) for idx, opt in enumerate(options)
                    ]
                    sel = Select(select_options)
                    self.widget_region.mount(sel)
                    sel.focus()
                    state.temp_value = (sel, options)
                elif qtype == "checkbox":
                    options = list(getattr(item, "question_options", []) or [])
                    container = Vertical()
                    self.widget_region.mount(container)
                    checkboxes: List[Checkbox] = []
                    for idx, opt in enumerate(options):
                        cb = Checkbox(str(opt), value=False)
                        container.mount(cb)
                        checkboxes.append(cb)
                    state.temp_value = (checkboxes, options)
                elif qtype == "file_upload":
                    row = Horizontal()
                    self.widget_region.mount(row)
                    path_input = Input(placeholder="/path/to/file")
                    browse_btn = Button("Browse", id="browse")
                    row.mount(path_input)
                    row.mount(browse_btn)
                    state.temp_value = path_input
                    self.file_input = path_input
                else:
                    # Fallback single-line input
                    inp = Input()
                    self.widget_region.mount(inp)
                    inp.focus()
                    state.temp_value = inp

            # Validation and collection
            def _collect_and_validate(
                self, state: _QuestionViewState
            ) -> Tuple[bool, Optional[str]]:
                item = state.item
                qname = getattr(item, "question_name", None)
                if not qname:
                    return True, None

                qtype = getattr(item, "question_type", None)
                use_code = bool(getattr(item, "use_code", False))

                try:
                    if qtype == "free_text":
                        widget = state.temp_value
                        text_value = (
                            widget.text
                            if hasattr(widget, "text")
                            else str(widget.value)
                        )
                        validated = item._validate_answer({"answer": text_value})
                        value = validated.get("answer", text_value)
                    elif qtype == "multiple_choice":
                        sel, options = state.temp_value
                        selected = sel.value
                        if selected is None:
                            raise ValueError("Please select an option")
                        idx = int(selected)
                        value = idx if use_code else options[idx]
                        validated = item._validate_answer({"answer": value})
                        value = validated.get("answer", value)
                    elif qtype == "checkbox":
                        checkboxes, options = state.temp_value
                        indices = [
                            i
                            for i, cb in enumerate(checkboxes)
                            if getattr(cb, "value", False)
                        ]
                        if not indices:
                            value = [] if use_code else []
                        value = indices if use_code else [options[i] for i in indices]
                        validated = item._validate_answer({"answer": value})
                        value = validated.get("answer", value)
                    elif qtype == "file_upload":
                        path = (
                            state.temp_value.value
                            if hasattr(state.temp_value, "value")
                            else ""
                        )
                        validated = item._validate_answer({"answer": path})
                        value = validated.get("answer", path)
                    else:
                        # Generic single-line
                        raw = (
                            state.temp_value.value
                            if hasattr(state.temp_value, "value")
                            else str(state.temp_value)
                        )
                        validated = (
                            item._validate_answer({"answer": raw})
                            if hasattr(item, "_validate_answer")
                            else {"answer": raw}
                        )
                        value = validated.get("answer", raw)

                    answers[qname] = value
                    rule_answers[f"{qname}.answer"] = value
                    return True, None
                except Exception as e:
                    return False, str(e)

            # Events
            def on_button_pressed(self, event) -> None:  # type: ignore[override]
                button_id = getattr(event.button, "id", None)
                if button_id == "prev":
                    self._goto_prev()
                    return
                if button_id == "browse":
                    # Open a simple file chooser modal
                    self._open_file_modal()
                    return
                if button_id == "next":
                    if not history:
                        self._goto_next(None)
                        return
                    state = history[-1]
                    ok, err = self._collect_and_validate(state)
                    if ok:
                        self._goto_next(state.item)
                    else:
                        self.error_view.update(err or "Invalid input")

            def _open_file_modal(self) -> None:
                # Create a lightweight modal with a DirectoryTree; selecting a file populates the input
                if self.file_input is None:
                    return
                import os

                tree = DirectoryTree(os.getcwd())

                def _on_file_selected(message) -> None:  # type: ignore[no-untyped-def]
                    try:
                        path = str(getattr(message, "path", ""))
                        if path:
                            self.file_input.value = path
                        # Close modal by removing tree's parent container
                        container.remove()
                    except Exception:
                        container.remove()

                tree.can_focus = True
                tree.show_root = False
                tree.border_title = "Select a file"
                tree.on_directory_tree_file_selected = _on_file_selected  # type: ignore[attr-defined]
                container = Vertical()
                container.border_title = "File Browser"
                container.mount(tree)
                self.widget_region.mount(container)

        app = _App()
        self._app = app
        app.run()
        return dict(self.answers)


def run_textual_survey(survey: Any, title: Optional[str] = None) -> Dict[str, Any]:
    app = TextualInteractiveSurveyApp(survey=survey, title=title)
    return app.run()


__all__ = [
    "TextualInteractiveSurveyApp",
    "run_textual_survey",
    "TextualInteractiveSurveyUnavailable",
]
