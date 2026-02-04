"""
Clean configuration management for the vibe system.
"""

from dataclasses import dataclass, field
from typing import List, Any, Optional, Callable
from datetime import datetime

from .prompts.prompt_builder import PromptBuilder


@dataclass
class VibeChange:
    """Records a change made by the vibe processor."""

    question_name: str
    change_type: str  # 'text', 'options', 'type'
    original_value: Any
    new_value: Any
    reasoning: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "question_name": self.question_name,
            "change_type": self.change_type,
            "original_value": self.original_value,
            "new_value": self.new_value,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VibeConfig:
    """Configuration for vibe processing."""

    # Core functionality
    enabled: bool = True

    # AI model configuration
    model: Optional[str] = None  # Use default model if None
    temperature: float = 0.1  # Low temperature for consistent results

    # Processing configuration
    max_concurrent: int = 5
    timeout_seconds: int = 30

    # Logging configuration
    enable_logging: bool = True
    log_changes: bool = True  # Log individual changes with diffs
    verbose_logging: bool = False  # Include full analysis details

    # Advanced configuration
    custom_analyzers: Optional[List[Callable]] = None

    def __post_init__(self):
        """Initialize prompt builder after dataclass initialization."""
        self._prompt_builder = PromptBuilder()

    @property
    def system_prompt(self) -> str:
        """Get the system prompt from the prompt builder."""
        return self._prompt_builder.system_prompt

    def build_analysis_prompt(
        self, question_info: dict[str, Any], edsl_info: str
    ) -> str:
        """Build analysis prompt using the prompt builder."""
        return self._prompt_builder.build_analysis_prompt(question_info, edsl_info)
