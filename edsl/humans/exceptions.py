"""Exceptions for the Human module.

This module defines exceptions specific to the Human and HumanList classes.
"""

from ..base.base_exception import BaseException
from ..agents.exceptions import AgentErrors, AgentListError


class HumanErrors(AgentErrors):
    """
    Base exception class for all human-related errors.
    
    This class is the parent of all human-specific exceptions and may also be raised directly
    when there are issues related to human participants.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/humans.html"


class HumanContactInfoError(HumanErrors):
    """
    Exception raised when a Human is created without valid contact information.
    
    This exception occurs when:
    - No contact information is provided (email, phone, prolific_id, or ep_username)
    - Invalid contact information is provided (e.g., malformed email)
    
    To fix this, ensure that at least one valid contact method is provided when creating
    a Human object.
    
    Examples:
        ```python
        Human(traits={"age": 30})  # Raises HumanContactInfoError, no contact info
        Human(traits={"age": 30}, email="not-an-email")  # Raises HumanContactInfoError, invalid email
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/humans.html#contact-information"


class HumanListError(AgentListError):
    """
    Exception raised when a HumanList operation fails.
    
    This exception is raised in the following cases:
    - When an invalid expression is provided in the filter() method
    - When trying to add traits with mismatched lengths
    - When attempting to create a table from an empty HumanList
    - When operations specific to humans fail
    
    Examples:
        ```python
        humans.filter("invalid expression")  # Raises HumanListError
        humans.add_trait(name="scores", values=[1, 2])  # Raises HumanListError if humans list has different length
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/humans.html#human-lists"