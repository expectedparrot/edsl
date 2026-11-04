"""Models that evaluate context against typed questions instead of generating text."""

from __future__ import annotations

import asyncio
import math
import os
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class JudgmentCapabilities:
    primitives: frozenset[str] = frozenset({"choice", "score", "binary"})
    batching: bool = True
    max_options: int = 255
    max_levels: int = 10
    # Conservative UTF-8 JSON byte budgets, not tokenizer estimates. Leave
    # headroom below the documented 64k total / 32k state+question token limits.
    max_request_bytes: int = 60_000
    max_context_bytes: int = 30_000


class JudgmentModel:
    """A typed judgment provider. No credentials or network calls at construction.

    Provider implementations can subclass this class and override ``capabilities``
    and ``async_evaluate``. Register them for serialization with ``register``.
    """

    capabilities = JudgmentCapabilities()
    _providers: dict[str, type[JudgmentModel]] = {}

    def __init__(self, model: str = "jev-latest", service_name: str = "typesafe"):
        if not isinstance(model, str) or not model:
            raise ValueError("model must be a nonempty string")
        if service_name != "typesafe" and service_name not in self._providers:
            raise ValueError(f"Unknown judgment service: {service_name!r}")
        self.model = model
        self.service_name = service_name
        self._inference_service_ = service_name
        self.parameters = {}

    def __new__(cls, model="jev-latest", service_name="typesafe"):
        if cls is JudgmentModel and service_name in cls._providers:
            return object.__new__(cls._providers[service_name])
        return object.__new__(cls)

    @classmethod
    def register(cls, service_name: str, provider: type[JudgmentModel]):
        if not issubclass(provider, JudgmentModel):
            raise TypeError("provider must subclass JudgmentModel")
        if service_name == "typesafe":
            raise ValueError("Cannot replace the built-in typesafe provider")
        cls._providers[service_name] = provider

    async def async_evaluate(self, state: dict, questions: dict, *, client):
        """Return a provider-neutral batch response using an execution-owned client.

        Binary requests/responses use ``binary`` and ``probability`` internally;
        the TypeSafe adapter translates their Noul representation here.
        """
        key = os.environ.get("TYPESAFE_API_KEY")
        if not key:
            raise ValueError("Set TYPESAFE_API_KEY to execute TypeSafe evaluations")
        wire_questions = {
            name: {
                **question,
                "type": "noul" if question["type"] == "binary" else question["type"],
            }
            for name, question in questions.items()
        }
        for attempt in range(4):
            try:
                response = await client.post(
                    "https://api.typesafe.ai/v1/systemone",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": self.model,
                        "state": state,
                        "questions": wire_questions,
                    },
                )
            except httpx.TransportError:
                if attempt == 3:
                    raise RuntimeError(
                        "TypeSafe transport failed after retries"
                    ) from None
                await asyncio.sleep(2**attempt)
                continue
            if response.status_code in {429, 500, 502, 503, 504, 529} and attempt < 3:
                try:
                    delay = float(response.headers.get("retry-after", 2**attempt))
                    if not math.isfinite(delay) or delay < 0:
                        raise ValueError
                except ValueError:
                    delay = 2**attempt
                await asyncio.sleep(delay)
                continue
            if response.is_error:
                # Do not include headers, credentials, or provider-echoed content.
                raise RuntimeError(
                    f"TypeSafe evaluation failed (HTTP {response.status_code})"
                )
            data = response.json()
            for answer in data.get("answers", {}).values():
                if answer.get("type") == "noul":
                    answer["type"] = "binary"
                    answer["probability"] = answer.pop("noul")
                # Live TypeSafe responses sometimes contain quantized vectors
                # totaling 0.99 or 1.01. Repair only this bounded discrepancy,
                # preserving the exact provider vector and adjustment for audit.
                probabilities = answer.get("probabilities")
                if isinstance(probabilities, dict) and probabilities:
                    values = list(probabilities.values())
                    if all(
                        not isinstance(p, bool)
                        and isinstance(p, (int, float))
                        and math.isfinite(p)
                        and 0 <= p <= 1
                        for p in values
                    ):
                        total = math.fsum(values)
                        error = abs(total - 1)
                        if 1e-6 < error <= 0.01 + 1e-9:
                            answer["reported_probabilities"] = probabilities
                            answer["probability_normalization"] = {
                                "method": "divide_by_reported_total",
                                "reported_total": total,
                                "maximum_mass_error": 0.01,
                            }
                            answer["probabilities"] = {
                                key: value / total
                                for key, value in probabilities.items()
                            }
            return data

    def to_dict(self, add_edsl_version=True):
        # Keep the discriminator even when version metadata is omitted.
        data = {
            "model_kind": "judgment",
            "model": self.model,
            "service_name": self.service_name,
            "parameters": self.parameters,
        }
        if add_edsl_version:
            from edsl import __version__

            data.update(edsl_class_name="JudgmentModel", edsl_version=__version__)
        return data

    @classmethod
    def from_dict(cls, data):
        return cls(data["model"], service_name=data["service_name"])

    def __repr__(self):
        return f"JudgmentModel({self.model!r}, service_name={self.service_name!r})"
