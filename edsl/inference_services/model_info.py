"""Unified ModelInfo class for inference services."""

from dataclasses import dataclass
from typing import Any, Dict


def _convert_to_dict(obj: Any) -> Any:
    """Recursively convert an object to a dictionary representation."""
    if hasattr(obj, "__dict__"):
        return {k: _convert_to_dict(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, dict):
        return {k: _convert_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_dict(item) for item in obj]
    else:
        return obj


@dataclass
class ModelInfo:
    """Unified model information class for all inference services.

    This class stores raw model data from different API providers and provides
    a common interface for accessing model information.
    """

    service_name: str
    id: str
    raw_data: Dict[str, Any]
    original_class: str

    @classmethod
    def from_raw(cls, obj: Any, service_name: str, model_id: str) -> "ModelInfo":
        """Create a ModelInfo instance from raw API response data.

        Args:
            obj: Raw object from the API (can be any type with __dict__)
            service_name: Name of the inference service (e.g., "openai", "anthropic")

        Returns:
            ModelInfo instance with converted raw data
        """
        raw_data = _convert_to_dict(obj)
        original_class = (
            str(obj.__class__.__name__)
            if hasattr(obj, "__class__")
            else str(type(obj).__name__)
        )

        return cls(
            service_name=service_name,
            id=model_id,
            raw_data=raw_data,
            original_class=original_class,
        )

    @classmethod
    def get_id_from_raw(cls, obj: Any, service_name: str) -> str:
        """Get the model ID from raw service provider data (common across all services)."""
        if not isinstance(obj, dict):
            raw_data = _convert_to_dict(obj)
        else:
            raw_data = obj

        if service_name == "bedrock":
            return raw_data.get("modelId")
        elif service_name == "google":
            base_name = raw_data.get("name")
            if isinstance(base_name, str):
                return base_name.lstrip("models/")
            else:
                return base_name
        else:
            return raw_data.get("id")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the raw data with optional default."""
        return self.raw_data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Support dictionary-like access to raw data."""
        return self.raw_data[key]

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for checking if key exists in raw data."""
        return key in self.raw_data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        """Create a ModelInfo object from a dictionary."""
        if "service_name" not in data:
            raise ValueError("service_name is required")
        if "id" not in data:
            raise ValueError("id is required")
        if "raw_data" not in data:
            raise ValueError("raw_data is required")
        if "original_class" not in data:
            raise ValueError("original_class is required")

        return cls(
            service_name=data["service_name"],
            id=data["id"],
            raw_data=data["raw_data"],
            original_class=data["original_class"],
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the ModelInfo object to a dictionary."""
        return {
            "service_name": self.service_name,
            "id": self.id,
            "raw_data": self.raw_data,
            "original_class": self.original_class,
        }

    # def __repr__(self) -> str:
    #     return f"ModelInfo(service='{self.service_name}', id='{self.id}', class='{self.original_class}')"
