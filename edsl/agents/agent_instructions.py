"""Agent instructions functionality.

This module provides the AgentInstructions class that handles instruction management
for Agent instances, including initialization and validation.
"""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Agent


class AgentInstructions:
    """Handles instruction management for Agent instances.
    
    This class provides methods to initialize and manage agent instructions,
    including handling default instructions and custom instruction validation.
    """

    def __init__(self, agent: "Agent"):
        """Initialize the AgentInstructions manager.
        
        Args:
            agent: The agent instance this manager belongs to
        """
        self.agent = agent

    def initialize(self, instruction: Optional[str]) -> None:
        """Initialize the instruction for how the agent should answer questions.

        If no instruction is provided, uses the default instruction.

        Args:
            instruction: Directive for how the agent should answer questions

        Examples:
            Using default instruction:

            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 30})
            >>> agent.instruction == Agent.default_instruction
            True
            >>> agent.set_instructions
            False

            Using custom instruction:

            >>> agent = Agent(traits={"age": 30}, instruction="Be helpful and friendly")
            >>> agent.instruction
            'Be helpful and friendly'
            >>> agent.set_instructions
            True
        """
        if instruction is None:
            self.agent.instruction = self.agent.default_instruction
            self.agent._instruction = self.agent.default_instruction
            self.agent.set_instructions = False
        else:
            self.agent.instruction = instruction
            self.agent._instruction = instruction
            self.agent.set_instructions = True

    def is_default_instruction(self) -> bool:
        """Check if the agent is using the default instruction.
        
        Returns:
            True if using default instruction, False otherwise
            
        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 30})
            >>> agent.instructions.is_default_instruction()
            True
            
            >>> agent_custom = Agent(traits={"age": 30}, instruction="Custom instruction")
            >>> agent_custom.instructions.is_default_instruction()
            False
        """
        return self.agent.instruction == self.agent.default_instruction

    def update_instruction(self, new_instruction: str) -> None:
        """Update the agent's instruction.
        
        Args:
            new_instruction: The new instruction to set
            
        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 30})
            >>> agent.instructions.update_instruction("Be creative and thoughtful")
            >>> agent.instruction
            'Be creative and thoughtful'
            >>> agent.set_instructions
            True
        """
        self.agent.instruction = new_instruction
        self.agent._instruction = new_instruction
        self.agent.set_instructions = new_instruction != self.agent.default_instruction

    def reset_to_default(self) -> None:
        """Reset the agent's instruction to the default.
        
        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 30}, instruction="Custom instruction")
            >>> agent.instructions.reset_to_default()
            >>> agent.instruction == Agent.default_instruction
            True
            >>> agent.set_instructions
            False
        """
        self.agent.instruction = self.agent.default_instruction
        self.agent._instruction = self.agent.default_instruction
        self.agent.set_instructions = False

    def get_effective_instruction(self) -> str:
        """Get the effective instruction that will be used.
        
        This method provides a way to get the current instruction that will
        actually be used by the agent, which is useful for debugging and
        introspection.
        
        Returns:
            The current instruction string
            
        Examples:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={"age": 30})
            >>> instruction = agent.instructions.get_effective_instruction()
            >>> instruction == Agent.default_instruction
            True
        """
        return self.agent.instruction 