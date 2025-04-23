"""
The conversation module provides tools for simulating conversations between agents.

It includes classes for managing dialogues, tracking statements, and controlling
conversation flow between multiple participants.
"""

from .Conversation import Conversation, ConversationList, AgentStatement, AgentStatements
from .exceptions import ConversationError, ConversationValueError, ConversationStateError
from .next_speaker_utilities import (
    default_turn_taking_generator,
    turn_taking_generator_with_focal_speaker,
    random_turn_taking_generator,
    random_inclusive_generator,
    speaker_closure,
)

__all__ = [
    "Conversation",
    "ConversationList",
    "AgentStatement",
    "AgentStatements",
    "ConversationError",
    "ConversationValueError",
    "ConversationStateError",
    "default_turn_taking_generator",
    "turn_taking_generator_with_focal_speaker",
    "random_turn_taking_generator",
    "random_inclusive_generator",
    "speaker_closure",
]