from __future__ import annotations

from typing import Optional


class ImageGeneration:
    """Factory for provider-backed image generation."""

    default_service_name = "google"
    default_model = "gemini-3.1-flash-image"

    _service_classes = {
        "test": (
            "edsl.image_generation.services.test_image_service",
            "TestImageGenerationService",
        ),
        "google": (
            "edsl.image_generation.services.google_image_service",
            "GoogleImageGenerationService",
        ),
    }

    def __init__(
        self,
        model: Optional[str] = None,
        service_name: Optional[str] = None,
        **parameters,
    ):
        self.model = model or self.default_model
        self.service_name = service_name or self.default_service_name
        self.parameters = parameters
        self.service = self._load_service(self.service_name)

    @classmethod
    def _load_service(cls, service_name: str):
        if service_name not in cls._service_classes:
            available = sorted(cls._service_classes)
            raise ValueError(
                f"Image generation service '{service_name}' not found. "
                f"Available services: {available}"
            )
        module_name, class_name = cls._service_classes[service_name]
        import importlib

        module = importlib.import_module(module_name)
        return getattr(module, class_name)()

    async def async_generate(
        self,
        prompt: str,
        *,
        input_images: Optional[list] = None,
        return_type: str = "filestore",
        **kwargs,
    ):
        params = {**self.parameters, **kwargs}
        images = await self.service.async_generate(
            prompt,
            model=self.model,
            input_images=input_images,
            **params,
        )
        if return_type == "generated_image":
            return images[0] if len(images) == 1 else images
        if return_type == "filestore":
            filestores = [image.to_filestore() for image in images]
            return filestores[0] if len(filestores) == 1 else filestores
        raise ValueError("return_type must be 'filestore' or 'generated_image'.")

    def generate(
        self,
        prompt: str,
        *,
        input_images: Optional[list] = None,
        return_type: str = "filestore",
        **kwargs,
    ):
        import asyncio

        return asyncio.run(
            self.async_generate(
                prompt,
                input_images=input_images,
                return_type=return_type,
                **kwargs,
            )
        )
