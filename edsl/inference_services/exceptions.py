from ..base import BaseException


class InferenceServiceError(BaseException):
    """
    Exception raised when an error occurs with an inference service.
    
    This exception is raised in the following scenarios:
    - When a service connection fails or times out
    - When the API returns an error response (e.g., rate limit exceeded)
    - When model parameters are invalid for the specified service
    - When the service doesn't support requested functionality
    - When there's an issue with authentication or API keys
    
    To fix this error:
    1. Check your API key is valid and has appropriate permissions
    2. Verify your network connection is stable
    3. Ensure the requested model is available on the service
    4. Check if provided parameters are valid for the model
    5. Verify you're not exceeding service rate limits
    
    If the issue persists, you may need to:
    - Switch to a different service provider
    - Use a different model with similar capabilities
    - Implement retry logic with exponential backoff
    
    Examples:
        ```python
        # Authentication error
        model = Model("gpt-4", api_key="invalid-key")  # Raises InferenceServiceError
        
        # Invalid model parameters
        model = Model("claude-3-opus", temperature=2.5)  # Raises InferenceServiceError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/remote_inference.html"


class InferenceServiceValueError(InferenceServiceError):
    """
    Exception raised when invalid values are provided to inference services.
    
    This exception occurs when parameters, configurations, or inputs for an inference
    service have invalid values, such as:
    - Invalid model names or identifiers
    - Out-of-range parameter values (e.g., temperature > 1.0)
    - Incorrect service names
    - Invalid regular expressions for pattern matching
    
    Examples:
        ```python
        # Invalid model name
        model = Model("non-existent-model")  # Raises InferenceServiceValueError
        
        # Out-of-range temperature
        model = Model("gpt-4", temperature=2.5)  # Raises InferenceServiceValueError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/language_models.html#model-parameters"


class InferenceServiceIndexError(InferenceServiceError):
    """
    Exception raised when attempting to access an invalid index in a collection.
    
    This exception occurs when trying to access elements outside the valid range 
    of an inference service's internal collections, such as:
    - Accessing results that don't exist
    - Using an invalid index in a list of models or services
    
    Examples:
        ```python
        service_models = get_available_models_for_service("openai")
        model = service_models[999]  # Raises InferenceServiceIndexError if there aren't 1000 models
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/language_models.html#available-models"


class InferenceServiceNotImplementedError(InferenceServiceError):
    """
    Exception raised when a requested feature or method is not implemented.
    
    This exception occurs when trying to use functionality that is defined in
    the interface but not yet implemented in a particular service, such as:
    - Using a feature only available in certain services
    - Calling methods that are not implemented in the concrete service class
    - Using functionality that is planned but not yet available
    
    Examples:
        ```python
        # Using a feature only available in certain services
        model = Model("test-model")
        model.streaming_generate()  # Raises InferenceServiceNotImplementedError if streaming is not supported
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/language_models.html#available-models"


class InferenceServiceRuntimeError(InferenceServiceError):
    """
    Exception raised when a runtime error occurs during inference.
    
    This exception occurs when there is a problem during the execution
    of an inference service operation, such as:
    - Service availability changes during operation
    - Network interruptions during API calls
    - Resource limits reached during execution
    
    Examples:
        ```python
        # Service becomes unavailable during operation
        model = Model("gpt-4")
        model.generate()  # Might raise InferenceServiceRuntimeError if service goes down mid-request
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/remote_inference.html"


class InferenceServiceEnvironmentError(InferenceServiceError):
    """
    Exception raised when there's an issue with the environment configuration.
    
    This exception occurs when the environment is not properly set up for
    using a particular inference service, such as:
    - Missing required environment variables (API keys, endpoints)
    - Improperly formatted environment variables
    - Insufficient permissions in the environment
    
    Examples:
        ```python
        # Missing required environment variables
        model = Model("azure-gpt4")  # Raises InferenceServiceEnvironmentError if AZURE_API_KEY is not set
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/api_keys.html"
