from __future__ import annotations

import datetime
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class EmbeddingCacheEntry:
    service_name: str
    model: str
    parameters: dict[str, Any]
    input: str
    embedding: list[float]
    usage: Optional[dict[str, Any]] = None
    timestamp: Optional[int] = None

    @classmethod
    def gen_key(
        cls,
        *,
        service_name: str,
        model: str,
        parameters: dict[str, Any],
        input: str,
    ) -> str:
        payload = {
            "service_name": service_name,
            "model": model,
            "parameters": parameters,
            "input": input,
        }
        return hashlib.md5(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    @property
    def key(self) -> str:
        return self.gen_key(
            service_name=self.service_name,
            model=self.model,
            parameters=self.parameters,
            input=self.input,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_name": self.service_name,
            "model": self.model,
            "parameters": self.parameters,
            "input": self.input,
            "embedding": self.embedding,
            "usage": self.usage,
            "timestamp": self.timestamp
            or int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingCacheEntry":
        return cls(**data)


class EmbeddingCache:
    def __init__(
        self,
        *,
        filename: Optional[str] = None,
        data: Optional[dict[str, EmbeddingCacheEntry]] = None,
        immediate_write: bool = True,
    ):
        if filename and data is not None:
            raise ValueError("Cannot provide both filename and data.")
        self.filename = filename
        self.immediate_write = immediate_write
        self.data: dict[str, EmbeddingCacheEntry] = data or {}
        self.new_entries: dict[str, EmbeddingCacheEntry] = {}
        if filename and os.path.exists(filename):
            self._load_jsonl(filename)

    def _load_jsonl(self, filename: str) -> None:
        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                entry = EmbeddingCacheEntry.from_dict(json.loads(line))
                self.data[entry.key] = entry

    def fetch(
        self,
        *,
        service_name: str,
        model: str,
        parameters: dict[str, Any],
        input: str,
    ) -> tuple[Optional[EmbeddingCacheEntry], str]:
        key = EmbeddingCacheEntry.gen_key(
            service_name=service_name,
            model=model,
            parameters=parameters,
            input=input,
        )
        return self.data.get(key), key

    def store(
        self,
        *,
        service_name: str,
        model: str,
        parameters: dict[str, Any],
        input: str,
        embedding: list[float],
        usage: Optional[dict[str, Any]] = None,
    ) -> str:
        entry = EmbeddingCacheEntry(
            service_name=service_name,
            model=model,
            parameters=parameters,
            input=input,
            embedding=embedding,
            usage=usage,
        )
        key = entry.key
        self.data[key] = entry
        self.new_entries[key] = entry
        if self.immediate_write:
            self.flush()
        return key

    def flush(self) -> None:
        if not self.new_entries:
            return
        if self.filename:
            with open(self.filename, "a", encoding="utf-8") as f:
                for entry in self.new_entries.values():
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        self.new_entries.clear()

    def keys(self) -> list[str]:
        return list(self.data.keys())

    def __len__(self) -> int:
        return len(self.data)
