from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, field_validator

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class DiagramResponse(BaseModel):
    answer: Any
    generated_tokens: Optional[str] = None
    comment: Optional[str] = None

    @field_validator("answer")
    @classmethod
    def validate_filestore_like(cls, value):
        if not hasattr(value, "base64_string") or not hasattr(value, "mime_type"):
            raise ValueError("answer must be a FileStore-like diagram object")
        if value.mime_type not in {"image/svg+xml", "image/png"}:
            raise ValueError("answer must be an SVG or PNG image")
        return value

    class Config:
        arbitrary_types_allowed = True


class DiagramResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = []
    invalid_examples = []


class QuestionDiagram(QuestionBase):
    """A question whose answer is a rendered Graphviz DOT diagram FileStore."""

    question_type = "diagram"
    _response_model = DiagramResponse
    response_validator_class = DiagramResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        output_format: str = "svg",
        engine: str = "dot",
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
    ):
        output_format = output_format.lower()
        if output_format not in {"svg", "png"}:
            raise ValueError("output_format must be 'svg' or 'png'")

        self.question_name = question_name
        self.question_text = question_text
        self.output_format = output_format
        self.engine = engine
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    def answer_question_directly(self, scenario, agent_traits=None):
        if hasattr(scenario, "data"):
            render_context = scenario.data
        else:
            render_context = scenario

        rendered_question = self.render(render_context)
        dot_source = rendered_question.question_text
        diagram = self._render_dot(dot_source)
        result = {
            "answer": diagram,
            "comment": None,
            "generated_tokens": dot_source,
        }
        return self._response_model(**result).model_dump()

    def _render_dot(self, dot_source: str):
        import base64

        try:
            import pydot
        except ImportError as e:
            raise ImportError(
                "QuestionDiagram requires pydot. Install it with `pip install pydot` "
                "or `pip install 'edsl[viz]'`."
            ) from e

        graphs = pydot.graph_from_dot_data(dot_source)
        if not graphs:
            raise ValueError("Could not parse DOT source")
        graph = graphs[0]

        try:
            if self.output_format == "svg":
                content = graph.create_svg(prog=self.engine)
                suffix = "svg"
                mime_type = "image/svg+xml"
            else:
                content = graph.create_png(prog=self.engine)
                suffix = "png"
                mime_type = "image/png"
        except FileNotFoundError as e:
            raise RuntimeError(
                "QuestionDiagram requires Graphviz on PATH. Install Graphviz, "
                "for example with `brew install graphviz` on macOS."
            ) from e

        from ..scenarios import FileStore

        return FileStore(
            base64_string=base64.b64encode(content).decode("utf-8"),
            binary=True,
            suffix=suffix,
            mime_type=mime_type,
            extracted_text="",
        )

    @property
    def question_html_content(self) -> str:
        return f'<pre class="diagram-question">{self.question_text}</pre>'

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionDiagram":
        addition = "" if not randomize else str(uuid4()).replace("-", "_")
        return cls(
            question_name="workflow_diagram",
            question_text=f"digraph {{ Start -> Review{addition}; Review{addition} -> Done }}",
        )
