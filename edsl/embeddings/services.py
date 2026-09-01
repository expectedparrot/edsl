from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Any, Optional


class EmbeddingService(ABC):
    service_name: str

    @abstractmethod
    async def async_embed(
        self, *, model: str, inputs: list[str], parameters: dict[str, Any]
    ) -> tuple[list[list[float]], Optional[dict[str, Any]]]:
        pass


class OpenAIEmbeddingService(EmbeddingService):
    service_name = "openai"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings.")

    async def async_embed(
        self, *, model: str, inputs: list[str], parameters: dict[str, Any]
    ) -> tuple[list[list[float]], Optional[dict[str, Any]]]:
        try:
            from openai import AsyncOpenAI, DefaultAioHttpClient
        except ImportError as e:
            raise ImportError(
                "The openai package is required. Install with `pip install edsl[inference]`."
            ) from e

        params = {"model": model, "input": inputs, "encoding_format": "float"}
        params.update({k: v for k, v in parameters.items() if v is not None})
        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=DefaultAioHttpClient(),
        )
        try:
            response = await client.embeddings.create(**params)
        finally:
            await client.close()

        data = response.model_dump(mode="json") if hasattr(response, "model_dump") else response
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings, data.get("usage")


class SentenceTransformersEmbeddingService(EmbeddingService):
    service_name = "sentence_transformers"
    _model_cache: dict[str, Any] = {}

    async def async_embed(
        self, *, model: str, inputs: list[str], parameters: dict[str, Any]
    ) -> tuple[list[list[float]], Optional[dict[str, Any]]]:
        if parameters.get("dimensions") is not None:
            raise ValueError(
                "`dimensions` is not supported by the sentence_transformers service."
            )

        def run_encode() -> list[list[float]]:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise ImportError(
                    "The sentence-transformers package is required. Install with `pip install edsl[agent_building]`."
                ) from e

            if model not in self._model_cache:
                self._model_cache[model] = SentenceTransformer(model)
            encoder = self._model_cache[model]
            encode_params = {
                k: v
                for k, v in parameters.items()
                if k in {"batch_size", "show_progress_bar", "normalize_embeddings"}
                and v is not None
            }
            vectors = encoder.encode(inputs, convert_to_numpy=False, **encode_params)
            return [list(map(float, vector)) for vector in vectors]

        return await asyncio.to_thread(run_encode), None


class TestEmbeddingService(EmbeddingService):
    service_name = "test"

    async def async_embed(
        self, *, model: str, inputs: list[str], parameters: dict[str, Any]
    ) -> tuple[list[list[float]], Optional[dict[str, Any]]]:
        dimensions = parameters.get("dimensions") or 3
        embeddings = []
        for text in inputs:
            base = float(len(text))
            embeddings.append([base + float(i) for i in range(dimensions)])
        return embeddings, {"prompt_tokens": sum(len(text.split()) for text in inputs)}


def get_embedding_service(
    service_name: str, *, api_key: Optional[str] = None, base_url: Optional[str] = None
) -> EmbeddingService:
    normalized = service_name.replace("-", "_")
    if normalized == "openai":
        return OpenAIEmbeddingService(api_key=api_key, base_url=base_url)
    if normalized in {"sentence_transformers", "sentence_transformer"}:
        return SentenceTransformersEmbeddingService()
    if normalized == "test":
        return TestEmbeddingService()
    raise ValueError(
        f"Unknown embedding service '{service_name}'. Supported services: openai, sentence_transformers, test."
    )
