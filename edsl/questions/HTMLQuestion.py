from typing import Optional
from jinja2.exceptions import SecurityError


class HTMLQuestion:
    def __init__(self, question):
        self.question = question

    def html(
        self,
        scenario: Optional[dict] = None,
        agent: Optional[dict] = {},
        answers: Optional[dict] = None,
        include_question_name: bool = False,
        height: Optional[int] = None,
        width: Optional[int] = None,
        iframe=False,
    ):
        """Return the question in HTML format."""
        from ..utilities.jinja import safe_template as Template

        if scenario is None:
            scenario = {}

        prior_answers_dict = {}

        if isinstance(answers, dict):
            for key, value in answers.items():
                if not key.endswith("_comment") and not key.endswith(
                    "_generated_tokens"
                ):
                    prior_answers_dict[key] = {"answer": value}

        base_template = """
        <div id="{{ question_name }}" class="survey_question" data-type="{{ question_type }}">
            {% if include_question_name %}
            <p>question_name: {{ question_name }}</p>
            {% endif %}
            <p class="question_text">{{ question_text }}</p>
            {{ question_content }}
        </div>
        """
        if not hasattr(self.question, "question_type"):
            self.question.question_type = "unknown"

        base_template = Template(base_template)

        # Resolve fields before placing their values into the fixed HTML shell.
        # Never compile the generated HTML: interpolated option/label strings
        # must not become a second template program.
        context = dict(scenario) | {"agent": agent} | prior_answers_dict
        try:
            rendered_question = self.question.render(context)
        except SecurityError:
            raise
        except Exception as e:
            print(
                f"Error rendering question: question_text = {self.question.question_text}, error = {e}"
            )
            rendered_question = self.question
        question_text = rendered_question.question_text
        question_content = getattr(rendered_question, "question_html_content", "")

        try:
            params = {
                "question_name": self.question.question_name,
                "question_text": question_text,
                "question_type": self.question.question_type,
                "question_content": question_content,
                "include_question_name": include_question_name,
            }
        except Exception as e:
            from .exceptions import QuestionValueError

            raise QuestionValueError(
                f"Error rendering question: params = {params}, error = {e}"
            )
        rendered_html = base_template.render(**params)

        if iframe:
            from ..utilities.display_utils import display_html

            height = height or 200
            width = width or 600
            display_html(rendered_html, width=width, height=height, as_iframe=True)
            return None

        return rendered_html
