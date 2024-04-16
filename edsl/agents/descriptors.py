"""This module contains the descriptors used to set the attributes of the Agent class."""
from typing import Dict
from edsl.utilities.utilities import is_valid_variable_name
from edsl.exceptions.agents import AgentNameError, AgentTraitKeyError


class NameDescriptor:
    """ABC for something."""

    def __get__(self, instance, owner):
        """Return the value of the attribute."""
        return instance.__dict__[self.name]

    def __set__(self, instance, name: str) -> None:
        """Set the value of the attribute."""
        instance.__dict__[self.name] = name

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name


class TraitsDescriptor:
    """ABC for something."""

    def __get__(self, instance, owner):
        """Return the value of the attribute."""
        return instance.__dict__[self.name]

    def __set__(self, instance, traits_dict: Dict[str, str]) -> None:
        """Set the value of the attribute."""
        for key, value in traits_dict.items():
            if key == "name":
                raise AgentNameError(
                    """Trait keys cannot be 'name'. Instead, use the 'name' attribute directly e.g., 
                    Agent(name="my_agent", traits={"trait1": "value1", "trait2": "value2"})
                    """
                )

            if not is_valid_variable_name(key):
                raise AgentTraitKeyError(
                    "Trait keys must be valid Python identifiers (must be alphanumeric, cannot start with a number and must use underscores instead of spaces)."
                )

        instance.__dict__[self.name] = traits_dict

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = name


class CodebookDescriptor:
    """ABC for something."""

    def __get__(self, instance, owner):
        """Return the value of the attribute."""
        return instance.__dict__[self.name]

    def __set__(self, instance, codebook_dict: Dict[str, str]) -> None:
        """Set the value of the attribute."""
        instance.__dict__[self.name] = codebook_dict

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
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
