"""Unified ModelInfo class for inference services."""

from dataclasses import dataclass
from typing import Any, Dict


def _convert_to_dict(obj: Any) -> Any:
    """Recursively convert an object to a dictionary representation."""
    if hasattr(obj, '__dict__'):
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
    raw_data: Dict[str, Any]
    original_class: str
    
    @classmethod
    def from_raw(cls, obj: Any, service_name: str) -> "ModelInfo":
        """Create a ModelInfo instance from raw API response data.
        
        Args:
            obj: Raw object from the API (can be any type with __dict__)
            service_name: Name of the inference service (e.g., "openai", "anthropic")
            
        Returns:
            ModelInfo instance with converted raw data
        """
        raw_data = _convert_to_dict(obj)
        original_class = obj.__class__.__name__ if hasattr(obj, '__class__') else type(obj).__name__
        
        return cls(
            service_name=service_name,
            raw_data=raw_data,
            original_class=original_class
        )
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the raw data with optional default."""
        return self.raw_data.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Support dictionary-like access to raw data."""
        return self.raw_data[key]
    
    def __contains__(self, key: str) -> bool:
        """Support 'in' operator for checking if key exists in raw data."""
        return key in self.raw_data
    
    @property
    def id(self) -> str:
        """Get the model ID from raw data (common across all services)."""
        # Most services use 'id', but some might use 'name'
        if not isinstance(self.raw_data, dict):
            raise TypeError(
                f"ModelInfo.raw_data expected dict, got {type(self.raw_data).__name__}: {repr(self.raw_data)}. "
                f"Service: {self.service_name}, Original class: {self.original_class}"
            )
        return self.raw_data.get('id') or self.raw_data.get('name', '')
    
    def __repr__(self) -> str:
        return f"ModelInfo(service='{self.service_name}', id='{self.id}', class='{self.original_class}')"