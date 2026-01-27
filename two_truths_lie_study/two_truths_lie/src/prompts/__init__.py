"""Prompt templates for Two Truths and a Lie game."""

from .base import BasePrompt
from .storyteller import TruthTellerPrompt, FibberPrompt, StorytellerAnswerPrompt
from .judge import JudgeReviewPrompt, JudgeQuestionPrompt, JudgeVerdictPrompt, JudgeIntermediateGuessPrompt
from .strategies import STRATEGIES, get_strategy_instructions

__all__ = [
    "BasePrompt",
    "TruthTellerPrompt",
    "FibberPrompt",
    "StorytellerAnswerPrompt",
    "JudgeReviewPrompt",
    "JudgeQuestionPrompt",
    "JudgeVerdictPrompt",
    "JudgeIntermediateGuessPrompt",
    "STRATEGIES",
    "get_strategy_instructions",
]
