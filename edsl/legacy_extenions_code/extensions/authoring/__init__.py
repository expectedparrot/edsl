"""EDSL Extension Authoring Package.

This package provides tools for creating and managing EDSL extension services:

- ExtensionService: Abstract base class for creating extension services
- ServicesBuilder: Container for managing multiple services
- ServiceDefinition: Data class representing service metadata
- ExtensionOutput, ExtensionOutputs: Output structure classes

Example:
    from edsl.extensions.authoring import ExtensionService, ServicesBuilder
    
    class MyService(ExtensionService):
        service_name = "my_service"
        description = "Does something useful"
        cost = 10
        
        extension_outputs = {
            'result': {
                'output_type': 'str',
                'description': 'The result',
                'returns_coopr_url': False
            }
        }
        
        @staticmethod
        def execute(input_text: str) -> dict:
            return {'result': f"Processed: {input_text}"}
        
        @property
        def example_inputs(self) -> dict:
            return {'input_text': 'hello world'}
"""

# Core extension service classes
from .extension_service import ExtensionService, ExtensionOutput, ExtensionOutputs

# Main authoring classes
from .authoring import (
    ServicesBuilder,
    ServiceDefinition,
    ServiceBuilder,
    ParameterDefinition,
    ReturnDefinition,
    CostDefinition,
)

# Exception classes
from .exceptions import (
    ExtensionError,
    ServiceConnectionError,
    ServiceResponseError,
    ServiceConfigurationError,
    ServiceParameterValidationError,
    ServiceDeserializationError,
    ServiceOutputValidationError,
)

__all__ = [
    # Core extension service classes
    "ExtensionService",
    "ExtensionOutput",
    "ExtensionOutputs",
    # Main authoring classes
    "ServicesBuilder",
    "ServiceDefinition",
    "ServiceBuilder",
    "ParameterDefinition",
    "ReturnDefinition",
    "CostDefinition",
    # Exception classes
    "ExtensionError",
    "ServiceConnectionError",
    "ServiceResponseError",
    "ServiceConfigurationError",
    "ServiceParameterValidationError",
    "ServiceDeserializationError",
    "ServiceOutputValidationError",
]
