"""Agent helper modules for supporting Agent functionality.

This package contains helper classes that support the Agent class,
including trait management, serialization, combination, and various
agent operations.
"""

from .descriptors import (
    TraitsDescriptor,
    CodebookDescriptor,
    InstructionDescriptor,
    NameDescriptor,
)
from .agent_combination import AgentCombination
from .agent_delta import AgentDelta
from .agent_direct_answering import AgentDirectAnswering
from .agent_dynamic_traits import AgentDynamicTraits
from .agent_from_result import AgentFromResult
from .agent_instructions import AgentInstructions
from .agent_invigilator import AgentInvigilator
from .agent_operations import AgentOperations
from .agent_prompt import AgentPrompt
from .agent_serialization import AgentSerialization
from .agent_table import AgentTable
from .agent_trait_manager import AgentTraitManager
from .agent_traits import AgentTraits
from .agent_traits_manager import AgentTraitsManager

__all__ = [
    "TraitsDescriptor",
    "CodebookDescriptor",
    "InstructionDescriptor",
    "NameDescriptor",
    "AgentCombination",
    "AgentDelta",
    "AgentDirectAnswering",
    "AgentDynamicTraits",
    "AgentFromResult",
    "AgentInstructions",
    "AgentInvigilator",
    "AgentOperations",
    "AgentPrompt",
    "AgentSerialization",
    "AgentTable",
    "AgentTraitManager",
    "AgentTraits",
    "AgentTraitsManager",
]
