from __future__ import annotations

from typing import Optional

from ..generated_image import GeneratedImage
from ..image_generation_service_abc import ImageGenerationServiceABC


class TestImageGenerationService(ImageGenerationServiceABC):
    service_name = "test"

    # 1x1 transparent PNG.
    _png_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
        "/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )

    async def async_generate(
        self,
        prompt: str,
        *,
        model: str,
        input_images: Optional[list] = None,
        **kwargs,
    ) -> list[GeneratedImage]:
        n = int(kwargs.get("n", 1))
        return [
            GeneratedImage(
                base64_string=self._png_base64,
                mime_type="image/png",
                model=model,
                service_name=self.service_name,
                prompt=prompt,
                raw_response={
                    "service": self.service_name,
                    "model": model,
                    "prompt": prompt,
                    "input_image_count": len(input_images or []),
                },
            )
            for _ in range(n)
        ]
