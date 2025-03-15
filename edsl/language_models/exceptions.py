from textwrap import dedent
from typing import Optional

from ..base import BaseException

class LanguageModelExceptions(BaseException):
    """
    Base exception class for all language model-related errors.
    
    This is the parent class for all exceptions related to language model operations,
    including model creation, API calls, and response handling.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/language_models.html"
    explanation = "This is the base class for all exceptions in the language models module."

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class LanguageModelNoResponseError(LanguageModelExceptions):
    """
    Exception raised when a language model API fails to respond.
    
    This exception occurs when:
    - The language model API cannot be reached (network error)
    - The API request times out
    - The service is unavailable or overloaded
    - Authentication fails (in some cases)
    
    This exception is used in the retry mechanism for handling model API failures,
    particularly during interviews and asynchronous operations.
    
    To fix this error:
    1. Check your internet connection
    2. Verify that the language model service is operational
    3. Increase timeout settings if dealing with complex requests
    4. Check API keys and authentication if applicable
    5. Consider implementing exponential backoff retry logic
    
    Examples:
        ```python
        # API timeout during a model call
        model.generate(prompt="Very complex prompt", timeout=1)  # Raises LanguageModelNoResponseError if timeout is too short
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/language_models.html#handling-errors"
    explanation = "This happens when the language model API cannot be reached or does not respond within the specified timeout."

    def __init__(self, message):
        super().__init__(message)


class LanguageModelBadResponseError(LanguageModelExceptions):
    """
    Exception raised when a language model responds with unusable data.
    
    This exception occurs when:
    - The API responds but with malformed data
    - Required fields are missing in the response
    - The response format doesn't match expectations
    - The content can't be properly parsed
    
    This exception is commonly raised during response parsing and is used
    to distinguish between no response (timeout/network error) and invalid response.
    
    To fix this error:
    1. Check if the language model API has changed its response format
    2. Verify that your prompt is correctly formatted for the expected response
    3. Consider using a different model if the current one consistently produces bad responses
    4. Review the attached response_json for clues about what went wrong
    
    Examples:
        ```python
        # Requesting a format the model can't produce
        model.generate(prompt="Return valid XML")  # May raise LanguageModelBadResponseError if response isn't valid XML
        ```
    
    Attributes:
        message (str): Error message
        response_json (Optional[dict]): The raw response that caused the error, if available
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/language_models.html#handling-errors"
    explanation = "This happens when the language model API responds, but does not return a usable or properly formatted answer."

    def __init__(self, message, response_json: Optional[dict] = None):
        super().__init__(message)
        self.response_json = response_json


class LanguageModelNotFound(LanguageModelExceptions):
    """
    Exception raised when attempting to use a non-existent language model.
    
    This exception occurs when:
    - A model name is not recognized by the system
    - The requested model is not available in the current environment
    - There's a typo in the model name
    
    To fix this error:
    1. Check the model name for typos
    2. Use Model.available() to see all available models
    3. If using a proprietary model, ensure you have the necessary API keys
    4. For new models, ensure your EDSL version supports them
    
    Examples:
        ```python
        Model("non-existent-model")  # Raises LanguageModelNotFound
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/language_models.html#available-models"

    def __init__(self, model_name):
        msg = dedent(
            f"""\
            Model {model_name} not found.
            To create an instance of this model, pass the model name to a `Model` object.
            You can optionally pass additional parameters to the model, e.g.: 
            m = Model('gpt-4-1106-preview', temperature=0.5)
            
            To use the default model, simply run your job without specifying a model.
            To check the default model, run the following code:
            Model()

            To see information about all available models, run the following code:
            Model.available()

            See https://docs.expectedparrot.com/en/latest/language_models.html#available-models for more details.
            """
        )
        super().__init__(msg)


class LanguageModelResponseNotJSONError(LanguageModelExceptions):
    """
    Exception raised when a language model response cannot be parsed as JSON.
    
    This exception is for cases where JSON output was expected but the
    model returned something that couldn't be parsed as valid JSON.
    
    To fix this error:
    1. Check your prompt instructions regarding JSON format
    2. Ensure the model is capable of producing JSON output
    3. Consider using a structured output format with the model
    
    Note: This exception is defined but not currently used in the codebase.
    It raises Exception("not used") to indicate this state.
    """
    def __init__(self, message="Language model response is not valid JSON", **kwargs):
        super().__init__(message, **kwargs)


class LanguageModelMissingAttributeError(LanguageModelExceptions):
    """
    Exception raised when a required language model attribute is missing.
    
    This exception is for cases where a language model instance is missing
    a required attribute for its operation.
    
    To fix this error:
    1. Ensure the model is properly initialized
    2. Check for any configuration issues
    3. Verify the model class implements all required attributes
    
    Note: This exception is defined but not currently used in the codebase.
    It raises Exception("not used") to indicate this state.
    """
    def __init__(self, message="Missing required language model attribute", **kwargs):
        super().__init__(message, **kwargs)


