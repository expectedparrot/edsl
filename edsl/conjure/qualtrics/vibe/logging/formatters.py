"""
Log formatters for consistent vibe logging output.
"""

from typing import Any, Dict, List


class VibeLogFormatter:
    """Formatter for vibe log messages."""

    def format_conversion_params(
        self, target_type: str, params: Dict[str, Any]
    ) -> List[str]:
        """Format conversion parameters for logging."""
        lines = []

        if target_type == "QuestionNumerical":
            lines.extend(self._format_numerical_params(params))
        elif target_type == "QuestionLinearScale":
            lines.extend(self._format_linear_scale_params(params))
        else:
            # Generic parameter formatting
            lines.append(f"📋 Parameters: {params}")

        return lines

    def _format_numerical_params(self, params: Dict[str, Any]) -> List[str]:
        """Format numerical converter parameters."""
        lines = []

        constraints = []
        if "min_value" in params:
            constraints.append(f"min={params['min_value']}")
        if "max_value" in params:
            constraints.append(f"max={params['max_value']}")

        if constraints:
            constraint_str = f" with {', '.join(constraints)}"
            lines.append(f"📊 Creating numerical question{constraint_str}")
        else:
            lines.append("📊 Creating numerical question")

        return lines

    def _format_linear_scale_params(self, params: Dict[str, Any]) -> List[str]:
        """Format linear scale converter parameters."""
        lines = []

        options = params.get("question_options", [])
        labels = params.get("option_labels", {})

        lines.append(f"📏 Scale: {options}")

        if labels:
            min_val, max_val = min(options), max(options)
            if min_val in labels and max_val in labels:
                lines.append(f"🏷️  Using complete endpoint labels: {labels}")
            else:
                lines.append(f"⚠️  Incomplete labels found: {labels}")
                lines.append(
                    "⚠️  QuestionLinearScale requires labels for both endpoints or none"
                )
                lines.append("⚠️  Skipping labels to avoid validation error")

        return lines

    def format_error_message(
        self, error_type: str, question_name: str, details: str
    ) -> str:
        """Format error messages consistently."""
        return f"❌ {error_type} error in {question_name}: {details}"

    def format_success_message(self, operation: str, question_name: str) -> str:
        """Format success messages consistently."""
        return f"✅ {operation} successful for {question_name}"
