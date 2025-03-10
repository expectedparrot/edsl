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
    
    This exception is raised when there are issues with creating, modifying,
    or using an AgentList in conjunction with scenarios.
    
    Args:
        message: A description of the error that occurred.
    """
    
    def __init__(self, message: str):
        """
        Initialize the AgentListError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)


class ScenarioError(BaseException):
    """
    Exception raised for errors related to Scenario operations.
    
    This exception is raised when there are issues with creating, modifying,
    or using Scenarios. It automatically includes a link to the documentation
    in the error message and makes URLs clickable in terminal output.
    
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
            >>> str(error)  # Returns the message with clickable link
        """
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, text)
        for url in urls:
            clickable_url = f"\033]8;;{url}\007{url}\033]8;;\007"
            text = text.replace(url, clickable_url)
        return text
