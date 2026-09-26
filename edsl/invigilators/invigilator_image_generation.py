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
                file
                for file in prompts["files_list"]
                if file.mime_type.startswith("image/")
            ]

        generator = self.question.image_generator
        # Request the GeneratedImage (not a FileStore) so provider usage /
        # cost metadata is available; convert to a FileStore for the answer.
        generated = await generator.async_generate(
            prompt_text, input_images=input_images, return_type="generated_image"
        )
        if isinstance(generated, list):
            generated = generated[0]
        image = generated.to_filestore()
        raw_response = generated.raw_response
        cost = generated.cost()

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
            "input_tokens": cost.input_tokens,
            "output_tokens": cost.output_tokens,
            "thinking_tokens": cost.thinking_tokens,
            "input_price_per_million_tokens": cost.input_price_per_million_tokens,
            "output_price_per_million_tokens": cost.output_price_per_million_tokens,
            "total_cost": cost.total_cost,
        }
        return EDSLResultObjectInput(**data)
