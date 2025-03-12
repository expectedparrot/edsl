"""
Exceptions module for the scenarios package.

This module defines custom exception classes used throughout the scenarios module.
These exceptions provide specific error information for different types of errors
that can occur when working with Scenarios, ScenarioLists, and related components.
"""

import re
from typing import List

from ..base import BaseException


class AgentListError(BaseException):
    """
    Exception raised for errors related to AgentList operations.
    
    This exception appears to be a duplicate of the exception defined in
    edsl.agents.exceptions. It exists here for legacy reasons but is not
    actively used from this module.
    
    Note: This exception is defined but not used from this module. The AgentListError
    from edsl.agents.exceptions is used instead. This raises Exception("not used")
    to indicate this state.
    """
    
    def __init__(self, message: str):
        """
        Initialize the AgentListError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)
        raise Exception("not used - see edsl.agents.exceptions.AgentListError instead")


class ScenarioError(BaseException):
    """
    Exception raised for errors related to Scenario operations.
    
    This exception is raised when:
    - Invalid data is passed to initialize a Scenario (not convertible to dictionary)
    - Required fields are missing in scenario data
    - File operations fail when loading scenarios from files
    - Scenario content cannot be properly parsed or processed
    - Scenario lists encounter issues with data formats or operations
    
    To fix this error:
    1. Check that your scenario data is properly formatted (valid dictionary or convertible to one)
    2. Ensure all required fields for a scenario are present
    3. Verify file paths and permissions when loading from files
    4. Check for syntax or format errors in scenario content
    
    Examples:
        >>> Scenario(123)  # Raises ScenarioError (not convertible to dictionary)
        >>> Scenario({"invalid_format": True})  # May raise ScenarioError (missing required fields)
    
    Args:
        message: A description of the error that occurred.
    """
    
    documentation = "https://docs.expectedparrot.com/en/latest/scenarios.html#module-edsl.scenarios.Scenario"

    def __init__(self, message: str):
        """
        Initialize the ScenarioError with a message and add documentation link.
        
        Args:
            message: A description of the error that occurred.
        """
        self.message = message + "\n" + "Documentation: " + self.documentation
        super().__init__(self.message)

    def __str__(self) -> str:
        """
        Return a string representation of the error with clickable URLs.
        
        This method makes any URLs in the error message clickable when displayed
        in terminal environments that support ANSI escape sequences.
        
        Returns:
            The error message with clickable URLs.
        """
        return self.make_urls_clickable(self.message)

    @staticmethod
    def make_urls_clickable(text: str) -> str:
        """
        Convert URLs in text to clickable links in terminal output.
        
        This method finds all URLs in the given text and wraps them in ANSI
        escape sequences that make them clickable in supporting terminals.
        
        Args:
            text: The text containing URLs to make clickable.
            
        Returns:
            The text with URLs converted to clickable links.
            
        Example:
            >>> error = ScenarioError("See docs at https://example.com")
            >>> s = str(error)  # Returns the message with clickable link
            ...
        """
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, text)
        for url in urls:
            clickable_url = f"\033]8;;{url}\007{url}\033]8;;\007"
            text = text.replace(url, clickable_url)
        return text


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)