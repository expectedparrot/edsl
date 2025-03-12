"""This module contains the descriptors used to set the attributes of the Agent class."""

from typing import Dict
from .exceptions import AgentNameError, AgentTraitKeyError


def convert_agent_name(x):
    # potentially a numpy int64
    import numpy as np

    if isinstance(x, np.int64):
        return int(x)
    elif x is None:
        return None
    elif isinstance(x, int):
        return x
    else:
        return str(x)


class NameDescriptor:
    """Valid agent name descriptor."""

    def __get__(self, instance, owner):
        """Return the value of the attribute."""
        return instance.__dict__[self.name]

    def __set__(self, instance, name: str) -> None:
        """Set the value of the attribute."""
        instance.__dict__[self.name] = convert_agent_name(name)

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name


class TraitsDescriptor:
    """Traits descriptor."""

    def __get__(self, instance, owner):
        """Return the value of the attribute."""
        return instance.__dict__[self.name]

    def __set__(self, instance, traits_dict: Dict[str, str]) -> None:
        """Set the value of the attribute."""
        from ..utilities.utilities import is_valid_variable_name

        for key, value in traits_dict.items():
            if key == "name":
                raise AgentNameError(
                    "Trait keys cannot be 'name'. Instead, use the 'name' attribute directly e.g.,\n"
                    'Agent(name="my_agent", traits={"trait1": "value1", "trait2": "value2"})'
                )

            if not is_valid_variable_name(key):
                raise AgentTraitKeyError(
                    f"""Trait keys must be valid Python identifiers (must be alphanumeric, cannot start with a number and must use underscores instead of spaces).
                    You passed: {key}
                    """
                )

        instance.__dict__[self.name] = traits_dict

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = name


class CodebookDescriptor:
    """Descriptor for the Agent's codebook attribute.
    
    A codebook provides human-readable descriptions for trait keys, allowing traits
    to be presented in a more understandable format in prompts. The codebook is a
    dictionary mapping trait keys to their descriptive text.
    
    For example, a trait key like 'age' might have a codebook description of
    'Age in years', making prompts more natural and clear.
    
    Example:
        >>> # Agent would typically be imported from edsl.agents
        >>> # For doctests, we'll just demonstrate the descriptor behavior
        >>> class TestObject:
        ...     codebook = CodebookDescriptor()
        >>> test_obj = TestObject()
        >>> test_obj.codebook = {'age': 'Age in years'}
        >>> test_obj.codebook
        {'age': 'Age in years'}
        >>> test_obj.codebook = {'age': 'How old they are'}
        >>> test_obj.codebook
        {'age': 'How old they are'}
    """

    def __get__(self, instance, owner):
        """Return the codebook dictionary.
        
        Args:
            instance: The instance object
            owner: The class
            
        Returns:
            dict: The codebook dictionary mapping trait keys to descriptions
        """
        return instance.__dict__[self.name]

    def __set__(self, instance, codebook_dict: Dict[str, str]) -> None:
        """Set the codebook dictionary.
        
        Args:
            instance: The instance object
            codebook_dict: Dictionary mapping trait keys to descriptions
        """
        instance.__dict__[self.name] = codebook_dict

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute in the instance's dictionary.
        
        Args:
            owner: The class
            name: The name of the attribute
        """
        self.name = "_" + name


class InstructionDescriptor:
    """ABC for something."""

    def __get__(self, instance, owner):
        """Return the value of the attribute."""
        return instance.__dict__[self.name]

    def __set__(self, instance, instruction) -> None:
        """Set the value of the attribute."""
        instance.__dict__[self.name] = instruction
        instance.set_instructions = instruction != instance.default_instruction

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name
