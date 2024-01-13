from typing import Dict
from edsl.utilities.utilities import is_valid_variable_name


class TraitsDescriptor:
    """ABC for something."""

    def __get__(self, instance, owner):
        """"""
        return instance.__dict__[self.name]

    def __set__(self, instance, traits_dict: Dict[str, str]) -> None:
        for key, value in traits_dict.items():
            if not is_valid_variable_name(key):
                raise Exception("Trait keys must be a valid variable name!")
        instance.__dict__[self.name] = traits_dict

    def __set_name__(self, owner, name: str) -> None:
        self.name = "_" + name


class CodebookDescriptor:
    """ABC for something."""

    def __get__(self, instance, owner):
        """"""
        return instance.__dict__[self.name]

    def __set__(self, instance, codebook_dict: Dict[str, str]) -> None:
        instance.__dict__[self.name] = codebook_dict

    def __set_name__(self, owner, name: str) -> None:
        self.name = "_" + name


class InstructionDescriptor:
    """ABC for something."""

    def __get__(self, instance, owner):
        """"""
        return instance.__dict__[self.name]

    def __set__(self, instance, instruction) -> None:
        instance.__dict__[self.name] = instruction
        instance.set_instructions = instruction != instance.default_instruction

    def __set_name__(self, owner, name: str) -> None:
        self.name = "_" + name
