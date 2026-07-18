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
            raise ValueError(
                "Google image generation response did not include output_image."
            )

        mime_type = getattr(output_image, "mime_type", None) or "image/png"
        return [
            GeneratedImage(
                base64_string=output_image.data,
                mime_type=mime_type,
                model=model,
                service_name=self.service_name,
                prompt=prompt,
                raw_response=raw_response,
                usage=self._extract_usage(raw_response),
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
                usage=self._extract_usage(raw_response),
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

    # Candidate key names for each token count, covering both the genai SDK's
    # snake_case model_dump and the REST endpoint's camelCase, and the
    # Interactions API's "response_token_count" alias for output tokens.
    _INPUT_TOKEN_KEYS = ("prompt_token_count", "promptTokenCount")
    _OUTPUT_TOKEN_KEYS = (
        "candidates_token_count",
        "candidatesTokenCount",
        "response_token_count",
        "responseTokenCount",
    )
    _THINKING_TOKEN_KEYS = ("thoughts_token_count", "thoughtsTokenCount")

    @classmethod
    def _extract_usage(cls, raw_response) -> Optional[dict]:
        """Pull token usage out of a Google response into edsl's field names.

        Searches for a ``usage_metadata``/``usage`` block anywhere in the
        response (top level or nested within interaction steps) and normalizes
        it to prompt_token_count / candidates_token_count / thoughts_token_count.
        Returns None when no usage information is present.
        """
        usage_block = cls._find_usage_block(raw_response)
        if not usage_block:
            return None

        def _first(keys):
            for key in keys:
                value = usage_block.get(key)
                if value is not None:
                    return value
            return None

        normalized = {
            "prompt_token_count": _first(cls._INPUT_TOKEN_KEYS),
            "candidates_token_count": _first(cls._OUTPUT_TOKEN_KEYS),
            "thoughts_token_count": _first(cls._THINKING_TOKEN_KEYS),
        }
        if all(value is None for value in normalized.values()):
            return None
        return normalized

    @classmethod
    def _find_usage_block(cls, node, _depth: int = 0) -> Optional[dict]:
        """Recursively locate a usage dict (bounded depth) within a response."""
        if _depth > 6 or not isinstance(node, (dict, list)):
            return None
        if isinstance(node, dict):
            for key in ("usage_metadata", "usageMetadata", "usage"):
                candidate = node.get(key)
                if isinstance(candidate, dict) and cls._looks_like_usage(candidate):
                    return candidate
            # The response itself may be the usage block.
            if cls._looks_like_usage(node):
                return node
            for value in node.values():
                found = cls._find_usage_block(value, _depth + 1)
                if found:
                    return found
        else:
            for item in node:
                found = cls._find_usage_block(item, _depth + 1)
                if found:
                    return found
        return None

    @classmethod
    def _looks_like_usage(cls, candidate: dict) -> bool:
        keys = cls._INPUT_TOKEN_KEYS + cls._OUTPUT_TOKEN_KEYS
        return any(key in candidate for key in keys)

    @staticmethod
    def _extract_image_block(raw_response: dict) -> dict:
        for step in raw_response.get("steps", []):
            if step.get("type") != "model_output":
                continue
            for content_block in step.get("content", []):
                if content_block.get("type") == "image" and content_block.get("data"):
                    return content_block
        raise ValueError(
            "Google image generation response did not include an image block."
        )

    @staticmethod
    def _response_has_image(raw_response: dict) -> bool:
        try:
            GoogleImageGenerationService._extract_image_block(raw_response)
            return True
        except ValueError:
            return False
