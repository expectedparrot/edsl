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
        raise Exception("not used")


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
        raise Exception("not used")
