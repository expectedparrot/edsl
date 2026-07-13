from __future__ import annotations

import os
import asyncio
from typing import Optional

from ..generated_image import GeneratedImage
from ..image_generation_service_abc import ImageGenerationServiceABC

_genai = None


def _get_genai():
    global _genai
    if _genai is None:
        from google import genai

        _genai = genai
    return _genai


class GoogleImageGenerationService(ImageGenerationServiceABC):
    service_name = "google"

    async def async_generate(
        self,
        prompt: str,
        *,
        model: str,
        input_images: Optional[list] = None,
        **kwargs,
    ) -> list[GeneratedImage]:
        api_key = kwargs.pop("api_key", None) or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")

        request_input = self._build_input(prompt, input_images or [])

        create_kwargs = {
            "model": model,
            "input": request_input,
        }
        if "tools" in kwargs and kwargs["tools"] is not None:
            create_kwargs["tools"] = kwargs["tools"]
        if "previous_interaction_id" in kwargs and kwargs["previous_interaction_id"]:
            create_kwargs["previous_interaction_id"] = kwargs["previous_interaction_id"]
        if "response_format" in kwargs and kwargs["response_format"] is not None:
            create_kwargs["response_format"] = kwargs["response_format"]

        try:
            genai = _get_genai()
            client = genai.Client(api_key=api_key)
            interaction = await client.aio.interactions.create(**create_kwargs)
        except Exception as e:
            if "legacy Interactions API schema is no longer supported" not in str(e):
                raise
            return await self._async_generate_with_rest(
                api_key=api_key,
                prompt=prompt,
                model=model,
                payload=create_kwargs,
            )

        raw_response = (
            interaction.model_dump(mode="json")
            if hasattr(interaction, "model_dump")
            else {"id": getattr(interaction, "id", None)}
        )
        output_image = getattr(interaction, "output_image", None)
        if output_image is None:
            raise ValueError("Google image generation response did not include output_image.")

        mime_type = getattr(output_image, "mime_type", None) or "image/png"
        return [
            GeneratedImage(
                base64_string=output_image.data,
                mime_type=mime_type,
                model=model,
                service_name=self.service_name,
                prompt=prompt,
                raw_response=raw_response,
            )
        ]

    @staticmethod
    def _build_input(prompt: str, input_images: list) -> str | list[dict[str, str]]:
        if not input_images:
            return prompt

        parts = [{"type": "text", "text": prompt}]
        for image in input_images:
            parts.append(
                {
                    "type": "image",
                    "data": image.base64_string,
                    "mime_type": image.mime_type,
                }
            )
        return parts

    async def _async_generate_with_rest(
        self,
        *,
        api_key: str,
        prompt: str,
        model: str,
        payload: dict,
    ) -> list[GeneratedImage]:
        raw_response = await asyncio.to_thread(
            self._post_interaction, api_key=api_key, payload=payload
        )
        image_block = self._extract_image_block(raw_response)
        return [
            GeneratedImage(
                base64_string=image_block["data"],
                mime_type=image_block.get("mime_type", "image/png"),
                model=model,
                service_name=self.service_name,
                prompt=prompt,
                raw_response=raw_response,
            )
        ]

    @staticmethod
    def _post_interaction(*, api_key: str, payload: dict) -> dict:
        import json
        import requests

        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        try:
            return response.json()
        except requests.exceptions.JSONDecodeError:
            decoder = json.JSONDecoder()
            text = response.text
            index = 0
            decoded = []
            while index < len(text):
                while index < len(text) and text[index].isspace():
                    index += 1
                if index >= len(text):
                    break
                obj, end = decoder.raw_decode(text, index)
                decoded.append(obj)
                index = end
            for obj in decoded:
                if GoogleImageGenerationService._response_has_image(obj):
                    return obj
            if decoded:
                return decoded[-1]
            raise

    @staticmethod
    def _extract_image_block(raw_response: dict) -> dict:
        for step in raw_response.get("steps", []):
            if step.get("type") != "model_output":
                continue
            for content_block in step.get("content", []):
                if content_block.get("type") == "image" and content_block.get("data"):
                    return content_block
        raise ValueError("Google image generation response did not include an image block.")

    @staticmethod
    def _response_has_image(raw_response: dict) -> bool:
        try:
            GoogleImageGenerationService._extract_image_block(raw_response)
            return True
        except ValueError:
            return False
