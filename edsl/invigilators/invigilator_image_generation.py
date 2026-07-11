from __future__ import annotations

from typing import Any, Dict

from ..base.data_transfer_models import EDSLResultObjectInput
from .invigilators import InvigilatorBase


class InvigilatorImageGeneration(InvigilatorBase):
    """Invigilator that answers a question by generating an image."""

    def get_prompts(self) -> Dict[str, Any]:
        prompts = self.prompt_constructor.get_prompts()
        from ..prompts import Prompt

        prompts["system_prompt"] = Prompt("")
        return prompts

    async def async_answer_question(self) -> EDSLResultObjectInput:
        prompts = self.get_prompts()
        prompt_text = prompts["user_prompt"].text
        input_images = []
        if "files_list" in prompts:
            input_images = [
                file for file in prompts["files_list"] if file.mime_type.startswith("image/")
            ]

        generator = self.question.image_generator
        image = await generator.async_generate(prompt_text, input_images=input_images)
        raw_response = getattr(image, "raw_response", None)

        data = {
            "answer": image,
            "generated_tokens": prompt_text,
            "comment": None,
            "question_name": self.question.question_name,
            "prompts": prompts,
            "cached_response": None,
            "raw_model_response": raw_response,
            "cache_used": False,
            "cache_key": None,
            "validated": True,
            "exception_occurred": None,
            "input_tokens": None,
            "output_tokens": None,
            "thinking_tokens": None,
            "input_price_per_million_tokens": None,
            "output_price_per_million_tokens": None,
            "total_cost": None,
        }
        return EDSLResultObjectInput(**data)
