"""Model discovery service using EDSL API."""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from backend.utils.cache import SimpleCache

logger = logging.getLogger(__name__)

# Fallback models if EDSL unavailable
FALLBACK_MODELS = [
    {"name": "claude-opus-4-5-20251101", "service": "anthropic"},
    {"name": "claude-sonnet-4-5-20250929", "service": "anthropic"},
    {"name": "claude-3-7-sonnet-20250219", "service": "anthropic"},
    {"name": "chatgpt-4o-latest", "service": "openai"},
    {"name": "gpt-4-turbo", "service": "openai"},
    {"name": "gemini-2.5-flash", "service": "google"},
    {"name": "gemini-2.0-flash-exp", "service": "google"},
]

# Curated popular models for quick access
POPULAR_MODELS = [
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929",
    "gpt-4-turbo",
    "chatgpt-4o-latest",
    "gemini-2.5-flash",
    "claude-3-7-sonnet-20250219",
]


class ModelService:
    """Service for discovering and managing LLM models via EDSL."""

    def __init__(self):
        """Initialize model service with 24-hour cache."""
        self._cache = SimpleCache(ttl_hours=24)
        self._cache_key = "edsl_models"

    def get_all_models(self) -> List[Dict[str, str]]:
        """Get all available models from EDSL.

        Returns cached models if available and not expired,
        otherwise fetches from EDSL API.

        Returns:
            List of model dictionaries with 'name' and 'service' keys
        """
        # Try cache first
        cached = self._cache.get(self._cache_key)
        if cached is not None:
            logger.info("Returning cached model list")
            return cached

        # Fetch from EDSL
        try:
            models = self._fetch_from_edsl()
            self._cache.set(self._cache_key, models)
            logger.info(f"Fetched {len(models)} models from EDSL")
            return models
        except Exception as e:
            logger.error(f"Failed to fetch models from EDSL: {e}", exc_info=True)
            logger.warning("Falling back to default model list")
            return FALLBACK_MODELS

    def get_grouped_models(self) -> Dict[str, List[str]]:
        """Get models grouped by service provider.

        Returns:
            Dictionary mapping service names to lists of model names
        """
        all_models = self.get_all_models()
        grouped: Dict[str, List[str]] = {}

        for model in all_models:
            service = model.get("service", "unknown")
            if service not in grouped:
                grouped[service] = []
            grouped[service].append(model["name"])

        # Sort each service's models alphabetically
        for service in grouped:
            grouped[service].sort()

        return grouped

    def get_popular_models(self) -> List[str]:
        """Get curated list of popular models.

        Returns:
            List of popular model names
        """
        # Filter popular models to only those actually available
        all_models = self.get_all_models()
        available_names = {m["name"] for m in all_models}

        return [m for m in POPULAR_MODELS if m in available_names]

    def refresh_cache(self) -> None:
        """Force refresh of model cache from EDSL."""
        self._cache.clear(self._cache_key)
        logger.info("Model cache cleared, will refresh on next request")

    def get_cache_timestamp(self) -> Optional[str]:
        """Get timestamp when models were last cached.

        Returns:
            ISO format timestamp string, or None if not cached
        """
        timestamp = self._cache.get_timestamp(self._cache_key)
        if timestamp:
            return timestamp.isoformat()
        return None

    def _fetch_from_edsl(self) -> List[Dict[str, str]]:
        """Fetch models from EDSL API.

        Returns:
            List of model dictionaries

        Raises:
            Exception: If EDSL import or API call fails
        """
        try:
            from edsl import Model
        except ImportError as e:
            raise Exception(f"EDSL not installed: {e}")

        # Get all available models
        try:
            available_models = Model.available()
        except Exception as e:
            raise Exception(f"Model.available() failed: {e}")

        # Convert to list of dicts
        models = []
        for item in available_models:
            # Handle both dict and object formats
            if isinstance(item, dict):
                model_name = item.get("model", item.get("model_name", ""))
                service_name = item.get("service", item.get("service_name", "unknown"))
            else:
                # Assume it's an object with attributes
                model_name = getattr(item, "model", getattr(item, "model_name", ""))
                service_name = getattr(item, "service", getattr(item, "service_name", "unknown"))

            if model_name:
                models.append({
                    "name": model_name,
                    "service": service_name
                })

        if not models:
            raise Exception("No models returned from EDSL API")

        return models


# Singleton instance
_model_service_instance: Optional[ModelService] = None


def get_model_service() -> ModelService:
    """Get singleton ModelService instance.

    Returns:
        ModelService instance
    """
    global _model_service_instance
    if _model_service_instance is None:
        _model_service_instance = ModelService()
    return _model_service_instance
