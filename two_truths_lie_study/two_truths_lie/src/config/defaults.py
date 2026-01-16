"""Default configurations for Two Truths and a Lie game."""

from .schema import ModelConfig, GameConfig, ExperimentConfig


def get_default_config() -> ExperimentConfig:
    """Get the default experiment configuration."""
    return ExperimentConfig(
        name="two_truths_lie_default",
        judge_model=ModelConfig(
            name="claude-3-5-sonnet-20241022",
            temperature=1.0
        ),
        storyteller_model=ModelConfig(
            name="claude-3-5-sonnet-20241022",
            temperature=1.0
        ),
        game=GameConfig(
            num_storytellers=3,
            num_truth_tellers=2,
            questions_per_storyteller=3,
            story_word_min=250,
            story_word_max=500,
            answer_word_min=25,
            answer_word_max=150,
            game_type="standard"
        ),
        rounds_per_condition=30,
        strategies=["baseline"],
        categories=["science"],
        question_styles=["curious"],
        output_dir="results"
    )


def get_mvp_config() -> ExperimentConfig:
    """Get the MVP configuration for initial testing.

    This is a minimal configuration for testing the game mechanics
    with Claude-only, single strategy, and reduced rounds.
    """
    return ExperimentConfig(
        name="two_truths_lie_mvp",
        judge_model=ModelConfig(
            name="claude-3-5-sonnet-20241022",
            temperature=1.0
        ),
        storyteller_model=ModelConfig(
            name="claude-3-5-sonnet-20241022",
            temperature=1.0
        ),
        game=GameConfig(
            num_storytellers=3,
            num_truth_tellers=2,
            questions_per_storyteller=3,
            story_word_min=250,
            story_word_max=500,
            answer_word_min=25,
            answer_word_max=150,
            game_type="standard"
        ),
        rounds_per_condition=1,  # Single round for MVP testing
        strategies=["baseline"],
        categories=["science"],
        question_styles=["curious"],
        output_dir="results"
    )
