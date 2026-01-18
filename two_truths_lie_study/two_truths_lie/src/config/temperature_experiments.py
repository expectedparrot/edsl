"""Temperature experiment configurations and utilities.

This module provides pre-configured setups for running temperature experiments
to study the impact of temperature on judge performance.
"""

from typing import List
from .schema import ExperimentConfig, LLMConfig, GameConfig


def get_temperature_sweep_config(
    temperatures: List[float] = None,
    rounds_per_temperature: int = 10,
    strategies: List[str] = None,
    categories: List[str] = None,
    question_styles: List[str] = None
) -> ExperimentConfig:
    """Create an experiment config for temperature sweep.

    This config tests multiple judge temperatures while holding other
    variables constant.

    Args:
        temperatures: List of temperatures to test (default: [0.5, 0.7, 1.0, 1.3, 1.5])
        rounds_per_temperature: Rounds to run per temperature (default: 10)
        strategies: Storyteller strategies to test (default: ["baseline"])
        categories: Fact categories to test (default: ["science"])
        question_styles: Judge question styles to test (default: ["curious"])

    Returns:
        ExperimentConfig configured for temperature sweep

    Example:
        >>> config = get_temperature_sweep_config(
        ...     temperatures=[0.5, 1.0, 1.5],
        ...     rounds_per_temperature=20
        ... )
        >>> # This will run 60 rounds total (3 temps × 20 rounds)
    """
    if temperatures is None:
        temperatures = [0.5, 0.7, 1.0, 1.3, 1.5]

    if strategies is None:
        strategies = ["baseline"]

    if categories is None:
        categories = ["science"]

    if question_styles is None:
        question_styles = ["curious"]

    # We can't directly set multiple temperatures in ExperimentConfig
    # Instead, caller should run this config multiple times with different judge temps
    # This is a template config - actual execution requires iteration

    return ExperimentConfig(
        name="temperature_sweep",
        judge_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0),
        storyteller_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0),
        game=GameConfig(),
        rounds_per_condition=rounds_per_temperature,
        strategies=strategies,
        categories=categories,
        question_styles=question_styles,
        output_dir="results/temperature_sweep"
    )


def get_low_temperature_config(rounds: int = 30) -> ExperimentConfig:
    """Get config for low-temperature judge experiments.

    Low temperature (0.3) makes the judge more deterministic and focused.
    Use this to test if lower randomness improves detection.

    Args:
        rounds: Number of rounds to run (default: 30)

    Returns:
        ExperimentConfig with temperature=0.3 for judge
    """
    return ExperimentConfig(
        name="low_temperature_judge",
        judge_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=0.3),
        storyteller_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0),
        game=GameConfig(),
        rounds_per_condition=rounds,
        strategies=["baseline"],
        categories=["science"],
        question_styles=["curious"],
        output_dir="results/low_temp"
    )


def get_high_temperature_config(rounds: int = 30) -> ExperimentConfig:
    """Get config for high-temperature judge experiments.

    High temperature (1.5) makes the judge more creative and exploratory.
    Use this to test if increased randomness helps detect subtle patterns.

    Args:
        rounds: Number of rounds to run (default: 30)

    Returns:
        ExperimentConfig with temperature=1.5 for judge
    """
    return ExperimentConfig(
        name="high_temperature_judge",
        judge_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.5),
        storyteller_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0),
        game=GameConfig(),
        rounds_per_condition=rounds,
        strategies=["baseline"],
        categories=["science"],
        question_styles=["curious"],
        output_dir="results/high_temp"
    )


def get_temperature_comparison_configs() -> List[ExperimentConfig]:
    """Get a set of configs for comprehensive temperature comparison.

    Returns three configs (low, medium, high temperature) for side-by-side
    comparison of judge performance.

    Returns:
        List of 3 ExperimentConfigs with different temperatures

    Example:
        >>> configs = get_temperature_comparison_configs()
        >>> # Run each config separately and compare results
        >>> for config in configs:
        ...     runner.run_experiment(config)
    """
    return [
        get_low_temperature_config(rounds=30),
        ExperimentConfig(
            name="medium_temperature_judge",
            judge_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0),
            storyteller_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0),
            game=GameConfig(),
            rounds_per_condition=30,
            strategies=["baseline"],
            categories=["science"],
            question_styles=["curious"],
            output_dir="results/medium_temp"
        ),
        get_high_temperature_config(rounds=30),
    ]


# Temperature recommendations based on use case
TEMPERATURE_RECOMMENDATIONS = {
    "deterministic": 0.3,     # Most consistent, focused reasoning
    "balanced": 0.7,          # Good balance of consistency and creativity
    "default": 1.0,           # Standard Claude default
    "creative": 1.3,          # More exploratory, less constrained
    "exploratory": 1.5,       # Maximum creativity, less predictable
}


def get_recommended_temperature_config(
    use_case: str,
    rounds: int = 30
) -> ExperimentConfig:
    """Get a config with recommended temperature for a use case.

    Args:
        use_case: One of "deterministic", "balanced", "default", "creative", "exploratory"
        rounds: Number of rounds to run

    Returns:
        ExperimentConfig with appropriate temperature

    Raises:
        ValueError: If use_case is not recognized
    """
    if use_case not in TEMPERATURE_RECOMMENDATIONS:
        valid_cases = ", ".join(TEMPERATURE_RECOMMENDATIONS.keys())
        raise ValueError(f"Unknown use case: {use_case}. Must be one of: {valid_cases}")

    temp = TEMPERATURE_RECOMMENDATIONS[use_case]

    return ExperimentConfig(
        name=f"judge_temp_{use_case}",
        judge_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=temp),
        storyteller_model=LLMConfig(name="claude-3-5-haiku-20241022", temperature=1.0),
        game=GameConfig(),
        rounds_per_condition=rounds,
        strategies=["baseline"],
        categories=["science"],
        question_styles=["curious"],
        output_dir=f"results/temp_{use_case}"
    )
