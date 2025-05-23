"""Human module for representing real human participants.

This module provides classes to represent human participants in research studies,
interviews, and surveys. It includes:

- Human: A class representing an individual human participant
- HumanList: A collection of Human objects
- Exceptions: Custom exceptions for human-related errors

Humans are a specialized type of Agent with required contact information.
"""

from .human import Human
from .human_list import HumanList
from .exceptions import (
    HumanErrors,
    HumanContactInfoError,
    HumanListError,
)

__all__ = [
    "Human",
    "HumanList",
    "HumanErrors",
    "HumanContactInfoError",
    "HumanListError",
]