class LanguageModelAttributeTypeError(LanguageModelExceptions):
    """
    Exception raised when a language model attribute has an incorrect type.
    
    This exception occurs when:
    - An invalid inference service is provided
    - A model parameter has the wrong data type
    - The model metaclass validation fails
    
    This exception is used during model registration to validate that model
    attributes meet the required specifications.
    
    To fix this error:
    1. Check the types of all parameters passed to the Model constructor
    2. Ensure inference service objects are properly initialized
    3. Verify that custom model classes follow the required attribute patterns
    
    Examples:
        ```python
        Model("gpt-4", max_tokens="not a number")  # Raises LanguageModelAttributeTypeError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/language_models.html#model-parameters"
    
    def __init__(self, message="Language model attribute has incorrect type"):
        super().__init__(message)


class LanguageModelDoNotAddError(LanguageModelExceptions):
    """
    Exception raised when attempting to add custom models inappropriately.
    
    This exception is designed to prevent inappropriate additions or
    modifications to the language model registry.
    
    Note: This exception is defined but not currently used in the codebase.
    """
    def __init__(self, message="Do not add custom models this way", **kwargs):
        super().__init__(message, **kwargs)


class LanguageModelValueError(LanguageModelExceptions):
    """
    Exception raised when there's an invalid value in a language model operation.
    
    This exception occurs when:
    - A parameter value is out of its acceptable range
    - A model configuration is invalid or incompatible
    - An operation is attempted with improper settings
    
    To fix this error:
    1. Check parameter values for validity (temperature, max_tokens, etc.)
    2. Ensure model settings are compatible with the chosen provider
    3. Verify that operation parameters are within acceptable ranges
    
    Examples:
        ```python
        # Setting temperature outside valid range
        model = Model("gpt-4", temperature=2.5)  # Raises LanguageModelValueError
        ```
    """
    def __init__(self, message="Invalid value in language model operation", **kwargs):
        super().__init__(message, **kwargs)


class LanguageModelTypeError(LanguageModelExceptions):
    """
    Exception raised when there's a type mismatch in a language model operation.
    
    This exception occurs when:
    - A parameter is of the wrong type (e.g., string instead of number)
    - An object of the wrong type is passed to a language model method
    - Type conversion fails during processing
    
    To fix this error:
    1. Check the types of all parameters passed to language model methods
    2. Ensure proper type conversions before passing data to models
    3. Verify that response handling functions expect the correct types
    
    Examples:
        ```python
        # Passing non-string prompt
        model.generate(prompt=123)  # Raises LanguageModelTypeError
        ```
    """
    def __init__(self, message="Type mismatch in language model operation", **kwargs):
        super().__init__(message, **kwargs)


class LanguageModelImplementationError(LanguageModelExceptions):
    """
    Exception raised when a required method or feature is not implemented.
    
    This exception occurs when:
    - An abstract method is not implemented by a subclass
    - A feature is requested that is not available for a specific model
    - A required interface method is missing
    
    To fix this error:
    1. Implement the required method in your subclass
    2. Use a model that supports the requested feature
    3. Check for updates that might add the missing functionality
    
    Examples:
        ```python
        # Requesting an unimplemented feature
        model.specialized_feature()  # Raises LanguageModelImplementationError
        ```
    """
    def __init__(self, message="Required method or feature is not implemented", **kwargs):
        super().__init__(message, **kwargs)


class LanguageModelRegistryError(LanguageModelExceptions):
    """
    Exception raised when there's an issue with the language model registry.
    
    This exception occurs when:
    - A model registration fails
    - There's a conflict in the registry
    - The registry contains invalid or corrupted entries
    
    To fix this error:
    1. Check for duplicate model registrations
    2. Ensure model classes follow the required registration pattern
    3. Verify that the registry is correctly initialized
    
    Examples:
        ```python
        # Attempting to register a model with a duplicate name
        Registry.register(duplicate_model)  # Raises LanguageModelRegistryError
        ```
    """
    def __init__(self, message="Error in language model registry", **kwargs):
        super().__init__(message, **kwargs)


class LanguageModelKeyError(LanguageModelExceptions):
    """
    Exception raised when a key is missing in a language model operation.
    
    This exception occurs when:
    - A required key is missing in a response dictionary
    - A lookup operation fails to find the requested key
    - An expected field is not present in a model response
    
    To fix this error:
    1. Check if the response format has changed
    2. Ensure the key you're looking for is correctly spelled
    3. Add fallback behavior for missing keys in responses
    
    Examples:
        ```python
        # Accessing a missing key in a model response
        response = model.generate(prompt="hello")
        print(response["missing_key"])  # Raises LanguageModelKeyError
        ```
    """
    def __init__(self, message="Key missing in language model operation", **kwargs):
        super().__init__(message, **kwargs)


class LanguageModelIndexError(LanguageModelExceptions):
    """
    Exception raised when an index is out of range in a language model operation.
    
    This exception occurs when:
    - An attempt is made to access an item at an invalid index
    - A list or sequence access is out of bounds
    - A token or completion index is invalid
    
    To fix this error:
    1. Check array boundaries before accessing elements
    2. Ensure index values are within valid ranges
    3. Add bounds checking for array operations
    
    Examples:
        ```python
        # Accessing an out-of-range index in a response
        completions = model.generate_completions(prompt="hello")
        print(completions[9999])  # Raises LanguageModelIndexError if fewer completions exist
        ```
    """
    def __init__(self, message="Index out of range in language model operation", **kwargs):
        super().__init__(message, **kwargs)
