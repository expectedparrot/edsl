from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .generated_image import GeneratedImage


class ImageGenerationServiceABC(ABC):
    """Base class for image generation providers."""

    service_name: str

    @abstractmethod
    async def async_generate(
        self,
        prompt: str,
        *,
        model: str,
        input_images: Optional[list] = None,
        **kwargs,
    ) -> list[GeneratedImage]:
        pass

    def generate(
        self,
        prompt: str,
        *,
        model: str,
        input_images: Optional[list] = None,
        **kwargs,
    ) -> list[GeneratedImage]:
        import asyncio

        return asyncio.run(
            self.async_generate(
                prompt,
                model=model,
                input_images=input_images,
                **kwargs,
            )
        )
