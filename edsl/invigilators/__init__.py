"""
The invigilators module handles the administration of questions to agents.

An invigilator (from the Latin "to watch over") is responsible for administering
questions to agents, managing the interaction between questions, language models,
and agents, and validating responses. This module is a core part of EDSL's architecture
for ensuring that questions are properly presented to agents and responses are
appropriately processed.

Technical architecture:
- InvigilatorBase: Abstract base class defining the core interface for invigilators
- PromptConstructor: Transforms questions, scenarios, and agent memory into prompts
- QuestionTemplateReplacementsBuilder: Handles template variable substitution
- PromptHelpers: Utilities for prompt construction and manipulation

Invigilator implementations:
- InvigilatorAI: Administers questions to AI agents via language models
- InvigilatorHuman: Handles questions to be answered by human users
- InvigilatorFunctional: Uses custom functions to generate responses

This module is primarily intended for EDSL developers or advanced users who need
to customize the question administration process. Most users interact with invigilators
indirectly through the Survey, Question, and Jobs interfaces.

Design considerations:
- Separation of prompt construction from response handling
- Support for different agents and response types
- Asynchronous execution for efficient processing
- Extensibility through the abstract base class
"""

from .invigilators import InvigilatorAI
from .invigilators import InvigilatorHuman
from .invigilator_base import InvigilatorBase
from .invigilators import InvigilatorFunctional
from .prompt_constructor import PromptConstructor

__all__ = [
    'InvigilatorAI',
    'InvigilatorHuman',
    'InvigilatorBase',
    'InvigilatorFunctional',
    'PromptConstructor'
]