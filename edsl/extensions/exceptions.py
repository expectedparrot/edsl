from ..base import BaseException


class ExtensionError(BaseException):
    """
    Base exception for all extension-related errors.    
    """
    pass

class ServiceConnectionError(ExtensionError):
    """Raised when there is an error connecting to the service endpoint or gateway."""
    pass

class ServiceResponseError(ExtensionError):
    """Raised when the service returns an unexpected or invalid response (e.g., bad status code, invalid JSON)."""
    pass

class ServiceConfigurationError(ExtensionError):
    """Raised when the service definition or client configuration is invalid or missing."""
    pass

class ServiceParameterValidationError(ExtensionError):
    """Raised when the parameters provided for a service call are invalid."""
    pass

class ServiceDeserializationError(ExtensionError):
    """Raised when the service response cannot be deserialized into the expected EDSL object or type."""
    pass

class ServiceOutputValidationError(ExtensionError):
    """Raised when the output produced by a service implementation does not match the defined returns."""
    pass