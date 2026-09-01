from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class EmbeddingResult:
    embeddings: list[list[float]]
    input: list[str]
    model: str
    service_name: str
    dimensions: Optional[int] = None
    usage: Optional[dict[str, Any]] = None
    cache_keys: Optional[list[Optional[str]]] = None
    cache_used: Optional[list[bool]] = None

    def to_dict(self, add_edsl_version: bool = True) -> dict[str, Any]:
        data = {
            "embeddings": self.embeddings,
            "input": self.input,
            "model": self.model,
            "service_name": self.service_name,
            "dimensions": self.dimensions,
            "usage": self.usage,
            "cache_keys": self.cache_keys,
            "cache_used": self.cache_used,
        }
        if add_edsl_version:
            from edsl import __version__

            data["edsl_version"] = __version__
            data["edsl_class_name"] = self.__class__.__name__
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingResult":
        data = dict(data)
        data.pop("edsl_version", None)
        data.pop("edsl_class_name", None)
        return cls(**data)

    def to_dataset(self):
        from edsl.dataset import Dataset

        return Dataset(
            [
                {"input": self.input},
                {"embedding": self.embeddings},
                {"model": [self.model] * len(self.input)},
                {"service_name": [self.service_name] * len(self.input)},
                {"dimensions": [self.dimensions] * len(self.input)},
                {"cache_key": self.cache_keys or [None] * len(self.input)},
                {"cache_used": self.cache_used or [False] * len(self.input)},
            ]
        )

    def to_scenario_list(self):
        return self.to_dataset().to_scenario_list()

    def __len__(self) -> int:
        return len(self.embeddings)

    def __getitem__(self, index: int) -> list[float]:
        return self.embeddings[index]
