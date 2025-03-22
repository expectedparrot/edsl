"""
Exceptions module for the scenarios package.

This module defines custom exception classes used throughout the scenarios module.
These exceptions provide specific error information for different types of errors
that can occur when working with Scenarios, ScenarioLists, and related components.
"""

import re

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
        ```python
        Scenario(123)  # Raises ScenarioError (not convertible to dictionary)
        Scenario({"invalid_format": True})  # May raise ScenarioError (missing required fields)
        ```
    
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
            ```python
            error = ScenarioError("See docs at https://example.com")
            s = str(error)  # Returns the message with clickable link
            ```
        """
        url_pattern = r"https?://[^\s]+"
        urls = re.findall(url_pattern, text)
        for url in urls:
            clickable_url = f"\033]8;;{url}\007{url}\033]8;;\007"
            text = text.replace(url, clickable_url)
        return text


class FileNotFoundScenarioError(ScenarioError):
    """
    Exception raised when a file needed for a scenario cannot be found.
    
    This exception occurs when:
    - A file specified in a file path does not exist
    - A referenced image, document, or other resource is missing
    - A directory expected to contain scenario files is not found
    
    To fix this error:
    1. Check that the file path is correct and the file exists
    2. Verify file system permissions allow access to the file
    3. Ensure any referenced external resources are properly available
    
    Examples:
        ```python
        Scenario.from_file("/path/to/nonexistent/file.json")  # Raises FileNotFoundScenarioError
        ```
    """
    
    def __init__(self, message: str):
        """
        Initialize the FileNotFoundScenarioError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)


class ImportScenarioError(ScenarioError):
    """
    Exception raised when importing a library needed for scenario operations fails.
    
    This exception occurs when:
    - A required library for handling specific file types is not installed
    - A module needed for processing scenario data cannot be imported
    - Optional dependencies for advanced features are missing
    
    To fix this error:
    1. Install the required dependencies mentioned in the error message
    2. Check for version conflicts between dependencies
    3. Ensure your environment has all necessary packages
    
    Examples:
        ```python
        # When attempting to load a PDF without the pdf dependencies
        Scenario.from_pdf("document.pdf")  # Raises ImportScenarioError
        ```
    """
    
    def __init__(self, message: str):
        """
        Initialize the ImportScenarioError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)


class TypeScenarioError(ScenarioError):
    """
    Exception raised when there's a type mismatch in scenario operations.
    
    This exception occurs when:
    - A parameter is of the wrong type for a scenario operation
    - Incompatible types are used in scenario methods
    - Type conversion fails during scenario processing
    
    To fix this error:
    1. Check the types of parameters passed to scenario methods
    2. Ensure data structures match what scenario operations expect
    3. Verify that operations between scenarios and other objects are compatible
    
    Examples:
        ```python
        scenario * "invalid_operand"  # Raises TypeScenarioError
        ```
    """
    
    def __init__(self, message: str):
        """
        Initialize the TypeScenarioError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)


class ValueScenarioError(ScenarioError):
    """
    Exception raised when there's an invalid value in scenario operations.
    
    This exception occurs when:
    - A parameter value is out of its acceptable range
    - Invalid formats are provided for scenario data
    - Operation parameters are invalid for the requested action
    
    To fix this error:
    1. Check parameter values against allowed ranges or formats
    2. Verify inputs meet the requirements for specific operations
    3. Ensure data formats match what's expected by scenario methods
    
    Examples:
        ```python
        scenario_list.to_table(output_type="invalid_format")  # Raises ValueScenarioError
        ```
    """
    
    def __init__(self, message: str):
        """
        Initialize the ValueScenarioError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)


class AttributeScenarioError(ScenarioError):
    """
    Exception raised when accessing a non-existent attribute in a scenario.
    
    This exception occurs when:
    - Attempting to access a field not present in a scenario
    - Using an attribute accessor on a scenario for a missing property
    - CSV or dataframe column access issues
    
    To fix this error:
    1. Check that the attribute name is correct
    2. Verify the scenario contains the expected fields
    3. Use hasattr() to check for attribute existence before access
    
    Examples:
        ```python
        scenario.nonexistent_attribute  # Raises AttributeScenarioError
        ```
    """
    
    def __init__(self, message: str):
        """
        Initialize the AttributeScenarioError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)


class IndexScenarioError(ScenarioError):
    """
    Exception raised when an index is out of range in scenario operations.
    
    This exception occurs when:
    - Accessing a scenario index outside the valid range
    - Using an invalid index in a scenario list operation
    - Sequence operations with invalid indices
    
    To fix this error:
    1. Check array boundaries before accessing elements
    2. Verify indices are within valid ranges for the collection
    3. Use len() to determine the valid index range
    
    Examples:
        ```python
        scenario_list[999]  # Raises IndexScenarioError if fewer items exist
        ```
    """
    
    def __init__(self, message: str):
        """
        Initialize the IndexScenarioError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)


class KeyScenarioError(ScenarioError):
    """
    Exception raised when a key is missing in scenario operations.
    
    This exception occurs when:
    - Accessing a non-existent key in a scenario
    - Using key-based access for missing fields
    - Dictionary operations with invalid keys
    
    To fix this error:
    1. Check if the key exists before attempting access
    2. Use dictionary get() method with default values for safer access
    3. Verify the scenario contains the expected keys
    
    Examples:
        ```python
        scenario["missing_key"]  # Raises KeyScenarioError
        ```
    """
    
    def __init__(self, message: str):
        """
        Initialize the KeyScenarioError with a message.
        
        Args:
            message: A description of the error that occurred.
        """
        super().__init__(message)

