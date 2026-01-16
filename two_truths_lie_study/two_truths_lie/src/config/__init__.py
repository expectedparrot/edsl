"""Configuration module for Two Truths and a Lie."""

from .schema import ModelConfig, GameConfig, ExperimentConfig, ConditionConfig
from .defaults import get_default_config, get_mvp_config

__all__ = [
    "ModelConfig",
    "GameConfig",
    "ExperimentConfig",
    "ConditionConfig",
    "get_default_config",
    "get_mvp_config",
]
