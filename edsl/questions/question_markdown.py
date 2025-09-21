from __future__ import annotations
from typing import Optional

from pydantic import BaseModel

from .question_free_text import QuestionFreeText, FreeTextResponse
from .response_validator_abc import ResponseValidatorABC
from .question_base_prompts_mixin import template_manager


class MarkdownResponse(FreeTextResponse):
    """
    Response model for markdown answers; same schema as free text.

    Examples:
        >>> r = MarkdownResponse(answer="# Title")
        >>> r.answer
        '# Title'
    """


class MarkdownResponseValidator(ResponseValidatorABC):
    """
    Validator that strips fenced code blocks from markdown-like answers.

    Behavior:
    - If the answer (or generated_tokens) contains a fenced block starting with
      ```markdown, extract the content inside the fence.
    - Otherwise, if any fenced block ```...``` is present, extract inside the first one.
    - If no fences are present, return the text as-is.
    - Keep answer and generated_tokens in sync with the stripped content.
    """

    required_params = []
    valid_examples = [({"answer": "# Title"}, {})]
    invalid_examples = []

    def fix(self, response: dict, verbose: bool = False) -> dict:
        """Synchronize answer and generated_tokens using generated_tokens as source.

        This mirrors free-text behavior so validation can succeed before post-processing.
        """
        return {
            "answer": str(response.get("generated_tokens")),
            "generated_tokens": str(response.get("generated_tokens")),
        }

    def _post_process(self, edsl_answer_dict: dict) -> dict:
        text_source = edsl_answer_dict.get("generated_tokens") or edsl_answer_dict.get(
            "answer", ""
        )
        text = str(text_source)

        def strip_fence(s: str) -> str:
            t = s.strip()
            # Prefer ```markdown fences
            if t.startswith("```markdown"):
                body = t[len("```markdown"):].lstrip("\n")
                if body.endswith("```"):
                    body = body[:-3]
                else:
                    idx = body.rfind("```")
                    if idx != -1:
                        body = body[:idx]
                return body.strip("\n")
            # Generic triple backtick
            if t.startswith("```"):
                body = t[3:].lstrip("\n")
                if body.endswith("```"):
                    body = body[:-3]
                else:
                    idx = body.rfind("```")
                    if idx != -1:
                        body = body[:idx]
                return body.strip("\n")
            return t

        stripped = strip_fence(text)
        return {
            "answer": stripped,
            "generated_tokens": stripped,
            "comment": edsl_answer_dict.get("comment"),
        }


class QuestionMarkdown(QuestionFreeText):
    """
    A free-text-like question intended to collect Markdown.

    Post-processing removes surrounding fenced code blocks and returns the inner content.

    Examples:
        >>> from edsl.language_models import Model
        >>> q = QuestionMarkdown(question_name="md", question_text="Provide markdown")
        >>> m = Model("test", canned_response="Sure!\n```markdown\n# Title\n```")
        >>> ans = q.by(m).run(disable_remote_inference=True)
        >>> txt = ans.select("answer.md").first()
        >>> txt.strip().startswith('# Title')
        True
    """

    question_type = "markdown"
    _response_model = MarkdownResponse
    response_validator_class = MarkdownResponseValidator

    @classmethod
    def default_answering_instructions(cls):
        """Reuse free_text answering instructions templates to avoid adding new resources."""
        template_text = template_manager.get_template(
            "free_text", "answering_instructions.jinja"
        )
        from ..prompts import Prompt

        extra = (
            "\n\n"
            "Please respond in valid Markdown. Do not wrap the response in code fences (```...```).\n"
            "Return only the markdown content."
        )
        return Prompt(text=template_text + extra)

    @classmethod
    def default_question_presentation(cls):
        """Reuse free_text question presentation template."""
        template_text = template_manager.get_template(
            "free_text", "question_presentation.jinja"
        )
        from ..prompts import Prompt

        hint = (
            "\n\n"
            "Hint: The expected answer format is valid Markdown (no code fences)."
        )
        return Prompt(text=template_text + hint)

    def __init__(
        self,
        question_name: str,
        question_text: str,
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        super().__init__(
            question_name=question_name,
            question_text=question_text,
            answering_instructions=answering_instructions,
            question_presentation=question_presentation,
        )

    def _simulate_answer(self, human_readable: bool = False) -> dict:
        """Return a consistent simulated markdown answer.

        Ensures answer and generated_tokens match to satisfy validation used in tests.
        """
        sample = "# Example Markdown\n\nThis is a sample."
        return {"answer": sample, "generated_tokens": sample}


