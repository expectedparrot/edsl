from ..base import BaseException

class PromptError(BaseException):
    """
    Base exception class for all prompt-related errors.
    
    This is the parent class for all exceptions related to prompt processing,
    rendering, and validation in the EDSL framework.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/prompts.html"


class TemplateRenderError(PromptError):
    """
    Exception raised when template rendering fails.
    
    This exception is raised when:
    - Template rendering exceeds the maximum nesting level (potential infinite loop)
    - Template variables cannot be correctly substituted
    - The template contains syntax errors
    
    To fix this error:
    1. Check for circular references in your template variables
    2. Ensure all referenced variables are available in the template context
    3. Verify template syntax follows the correct format
    
    Examples:
        ```python
        # Circular reference causing infinite loop
        prompt.add_variable("var1", "{var2}")
        prompt.add_variable("var2", "{var1}")
        prompt.render()  # Raises TemplateRenderError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/prompts.html#template-variables"


class PromptBadQuestionTypeError(PromptError):
    """
    Exception raised when an invalid question type is used with a prompt.
    
    This exception is for cases where a prompt is configured for a specific
    question type but is used with an incompatible question.
    
    To fix this error:
    1. Ensure you're using the correct question type with the prompt
    2. Check if the prompt needs to be updated to support the question type
    
    Note: This exception is defined but not currently used in the codebase.
    It raises Exception("not used") to indicate this state.
    """
    def __init__(self, message="Invalid question type for this prompt", **kwargs):
        super().__init__(message, **kwargs)


class PromptBadLanguageModelTypeError(PromptError):
    """
    Exception raised when an incompatible language model is used with a prompt.
    
    This exception is for cases where a prompt requires specific language model
    capabilities that the provided model doesn't support.
    
    To fix this error:
    1. Use a different language model that supports the required capabilities
    2. Modify the prompt to work with the available language model
    
    Note: This exception is defined but not currently used in the codebase.
    It raises Exception("not used") to indicate this state.
    """
    def __init__(self, message="Incompatible language model for this prompt", **kwargs):
        super().__init__(message, **kwargs)


class PromptValueError(PromptError):
    """
    Exception raised when there's an invalid value in prompt operations.
    
    This exception occurs when:
    - A path to a template folder is invalid
    - Invalid parameters are provided for prompt configuration
    - Other validation errors during prompt operations
    
    To fix this error:
    1. Check that file paths are valid and accessible
    2. Verify that parameter values are within expected ranges or formats
    3. Ensure that all required prompt attributes are properly set
    
    Examples:
        ```python
        # Invalid path for loading templates
        prompt = Prompt.from_folder("/nonexistent/path")  # Raises PromptValueError
        ```
    """
    def __init__(self, message="Invalid value in prompt operation", **kwargs):
        super().__init__(message, **kwargs)


class PromptImplementationError(PromptError):
    """
    Exception raised when a required method or feature is not implemented.
    
    This exception occurs when:
    - An abstract method is not implemented by a prompt subclass
    - A feature is requested that is not implemented for a specific prompt type
    
    To fix this error:
    1. Implement the required method in your prompt subclass
    2. Use a different prompt type that supports the requested feature
    3. Check for updates that might add the missing functionality
    
    Examples:
        ```python
        # Calling an unimplemented method
        custom_prompt = CustomPrompt()
        custom_prompt.unimplemented_method()  # Raises PromptImplementationError
        ```
    """
    def __init__(self, message="Required method or feature is not implemented", **kwargs):
        super().__init__(message, **kwargs)
