"""Configuration schema using Pydantic models."""

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class LLMConfig(BaseModel):
    """Configuration for an LLM model."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Model identifier (e.g., 'claude-3-5-sonnet-20241022')"
    )
    temperature: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0-2)"
    )


# Alias for backwards compatibility
ModelConfig = LLMConfig


class GameConfig(BaseModel):
    """Configuration for a single game round."""

    model_config = ConfigDict(frozen=True)

    num_storytellers: int = Field(
        default=3,
        ge=2,
        le=5,
        description="Number of storytellers per round"
    )
    num_truth_tellers: int = Field(
        default=2,
        ge=0,
        description="Number of truth-tellers (rest are fibbers)"
    )
    questions_per_storyteller: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Number of questions judge asks each storyteller"
    )
    story_word_min: int = Field(
        default=250,
        ge=50,
        description="Minimum words for story"
    )
    story_word_max: int = Field(
        default=500,
        ge=100,
        description="Maximum words for story"
    )
    answer_word_min: int = Field(
        default=25,
        ge=10,
        description="Minimum words for answer"
    )
    answer_word_max: int = Field(
        default=150,
        ge=25,
        description="Maximum words for answer"
    )
    game_type: Literal["standard", "all_truth", "all_lies", "majority_lies"] = Field(
        default="standard",
        description="Game configuration type"
    )

    @field_validator("num_truth_tellers")
    @classmethod
    def validate_truth_tellers(cls, v, info):
        """Ensure num_truth_tellers is valid for the game config."""
        num_storytellers = info.data.get("num_storytellers", 3)
        if v > num_storytellers:
            raise ValueError(
                f"num_truth_tellers ({v}) cannot exceed num_storytellers ({num_storytellers})"
            )
        return v

    @property
    def num_fibbers(self) -> int:
        """Calculate the number of fibbers."""
        return self.num_storytellers - self.num_truth_tellers


class ConditionConfig(BaseModel):
    """Configuration for a specific experimental condition."""

    model_config = ConfigDict(frozen=True)

    judge_model: LLMConfig = Field(default_factory=LLMConfig)
    storyteller_model: LLMConfig = Field(default_factory=LLMConfig)
    game: GameConfig = Field(default_factory=GameConfig)
    storyteller_strategy: str = Field(
        default="baseline",
        description="Strategy for storytellers"
    )
    judge_question_style: str = Field(
        default="curious",
        description="Question style for judge"
    )
    fact_category: Optional[str] = Field(
        default="science",
        description="Category of facts to use (None for random selection across all categories)"
    )


class ExperimentConfig(BaseModel):
    """Top-level configuration for an experiment."""

    model_config = ConfigDict(frozen=False)  # Allow modification for experiment setup

    name: str = Field(
        default="two_truths_lie_experiment",
        description="Experiment name"
    )
    judge_model: LLMConfig = Field(default_factory=LLMConfig)
    storyteller_model: LLMConfig = Field(default_factory=LLMConfig)
    game: GameConfig = Field(default_factory=GameConfig)
    rounds_per_condition: int = Field(
        default=30,
        ge=1,
        description="Number of rounds per experimental condition"
    )
    strategies: list[str] = Field(
        default=["baseline"],
        description="List of storytelling strategies to test"
    )
    categories: list[str] = Field(
        default=["science"],
        description="List of fact categories to test"
    )
    question_styles: list[str] = Field(
        default=["curious"],
        description="List of judge question styles to test"
    )
    output_dir: str = Field(
        default="results",
        description="Directory to store results"
    )
