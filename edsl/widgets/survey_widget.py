"""
Survey Widget

An interactive widget for presenting EDSL surveys to users one question at a time,
collecting their responses, and generating the final answer dictionary.
"""

from typing import Any, Dict
import traitlets
from .base_widget import EDSLBaseWidget


class SurveyWidget(EDSLBaseWidget):
    """Interactive widget for collecting responses to EDSL surveys.

    This widget presents questions from an EDSL Survey one at a time, allowing users
    to provide answers through HTML form elements. It handles survey flow logic,
    including skip logic and branching rules, using the survey's gen_path_through_survey
    method.

    Features:
    - One question at a time presentation
    - Uses each question's question_html_content property for rendering
    - Handles survey rules and conditional logic
    - Returns a complete answer dictionary when finished
    - Simple, clean interface with navigation controls
    - Resume surveys from previous state with initial answers
    - Dynamic answer updates after widget creation

    Example:
        >>> from edsl.surveys import Survey
        >>> from edsl.questions import QuestionFreeText, QuestionMultipleChoice
        >>> from edsl.widgets import SurveyWidget
        >>>
        >>> survey = Survey([
        ...     QuestionFreeText(question_name="name", question_text="What is your name?"),
        ...     QuestionMultipleChoice(
        ...         question_name="satisfaction",
        ...         question_text="How satisfied are you?",
        ...         question_options=["Very Satisfied", "Satisfied", "Neutral", "Dissatisfied"]
        ...     )
        ... ])
        >>>
        >>> # Start fresh
        >>> widget = SurveyWidget(survey)
        >>> widget  # Display in Jupyter notebook
        >>>
        >>> # Resume from previous answers
        >>> previous_answers = {"name": "Alice"}
        >>> widget_resumed = SurveyWidget(survey, previous_answers)
        >>> widget_resumed  # Starts at 'satisfaction' question
        >>>
        >>> # Update answers dynamically
        >>> widget.set_initial_answers({"name": "Bob"})  # Restarts survey with Bob
    """

    widget_short_name = "survey_widget"

    # Traitlets for communication with frontend
    survey = traitlets.Any(allow_none=True).tag(sync=False)
    current_question_html = traitlets.Unicode(default_value="").tag(sync=True)
    current_question_name = traitlets.Unicode(default_value="").tag(sync=True)
    is_complete = traitlets.Bool(default_value=False).tag(sync=True)
    answers = traitlets.Dict().tag(sync=True)
    progress = traitlets.Dict().tag(sync=True)  # {"current": 1, "total": 5} or similar
    error_message = traitlets.Unicode(default_value="").tag(sync=True)

    # Inline assets to avoid external Coop dependency for this widget
    _css = """
    .survey-widget { font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji"; line-height: 1.35; }
    .survey-widget .survey-progress { color: #666; font-size: 12px; margin-bottom: 8px; }
    .survey-widget .survey-content { padding: 8px 0; }
    .survey-widget .survey-controls { margin-top: 12px; display: flex; gap: 8px; }
    .survey-widget .survey-controls button { appearance: none; border: 1px solid #bbb; background: #f8f8f8; border-radius: 6px; padding: 6px 10px; cursor: pointer; }
    .survey-widget .survey-controls button:hover { background: #f0f0f0; }
    .survey-widget .survey-controls button:disabled { opacity: 0.6; cursor: not-allowed; }
    .survey-widget .survey-error { color: #b00020; font-size: 12px; min-height: 16px; margin-top: 6px; }
    .survey-widget .survey-complete { padding: 12px; border: 1px solid #c6f6d5; background: #f0fff4; border-radius: 6px; }
    """

    _esm = """
    export default {
      render(args) {
        try {
          const model = args && args.model;
          const el = args && args.el;
          if (!model || !el) { return; }

          const root = document.createElement('div');
          root.className = 'survey-widget';
          const progress = document.createElement('div');
          progress.className = 'survey-progress';
          const content = document.createElement('div');
          content.className = 'survey-content';
          const error = document.createElement('div');
          error.className = 'survey-error';
          const controls = document.createElement('div');
          controls.className = 'survey-controls';
          const submitBtn = document.createElement('button');
          submitBtn.textContent = 'Submit';
          const restartBtn = document.createElement('button');
          restartBtn.textContent = 'Restart';
          controls.appendChild(submitBtn);
          controls.appendChild(restartBtn);
          root.appendChild(progress);
          root.appendChild(content);
          root.appendChild(error);
          root.appendChild(controls);
          el.replaceChildren(root);

          function render() {
            const html = model.get('current_question_html') || '';
            const qname = model.get('current_question_name') || '';
            const isComplete = !!model.get('is_complete');
            const prog = model.get('progress') || {};
            error.textContent = '';
            if (prog && typeof prog.current !== 'undefined' && typeof prog.total !== 'undefined') {
              progress.textContent = `Question ${prog.current} of ${prog.total}`;
            } else {
              progress.textContent = '';
            }

            if (isComplete) {
              content.innerHTML = html || '<div class=\"survey-complete\"><h3>Survey Complete!</h3><p>Thank you for your responses.</p></div>';
              submitBtn.disabled = true;
              return;
            }

            content.innerHTML = html || '';
            submitBtn.disabled = !qname;
          }

          function extractAnswer() {
            const qname = model.get('current_question_name') || '';
            if (!qname) return null;
            const radios = content.querySelectorAll(`input[type=\"radio\"][name=\"${qname}\"]`);
            if (radios && radios.length) {
              const selected = Array.from(radios).find(r => r.checked);
              return selected ? selected.value : null;
            }
            const checks = content.querySelectorAll(`input[type=\"checkbox\"][name=\"${qname}\"]`);
            if (checks && checks.length) {
              const values = Array.from(checks).filter(c => c.checked).map(c => c.value);
              return values;
            }
            const textarea = content.querySelector(`textarea#${qname}, textarea[name=\"${qname}\"]`);
            if (textarea) return textarea.value;
            const input = content.querySelector(`input#${qname}, input[name=\"${qname}\"]`);
            if (input) {
              if (input.type === 'number') return input.value === '' ? null : Number(input.value);
              return input.value;
            }
            const select = content.querySelector(`select#${qname}, select[name=\"${qname}\"]`);
            if (select) return select.value;
            return null;
          }

          submitBtn.addEventListener('click', () => {
            const qname = model.get('current_question_name') || '';
            const val = extractAnswer();
            if (val === null || (Array.isArray(val) && val.length === 0)) {
              error.textContent = 'Please provide an answer.';
              return;
            }
            model.send({ type: 'submit_answer', question_name: qname, answer: val });
          });

          restartBtn.addEventListener('click', () => {
            model.send({ type: 'restart_survey' });
          });

          model.on('change:current_question_html', render);
          model.on('change:current_question_name', render);
          model.on('change:is_complete', render);
          model.on('change:progress', render);
        model.on('change:error_message', () => {
          const msg = model.get('error_message') || '';
          error.textContent = msg;
        });
          render();

        // Allow Enter key in text inputs to submit
        content.addEventListener('keydown', (ev) => {
          const target = ev.target;
          if (ev.key === 'Enter' && target && (target.tagName === 'INPUT')) {
            ev.preventDefault();
            submitBtn.click();
          }
        });
        } catch (e) {
          console.error('[survey_widget] render error:', e);
        }
      }
    }
    """

    def __init__(self, survey=None, initial_answers=None, **kwargs):
        """Initialize the Survey Widget.

        Args:
            survey: An EDSL Survey instance to present to the user.
            initial_answers: Optional dictionary of pre-existing answers to resume from.
                           Format: {"question_name": answer_value, ...}
            **kwargs: Additional keyword arguments passed to the base widget.
        """
        super().__init__(**kwargs)
        self._generator = None
        self._current_question = None
        self._question_count = 0
        self._questions_seen = 0
        self._initial_answers = initial_answers or {}

        # Set up message handling from frontend
        self.on_msg(self._handle_frontend_message)

        if survey is not None:
            self.survey = survey
            self._start_survey()

    def _handle_frontend_message(self, widget, content, buffers):
        """Handle messages sent from the JavaScript frontend."""
        try:
            msg_type = content.get("type")

            if msg_type == "submit_answer":
                question_name = content.get("question_name")
                answer = content.get("answer")
                if question_name and answer is not None:
                    self.submit_answer(answer)

            elif msg_type == "restart_survey":
                self.restart_survey()

        except Exception as e:
            self.error_message = f"Error handling message: {str(e)}"

    @traitlets.observe("survey")
    def _on_survey_change(self, change):
        """Update widget when survey changes."""
        if change["new"] is not None:
            self._start_survey()
        else:
            self._reset_widget()

    def _start_survey(self):
        """Start the survey by initializing the generator and showing the first question."""
        if self.survey is None:
            return

        try:
            # Initialize the survey path generator
            self._generator = self.survey.gen_path_through_survey()
            self.answers = {}
            self._questions_seen = 0
            self.is_complete = False
            self.error_message = ""

            # Count total questions for progress tracking (approximate)
            self._question_count = len(self.survey.questions)

            # If we have initial answers, replay them through the generator
            if self._initial_answers:
                self._replay_initial_answers()
            else:
                # Get the first question normally
                self._get_next_question()

        except Exception as e:
            self.error_message = f"Error starting survey: {str(e)}"
            self.current_question_html = ""
            self.current_question_name = ""

    def _get_next_question(self):
        """Get the next question from the generator and render it."""
        try:
            if self._generator is None:
                return

            # Get next question from the generator
            self._current_question = next(self._generator)
            self._questions_seen += 1

            # Render the question HTML
            self._render_current_question()

            # Update progress
            self.progress = {
                "current": self._questions_seen,
                "total": self._question_count,
            }

        except StopIteration:
            # Survey is complete
            self._complete_survey()
        except Exception as e:
            self.error_message = f"Error getting next question: {str(e)}"

    def _render_current_question(self):
        """Render the current question using its HTML content."""
        if self._current_question is None:
            return

        try:
            # Use HTMLQuestion to render the question
            from ..questions.HTMLQuestion import HTMLQuestion

            html_question = HTMLQuestion(self._current_question)
            html_content = html_question.html(
                scenario={}, agent={}, answers=self.answers, include_question_name=False
            )

            self.current_question_html = html_content
            self.current_question_name = self._current_question.question_name

        except Exception as e:
            self.error_message = f"Error rendering question: {str(e)}"
            self.current_question_html = f"<p>Error rendering question: {str(e)}</p>"

    def _replay_initial_answers(self):
        """Replay initial answers to advance the survey to the correct position.

        This method steps through the generator, submitting each initial answer
        until either all initial answers are consumed or the survey is complete.
        """
        try:
            # Get the first question
            self._current_question = next(self._generator)
            self._questions_seen += 1

            # Keep track of which answers we've processed
            processed_answers = set()

            while self._current_question and self._initial_answers:
                current_question_name = self._current_question.question_name

                # Check if we have an initial answer for this question
                if (
                    current_question_name in self._initial_answers
                    and current_question_name not in processed_answers
                ):
                    # Get the answer for this question
                    answer_value = self._initial_answers[current_question_name]

                    # Store the answer
                    self.answers = {**self.answers, current_question_name: answer_value}
                    processed_answers.add(current_question_name)

                    # Send the answer to the generator to get the next question
                    next_question = self._generator.send(
                        {f"{current_question_name}.answer": answer_value}
                    )
                    self._current_question = next_question
                    self._questions_seen += 1

                else:
                    # No initial answer for this question, stop replaying
                    break

            # Now render the current question (either the next unanswered question or completion)
            if self._current_question:
                self._render_current_question()

                # Update progress
                self.progress = {
                    "current": self._questions_seen,
                    "total": self._question_count,
                }
            else:
                # Survey completed during replay
                self._complete_survey()

        except StopIteration:
            # Survey completed during replay
            self._complete_survey()
        except Exception as e:
            self.error_message = f"Error replaying initial answers: {str(e)}"
            # Fall back to showing the first question
            self._get_next_question()

    def submit_answer(self, answer_value):
        """Submit an answer for the current question and advance to the next.

        This method is called from the frontend when the user submits an answer.

        Args:
            answer_value: The user's answer to the current question
        """
        if self._current_question is None or self._generator is None:
            return

        try:
            # Store the answer
            question_name = self._current_question.question_name
            self.answers = {**self.answers, question_name: answer_value}

            # Send the answer to the generator and get the next question
            next_question = self._generator.send(
                {f"{question_name}.answer": answer_value}
            )

            # Update the current question
            self._current_question = next_question
            self._questions_seen += 1

            # Render the next question
            self._render_current_question()

            # Update progress
            self.progress = {
                "current": self._questions_seen,
                "total": self._question_count,
            }

        except StopIteration:
            # Survey is complete
            self._complete_survey()
        except Exception as e:
            self.error_message = f"Error submitting answer: {str(e)}"

    def _complete_survey(self):
        """Mark the survey as complete."""
        self.is_complete = True
        self.current_question_html = "<div class='survey-complete'><h3>Survey Complete!</h3><p>Thank you for your responses.</p></div>"
        self.current_question_name = ""
        self.progress = {
            "current": self._questions_seen,
            "total": self._questions_seen,  # Update total to actual questions seen
        }

    def _reset_widget(self):
        """Reset the widget to initial state."""
        self.current_question_html = ""
        self.current_question_name = ""
        self.is_complete = False
        self.answers = {}
        self.progress = {"current": 0, "total": 0}
        self.error_message = ""
        self._generator = None
        self._current_question = None
        self._question_count = 0
        self._questions_seen = 0

    def restart_survey(self):
        """Restart the survey from the beginning.

        This method can be called to reset and restart the survey.
        """
        if self.survey is not None:
            self._start_survey()

    def get_answers(self) -> Dict[str, Any]:
        """Get the current answer dictionary.

        Returns:
            Dictionary mapping question names to user answers
        """
        return dict(self.answers)

    def set_initial_answers(self, initial_answers: Dict[str, Any]):
        """Set initial answers and restart the survey from that point.

        Args:
            initial_answers: Dictionary mapping question names to answer values
        """
        self._initial_answers = initial_answers or {}
        if self.survey is not None:
            self._start_survey()

    def add_initial_answer(self, question_name: str, answer_value: Any):
        """Add a single initial answer and restart the survey.

        Args:
            question_name: Name of the question
            answer_value: The answer value
        """
        if self._initial_answers is None:
            self._initial_answers = {}
        self._initial_answers[question_name] = answer_value

        if self.survey is not None:
            self._start_survey()

    def get_initial_answers(self) -> Dict[str, Any]:
        """Get the current initial answers dictionary.

        Returns:
            Dictionary of initial answers that were provided
        """
        return dict(self._initial_answers) if self._initial_answers else {}


# Convenience function for easy import
def create_survey_widget(survey=None, initial_answers=None):
    """Create and return a new Survey Widget instance.

    Args:
        survey: An EDSL Survey instance
        initial_answers: Optional dictionary of pre-existing answers

    Returns:
        SurveyWidget instance
    """
    return SurveyWidget(survey, initial_answers)


# Export the main class
__all__ = ["SurveyWidget", "create_survey_widget"]
