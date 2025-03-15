"""
Exceptions for the conversation module.

This module defines custom exceptions for the conversation module,
including errors for invalid participant configurations, agent interaction
failures, and conversation state errors.
"""

from ..base import BaseException


class ConversationError(BaseException):
    """
    Base exception class for all conversation-related errors.
    
    This is the parent class for all exceptions related to conversation
    operations, including agent communication, turn management, and
    participant configuration.
    """
    relevant_doc = "https://docs.expectedparrot.com/"


class ConversationValueError(ConversationError):
    """
    Exception raised when an invalid value is provided to a conversation.
    
    This exception occurs when attempting to create or modify a conversation
    with invalid values, such as:
    - Invalid participant configurations
    - Inappropriate agent parameters
    - Incompatible conversation settings
    
    Examples:
        ```python
        # Attempting to add an invalid participant to a conversation
        conversation.add_participant(None)  # Raises ConversationValueError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"
    

class ConversationStateError(ConversationError):
    """
    Exception raised when the conversation is in an invalid state.
    
    This exception occurs when attempting to perform an operation that
    is incompatible with the current state of the conversation, such as:
    - Ending a conversation that hasn't started
    - Starting a conversation that's already in progress
    - Accessing a participant that doesn't exist
    
    Examples:
        ```python
        # Attempting to get the next speaker when the conversation is empty
        empty_conversation.next_speaker()  # Raises ConversationStateError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"