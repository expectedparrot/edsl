"""
Exceptions specific to the instructions module.

This module defines custom exception classes for all instruction-related errors
in the EDSL framework, ensuring consistent error handling and user feedback.
"""

from ..base import BaseException


class InstructionError(BaseException):
    """
    Base exception class for all instruction-related errors.
    
    This is the parent class for all exceptions related to instruction creation,
    modification, and application.
    
    Examples:
        ```python
        # Usually not raised directly, but through subclasses
        # For example, when creating invalid instructions:
        instruction = Instruction(keep=None, drop=None)  # Would raise InstructionValueError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/instructions.html"


class InstructionValueError(InstructionError):
    """
    Exception raised when invalid values are provided to instruction methods.
    
    This exception occurs when:
    - Both keep and drop parameters are None in an Instruction
    - Invalid instruction options are provided
    - The instruction content is improperly formatted
    
    Examples:
        ```python
        # Creating an instruction with invalid parameters
        instruction = Instruction(keep=None, drop=None)  # Raises InstructionValueError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/instructions.html"


class InstructionCollectionError(InstructionError):
    """
    Exception raised when there's an issue with an instruction collection.
    
    This exception occurs when:
    - Instructions in a collection are invalid or incompatible
    - There's an attempt to add a duplicate instruction
    - The collection is used in an invalid context
    
    Examples:
        ```python
        # Adding an incompatible instruction to a collection
        collection.add(invalid_instruction)  # Raises InstructionCollectionError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/instructions.html"