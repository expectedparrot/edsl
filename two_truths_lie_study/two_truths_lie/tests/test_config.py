"""Tests for configuration module."""

import pytest
from pydantic import ValidationError

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.schema import ModelConfig, GameConfig, ConditionConfig, ExperimentConfig
from src.config.defaults import get_default_config, get_mvp_config


class TestModelConfig:
    """Tests for ModelConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ModelConfig()
        assert config.name == "claude-3-5-sonnet-20241022"
        assert config.temperature == 1.0

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ModelConfig(name="gpt-4", temperature=0.7)
        assert config.name == "gpt-4"
        assert config.temperature == 0.7

    def test_temperature_bounds(self):
        """Test temperature validation."""
        with pytest.raises(ValidationError):
            ModelConfig(temperature=-0.1)

        with pytest.raises(ValidationError):
            ModelConfig(temperature=2.1)


class TestGameConfig:
    """Tests for GameConfig."""

    def test_default_values(self):
        """Test default game configuration."""
        config = GameConfig()
        assert config.num_storytellers == 3
        assert config.num_truth_tellers == 2
        assert config.num_fibbers == 1
        assert config.game_type == "standard"

    def test_num_fibbers_property(self):
        """Test num_fibbers calculation."""
        config = GameConfig(num_storytellers=3, num_truth_tellers=1)
        assert config.num_fibbers == 2

    def test_truth_tellers_validation(self):
        """Test that num_truth_tellers cannot exceed num_storytellers."""
        with pytest.raises(ValidationError):
            GameConfig(num_storytellers=3, num_truth_tellers=4)

    def test_game_type_values(self):
        """Test valid game type values."""
        for game_type in ["standard", "all_truth", "all_lies", "majority_lies"]:
            config = GameConfig(game_type=game_type)
            assert config.game_type == game_type


class TestConditionConfig:
    """Tests for ConditionConfig."""

    def test_default_condition(self):
        """Test default condition configuration."""
        config = ConditionConfig()
        assert config.storyteller_strategy == "baseline"
        assert config.judge_question_style == "curious"
        assert config.fact_category == "science"


class TestExperimentConfig:
    """Tests for ExperimentConfig."""

    def test_default_config(self):
        """Test default experiment configuration."""
        config = get_default_config()
        assert config.rounds_per_condition == 30
        assert "baseline" in config.strategies

    def test_mvp_config(self):
        """Test MVP experiment configuration."""
        config = get_mvp_config()
        assert config.rounds_per_condition == 1
        assert config.name == "two_truths_lie_mvp"
