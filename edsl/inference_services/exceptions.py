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
