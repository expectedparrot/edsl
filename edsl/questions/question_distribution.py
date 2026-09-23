"""Elicit probability mass over named outcomes or a numerical partition."""

from __future__ import annotations

import json
import math
import re
from html import escape
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .decorators import inject_exception
from .distribution_intervals import MAX_BINS, generate_bins, parse_bins, portable
from .exceptions import QuestionCreationValidationError
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _decode_generated(text):
    """Read the original JSON before generic response repair can change values."""
    candidate = re.sub(r"^```(?:json)?\s*", "", text.strip(), count=1, flags=re.I)
    answer, end = json.JSONDecoder(object_pairs_hook=_unique_object).raw_decode(
        candidate
    )
    trailing = candidate[end:].strip()
    if trailing.startswith("```"):
        trailing = trailing[3:].strip()
    comment = re.sub(r"^COMMENT:\s*", "", trailing, count=1, flags=re.I) or None
    return answer, comment


class DistributionResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = [({"answer": {"a": 0.2, "b": 0.2, "c": 0.6}}, {})]
    invalid_examples = [({"answer": {"a": 1}}, {}, "Missing outcomes")]


class QuestionDistribution(QuestionBase):
    """Allocate probability mass across categories, explicit bins, or sized bins.

    Supply exactly one of ``question_options``, ``bins``, or the combination
    ``min_value``, ``max_value``, ``bucket_size``. Answers are dictionaries of
    finite probabilities summing to one (absolute tolerance defaults to 1e-6).
    Explicit bins must partition their support without gaps or overlaps.

    >>> q = QuestionDistribution("forecast", "Predict the outcome", question_options=["a", "b"])
    >>> q._validate_answer({"answer": {"b": 0.8, "a": 0.2}})["answer"]
    {'a': 0.2, 'b': 0.8}
    """

    question_type = "distribution"
    _response_model = None
    response_validator_class = DistributionResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        *,
        question_options: Optional[list[str]] = None,
        bins: Optional[list[str]] = None,
        min_value: int | float | str | None = None,
        max_value: int | float | str | None = None,
        bucket_size: int | float | None = None,
        tolerance: float = 1e-6,
        include_comment: bool = True,
        question_presentation: Optional[str] = None,
        answering_instructions: Optional[str] = None,
    ):
        self.question_name = question_name
        self.question_text = question_text
        self.include_comment = include_comment
        self.question_presentation = question_presentation
        self.answering_instructions = answering_instructions
        if (
            isinstance(tolerance, bool)
            or not isinstance(tolerance, (int, float))
            or not math.isfinite(tolerance)
            or not 0 <= tolerance <= 1e-3
        ):
            raise QuestionCreationValidationError(
                "tolerance must be a finite number between 0 and 0.001."
            )
        config = {"tolerance": tolerance}
        intervals = None
        if question_options is not None:
            if any(v is not None for v in (bins, min_value, max_value, bucket_size)):
                raise QuestionCreationValidationError(
                    "question_options cannot be combined with numerical fields."
                )
            if (
                not isinstance(question_options, list)
                or not 1 <= len(question_options) <= MAX_BINS
            ):
                raise QuestionCreationValidationError(
                    f"question_options must contain 1 to {MAX_BINS} labels."
                )
            for value in question_options:
                if (
                    not isinstance(value, str)
                    or not value
                    or value != value.strip()
                    or any(marker in value for marker in ("{{", "{%", "{#"))
                ):
                    raise QuestionCreationValidationError(
                        "Options must be nonempty, static string labels without outside whitespace."
                    )
            if len(set(question_options)) != len(question_options):
                raise QuestionCreationValidationError("Option labels must be unique.")
            config["question_options"] = tuple(question_options)
            keys = tuple(question_options)
        elif bins is not None:
            if bucket_size is not None:
                raise QuestionCreationValidationError(
                    "bins and bucket_size are mutually exclusive."
                )
            intervals = parse_bins(bins, min_value, max_value)
            keys = tuple(interval.label for interval in intervals)
            config["bins"] = keys
            if min_value is not None:
                config["min_value"] = portable(min_value)
            if max_value is not None:
                config["max_value"] = portable(max_value)
        else:
            if any(value is None for value in (min_value, max_value, bucket_size)):
                raise QuestionCreationValidationError(
                    "Supply question_options, bins, or min_value/max_value/bucket_size."
                )
            intervals = generate_bins(min_value, max_value, bucket_size)
            keys = tuple(interval.label for interval in intervals)
            config.update(
                min_value=min_value, max_value=max_value, bucket_size=bucket_size
            )
        self._distribution_config = config
        self._distribution_keys = keys
        self._distribution_intervals = intervals

    @property
    def answer_keys(self) -> tuple[str, ...]:
        return self._distribution_keys

    @property
    def resolved_bins(self) -> Optional[tuple[str, ...]]:
        return self.answer_keys if self._distribution_intervals is not None else None

    @property
    def question_options(self):
        return list(self.answer_keys)

    @property
    def bins(self):
        values = self._distribution_config.get("bins")
        return list(values) if values is not None else None

    @property
    def min_value(self):
        value = self._distribution_config.get("min_value")
        return float(value) if isinstance(value, str) else value

    @property
    def max_value(self):
        value = self._distribution_config.get("max_value")
        return float(value) if isinstance(value, str) else value

    @property
    def bucket_size(self):
        return self._distribution_config.get("bucket_size")

    @property
    def tolerance(self):
        return self._distribution_config["tolerance"]

    @property
    def data(self):
        data = super().data
        for name in (
            "distribution_config",
            "distribution_keys",
            "distribution_intervals",
        ):
            data.pop(name, None)
        data.update(
            {
                key: list(value) if isinstance(value, tuple) else value
                for key, value in self._distribution_config.items()
            }
        )
        # Prompt machinery treats string bounds as scenario templates. Expose
        # numerical infinities internally, but keep strict JSON on the wire.
        for key in ("min_value", "max_value"):
            if key in data:
                data[key] = getattr(self, key)
        # Prompt context includes the realized partition, while serialization
        # retains exactly one constructor form.
        data["answer_keys"] = list(self.answer_keys)
        data["resolved_bins"] = self.resolved_bins
        data["example_answer"] = json.dumps(self._simulate_answer()["answer"])
        return data

    def to_dict(self, add_edsl_version=True):
        data = super().to_dict(add_edsl_version=add_edsl_version)
        for key in ("answer_keys", "resolved_bins", "example_answer"):
            data.pop(key, None)
        for key in ("min_value", "max_value"):
            if key in data:
                data[key] = portable(data[key])
        return data

    def create_response_model(self):
        keys, tolerance = self.answer_keys, self.tolerance

        class DistributionResponse(BaseModel):
            answer: dict[str, float] = Field(
                json_schema_extra={
                    "properties": {
                        key: {"type": "number", "minimum": 0, "maximum": 1}
                        for key in keys
                    },
                    "required": list(keys),
                    "additionalProperties": False,
                }
            )
            comment: Optional[str] = None
            generated_tokens: Optional[Any] = None

            @model_validator(mode="before")
            @classmethod
            def validate_distribution(cls, data):
                if not isinstance(data, dict):
                    raise ValueError("Response must contain an answer dictionary.")
                data = data.copy()
                raw = data.get("generated_tokens")
                if isinstance(raw, str) and raw.strip():
                    answer, comment = _decode_generated(raw)
                    data["answer"] = answer
                    # Generic parsers may split pretty-printed JSON at a newline.
                    data["comment"] = comment
                answer = data.get("answer")
                if not isinstance(answer, dict) or set(answer) != set(keys):
                    raise ValueError(
                        f"Answer must contain exactly these keys: {list(keys)!r}."
                    )
                values = list(answer.values())
                for value in values:
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not 0 <= value <= 1
                        or not math.isfinite(value)
                    ):
                        raise ValueError(
                            "Probabilities must be finite numbers in [0,1], not strings or booleans."
                        )
                total = math.fsum(values)
                if abs(total - 1) > tolerance:
                    raise ValueError(
                        f"Probabilities must sum to 1 within {tolerance}; got {total}."
                    )
                data["answer"] = {key: answer[key] for key in keys}
                return data

        return DistributionResponse

    def draw(self, *args, **kwargs):
        raise QuestionCreationValidationError(
            "QuestionDistribution does not support option randomization."
        )

    def human_readable(self) -> str:
        """Describe the complete allocation rather than a single-choice answer."""
        lines = [
            f"Question Type: {self.question_type}",
            f"Question: {self.question_text}",
            "Allocate probability across every outcome below:",
            *(json.dumps(key, ensure_ascii=False) for key in self.answer_keys),
        ]
        if self.resolved_bins is not None:
            lines.append(
                "Each value is probability mass in the whole interval, not a density height. "
                "Square brackets include endpoints; parentheses exclude them. "
                "Inf denotes an unbounded tail."
            )
        lines.extend([
            "Return a JSON object mapping every exact label to its probability, "
            "including zero-probability outcomes.",
            "Use numeric probabilities from 0 to 1, not percentages. "
            f"Probabilities must sum to 1 within a tolerance of {self.tolerance}.",
        ])
        return "\n".join(lines)

    @property
    def unselected(self):
        # Every outcome is represented, including those assigned zero mass.
        return []

    def _eval_repr_(self):
        data = self.to_dict(add_edsl_version=False)
        data.pop("question_type")
        arguments = ", ".join(f"{key}={value!r}" for key, value in data.items())
        return f"Question('distribution', {arguments})"

    @classmethod
    def example_model(cls):
        from ..language_models import Model

        return Model(
            "test",
            canned_response=json.dumps(cls.example()._simulate_answer()["answer"]),
        )

    def _simulate_answer(self, human_readable=False):
        # Exact valid distribution even for tolerance=0; no random rounding.
        return {
            "answer": {key: float(i == 0) for i, key in enumerate(self.answer_keys)},
            "comment": "Simulated answer",
        }

    @property
    def question_html_content(self):
        rows = "".join(
            f'<label>{escape(key)} <input type="number" min="0" max="1" step="any" '
            f'name="{escape(self.question_name, quote=True)}[{escape(key, quote=True)}]" '
            'value="0" required></label><br>'
            for key in self.answer_keys
        )
        return (
            '<fieldset class="edsl-distribution">'
            + rows
            + '<output aria-live="polite">Total: 0 — probabilities must sum to 1.</output>'
            + "<script>(function(s){const f=s.parentElement;"
            'const update=()=>{const inputs=[...f.querySelectorAll("input")];'
            "const total=inputs.reduce((s,i)=>s+Number(i.value),0);"
            f"const valid=Math.abs(total-1)<={self.tolerance};"
            'f.querySelector("output").textContent="Total: "+total+(valid?"":" — probabilities must sum to 1.");'
            'inputs.forEach(i=>i.setCustomValidity(valid?"":"Probabilities must sum to 1."));};'
            'f.addEventListener("input",update);update();'
            "})(document.currentScript);</script></fieldset>"
        )

    @classmethod
    @inject_exception
    def example(cls, randomize=False):
        return cls(
            "outcome",
            "Predict the outcome." + (f" {uuid4()}" if randomize else ""),
            question_options=["a", "b", "c"],
        )
