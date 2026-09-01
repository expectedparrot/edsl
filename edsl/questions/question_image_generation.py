from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, field_validator

from .decorators import inject_exception
from .question_base import QuestionBase
from .response_validator_abc import ResponseValidatorABC


class ImageGenerationResponse(BaseModel):
    answer: Any
    generated_tokens: Optional[str] = None
    comment: Optional[str] = None

    @field_validator("answer")
    @classmethod
    def validate_filestore_like(cls, value):
        if not hasattr(value, "base64_string") or not hasattr(value, "mime_type"):
            raise ValueError("answer must be a FileStore-like image object")
        if not str(value.mime_type).startswith("image/"):
            raise ValueError("answer must have an image MIME type")
        return value

    class Config:
        arbitrary_types_allowed = True


class ImageGenerationResponseValidator(ResponseValidatorABC):
    required_params = []
    valid_examples = []
    invalid_examples = []


class QuestionImageGeneration(QuestionBase):
    """A question whose answer is a generated image FileStore."""

    question_type = "image_generation"
    _response_model = ImageGenerationResponse
    response_validator_class = ImageGenerationResponseValidator

    def __init__(
        self,
        question_name: str,
        question_text: str,
        model: str = "gemini-3.1-flash-image",
        service_name: str = "google",
        answering_instructions: Optional[str] = None,
        question_presentation: Optional[str] = None,
        generation_parameters: Optional[dict[str, Any]] = None,
        **extra_generation_parameters,
    ):
        if generation_parameters is not None:
            extra_generation_parameters = {
                **generation_parameters,
                **extra_generation_parameters,
            }
        self.question_name = question_name
        self.question_text = question_text
        self.model = model
        self.service_name = service_name
        self.generation_parameters = extra_generation_parameters
        self.answering_instructions = answering_instructions
        self.question_presentation = question_presentation

    @property
    def image_generator(self):
        from ..image_generation import ImageGeneration

        return ImageGeneration(
            model=self.model,
            service_name=self.service_name,
            **self.generation_parameters,
        )

    async def answer_question_directly(
        self, scenario, agent_traits=None, current_answers=None
    ):
        from jinja2 import Template

        current_answers = current_answers or {}
        template_context = dict(scenario) | self._prior_answer_template_context(
            current_answers
        )
        prompt = Template(self.question_text).render(template_context)
        input_images = self._referenced_input_images(scenario, current_answers)
        # Request the GeneratedImage so provider usage / cost metadata survives;
        # convert to a FileStore for the answer.
        generated = await self.image_generator.async_generate(
            prompt, input_images=input_images, return_type="generated_image"
        )
        if isinstance(generated, list):
            generated = generated[0]
        image = generated.to_filestore()
        cost = generated.cost()
        return {
            "answer": image,
            "comment": None,
            "cached": False,
            "input_tokens": cost.input_tokens,
            "output_tokens": cost.output_tokens,
            "input_price_per_million_tokens": cost.input_price_per_million_tokens,
            "output_price_per_million_tokens": cost.output_price_per_million_tokens,
            "total_cost": cost.total_cost,
            "generated_tokens": prompt,
            "raw_model_response": generated.raw_response,
            "user_prompt": prompt,
            "system_prompt": "",
        }

    @staticmethod
    def _prior_answer_template_context(current_answers: dict) -> dict:
        from types import SimpleNamespace

        context = {}
        for key, value in current_answers.items():
            if key.endswith(".answer"):
                continue
            context[key] = SimpleNamespace(answer=value)
        return context

    def _referenced_input_images(self, scenario: dict, current_answers: dict) -> list:
        from .question_base_prompts_mixin import QuestionBasePromptsMixin
        from ..scenarios import FileStore

        referenced_paths = QuestionBasePromptsMixin.extract_parameters(
            self.question_text
        )
        images = []
        for path in referenced_paths:
            name = path[0]
            value = current_answers.get(name)
            if (
                len(path) >= 2
                and path[1] == "answer"
                and isinstance(value, FileStore)
                and value.mime_type.startswith("image/")
            ):
                images.append(value)
                continue
            value = scenario.get(name)
            if (
                isinstance(value, FileStore)
                and value.mime_type.startswith("image/")
                and (len(path) == 1 or path[1] == "answer")
            ):
                images.append(value)
        return images

    @property
    def _invigilator_class(self):
        from ..invigilators.invigilator_image_generation import (
            InvigilatorImageGeneration,
        )

        return InvigilatorImageGeneration

    def to_dict(self, add_edsl_version: bool = True):
        data = {
            "question_name": self.question_name,
            "question_text": self.question_text,
            "model": self.model,
            "service_name": self.service_name,
            "generation_parameters": self.generation_parameters,
            "question_type": self.question_type,
        }
        if self._answering_instructions is not None:
            data["answering_instructions"] = self._answering_instructions
        if self._question_presentation is not None:
            data["question_presentation"] = self._question_presentation
        if add_edsl_version:
            from .. import __version__

            data["edsl_version"] = __version__
            data["edsl_class_name"] = "QuestionBase"
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "QuestionImageGeneration":
        local_data = data.copy()
        local_data.pop("edsl_version", None)
        local_data.pop("edsl_class_name", None)
        local_data.pop("question_type", None)
        generation_parameters = local_data.pop("generation_parameters", {})
        return cls(**local_data, **generation_parameters)

    @classmethod
    @inject_exception
    def example(cls, randomize: bool = False) -> "QuestionImageGeneration":
        addition = "" if not randomize else str(uuid4())
        return cls(
            question_name="generated_image",
            question_text=f"Create a simple blue square icon.{addition}",
            model="test-image",
            service_name="test",
        )
