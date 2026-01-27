"""Model validation service for experiment configurations."""

from typing import Dict, List, Optional, Tuple
import logging

from backend.services.model_service import get_model_service

logger = logging.getLogger(__name__)


class ModelValidator:
    """Validates model availability and provides suggestions."""

    def __init__(self):
        """Initialize validator with model service."""
        self.model_service = get_model_service()

    def validate_model(self, model_name: str) -> Tuple[bool, Optional[str]]:
        """Validate if a model exists in EDSL catalog.

        Args:
            model_name: Name of the model to validate

        Returns:
            Tuple of (is_valid, error_message)
            If valid, error_message is None
        """
        all_models = self.model_service.get_all_models()
        model_names = {m["name"] for m in all_models}

        if model_name in model_names:
            return True, None

        # Model not found - provide helpful error
        error_msg = f"Model '{model_name}' not found in EDSL catalog"

        # Try to suggest alternatives
        suggestions = self._find_similar_models(model_name, model_names)
        if suggestions:
            error_msg += f". Did you mean: {', '.join(suggestions[:3])}?"

        return False, error_msg

    def validate_experiment_config(self, config: Dict) -> Dict[str, any]:
        """Validate all models in an experiment configuration.

        Args:
            config: Experiment configuration dictionary

        Returns:
            Validation result with keys:
            - valid: Boolean indicating if all models are valid
            - errors: List of error messages
            - warnings: List of warning messages
        """
        errors = []
        warnings = []

        # Check storyteller model
        if "storytellerModel" in config:
            is_valid, error = self.validate_model(config["storytellerModel"])
            if not is_valid:
                errors.append(f"Storyteller: {error}")

        # Check judge model
        if "judgeModel" in config:
            is_valid, error = self.validate_model(config["judgeModel"])
            if not is_valid:
                errors.append(f"Judge: {error}")

        # Check if models are the same (warning, not error)
        if (config.get("storytellerModel") == config.get("judgeModel") and
            config.get("storytellerModel") is not None):
            warnings.append(
                "Storyteller and Judge are using the same model. "
                "This may reduce diversity in experiment results."
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def suggest_alternatives(
        self,
        model_name: str,
        count: int = 3
    ) -> List[str]:
        """Suggest alternative models similar to the given model.

        Args:
            model_name: Original model name
            count: Number of suggestions to return

        Returns:
            List of suggested model names
        """
        all_models = self.model_service.get_all_models()
        model_names = {m["name"] for m in all_models}

        return self._find_similar_models(model_name, model_names, count)

    def _find_similar_models(
        self,
        target: str,
        available: set,
        count: int = 3
    ) -> List[str]:
        """Find similar model names using string similarity.

        Args:
            target: Target model name
            available: Set of available model names
            count: Number of suggestions

        Returns:
            List of similar model names
        """
        # Extract key parts from target
        target_lower = target.lower()
        target_parts = set(target_lower.replace("-", " ").split())

        # Score each available model
        scored = []
        for model in available:
            model_lower = model.lower()
            model_parts = set(model_lower.replace("-", " ").split())

            # Calculate similarity score
            common_parts = target_parts & model_parts
            score = len(common_parts)

            # Bonus for containing target substring
            if target_lower in model_lower or model_lower in target_lower:
                score += 5

            # Bonus for same service (if detectable)
            if self._extract_service(target) == self._extract_service(model):
                score += 2

            if score > 0:
                scored.append((score, model))

        # Sort by score (descending) and return top N
        scored.sort(reverse=True, key=lambda x: x[0])
        return [model for _, model in scored[:count]]

    def _extract_service(self, model_name: str) -> Optional[str]:
        """Extract likely service provider from model name.

        Args:
            model_name: Model name

        Returns:
            Service name if detectable, None otherwise
        """
        model_lower = model_name.lower()

        if "claude" in model_lower or "anthropic" in model_lower:
            return "anthropic"
        elif "gpt" in model_lower or "chatgpt" in model_lower or "openai" in model_lower:
            return "openai"
        elif "gemini" in model_lower or "gemma" in model_lower:
            return "google"
        elif "mistral" in model_lower:
            return "mistral"
        elif "llama" in model_lower:
            return "meta"
        elif "grok" in model_lower:
            return "xai"

        return None


# Singleton instance
_validator_instance: Optional[ModelValidator] = None


def get_model_validator() -> ModelValidator:
    """Get singleton ModelValidator instance.

    Returns:
        ModelValidator instance
    """
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = ModelValidator()
    return _validator_instance
