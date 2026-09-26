from __future__ import annotations

from typing import Any, Optional, Union

from .embedding_cache import EmbeddingCache
from .embedding_result import EmbeddingResult
from .services import get_embedding_service
from ..utilities import jupyter_nb_handler


class EmbeddingModel:
    default_model_by_service = {
        "openai": "text-embedding-3-large",
        "sentence_transformers": "all-MiniLM-L6-v2",
        "test": "test",
    }

    def __init__(
        self,
        model_name: Optional[str] = None,
        service_name: str = "openai",
        *,
        dimensions: Optional[int] = None,
        remote: bool = False,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **parameters: Any,
    ):
        self.service_name = service_name.replace("-", "_")
        self.model = model_name or self.default_model_by_service.get(self.service_name)
        if self.model is None:
            raise ValueError(
                f"No default embedding model for service '{service_name}'."
            )
        self.remote = remote
        self.api_key = api_key
        self.base_url = base_url
        self.parameters = {"dimensions": dimensions, **parameters}

    @staticmethod
    def _normalize_inputs(input: Union[str, list[str]]) -> tuple[list[str], bool]:
        if isinstance(input, str):
            return [input], True
        if not isinstance(input, list) or not all(
            isinstance(item, str) for item in input
        ):
            raise TypeError("Embedding input must be a string or list of strings.")
        return input, False

    async def async_embed(
        self,
        input: Union[str, list[str]],
        *,
        cache: Optional[EmbeddingCache] = None,
    ) -> EmbeddingResult:
        inputs, _ = self._normalize_inputs(input)
        embeddings: list[Optional[list[float]]] = [None] * len(inputs)
        cache_keys: list[Optional[str]] = [None] * len(inputs)
        cache_used = [False] * len(inputs)
        uncached_inputs: list[str] = []
        uncached_positions: list[int] = []

        cache_parameters = {k: v for k, v in self.parameters.items() if v is not None}
        if cache is not None:
            for index, text in enumerate(inputs):
                entry, key = cache.fetch(
                    service_name=self.service_name,
                    model=self.model,
                    parameters=cache_parameters,
                    input=text,
                )
                cache_keys[index] = key
                if entry is None:
                    uncached_inputs.append(text)
                    uncached_positions.append(index)
                else:
                    embeddings[index] = entry.embedding
                    cache_used[index] = True
        else:
            uncached_inputs = list(inputs)
            uncached_positions = list(range(len(inputs)))

        usage = None
        if uncached_inputs:
            if self.remote:
                from edsl.coop import Coop

                result = await Coop().remote_async_embed(
                    self.to_dict(), uncached_inputs
                )
                if "embeddings" not in result:
                    raise ValueError(
                        "Remote embedding response did not include embeddings."
                    )
                new_embeddings = result["embeddings"]
                usage = result.get("usage")
            else:
                service = get_embedding_service(
                    self.service_name, api_key=self.api_key, base_url=self.base_url
                )
                new_embeddings, usage = await service.async_embed(
                    model=self.model,
                    inputs=uncached_inputs,
                    parameters=cache_parameters,
                )

            if len(new_embeddings) != len(uncached_inputs):
                raise ValueError(
                    "Embedding service returned "
                    f"{len(new_embeddings)} embeddings for {len(uncached_inputs)} inputs."
                )
            if any(vector is None for vector in new_embeddings):
                raise ValueError("Embedding service returned a missing embedding.")

            for position, text, vector in zip(
                uncached_positions, uncached_inputs, new_embeddings
            ):
                embeddings[position] = vector
                if cache is not None:
                    cache_keys[position] = cache.store(
                        service_name=self.service_name,
                        model=self.model,
                        parameters=cache_parameters,
                        input=text,
                        embedding=vector,
                        usage=usage,
                    )

        if any(vector is None for vector in embeddings):
            raise ValueError("Embedding result is incomplete.")
        final_embeddings = [vector for vector in embeddings if vector is not None]

        return EmbeddingResult(
            embeddings=final_embeddings,
            input=inputs,
            model=self.model,
            service_name=self.service_name,
            dimensions=len(final_embeddings[0]) if final_embeddings else None,
            usage=usage,
            cache_keys=[key for key in cache_keys],
            cache_used=cache_used,
        )

    @jupyter_nb_handler
    def embed(
        self,
        input: Union[str, list[str]],
        *,
        cache: Optional[EmbeddingCache] = None,
    ) -> EmbeddingResult:
        async def main():
            return await self.async_embed(input, cache=cache)

        return main()

    def to_dict(self, add_edsl_version: bool = True) -> dict[str, Any]:
        data = {
            "model": self.model,
            "service_name": self.service_name,
            "parameters": self.parameters,
            "remote": self.remote,
        }
        if add_edsl_version:
            from edsl import __version__

            data["edsl_version"] = __version__
            data["edsl_class_name"] = self.__class__.__name__
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingModel":
        data = dict(data)
        data.pop("edsl_version", None)
        data.pop("edsl_class_name", None)
        parameters = data.pop("parameters", {})
        model = data.pop("model")
        service_name = data.pop("service_name")
        return cls(model, service_name=service_name, **parameters, **data)

    def __repr__(self) -> str:
        params = {k: v for k, v in self.parameters.items() if v is not None}
        return (
            f"EmbeddingModel(model_name={self.model!r}, "
            f"service_name={self.service_name!r}, parameters={params!r})"
        )
