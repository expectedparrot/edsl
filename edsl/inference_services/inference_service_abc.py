from abc import abstractmethod, ABC
import re
from datetime import datetime, timedelta
from typing import Any, List, Dict

from ..config import CONFIG
from .model_info import ModelInfo
#from .inference_service_registry import InferenceServiceRegistry

from .registry import GLOBAL_REGISTRY as _GLOBAL_REGISTRY


class InferenceServiceABC(ABC):
    """
    Abstract class for inference services.
    """

    _coop_config_vars = None

    def __init_subclass__(cls):
        """
        Check that the subclass has the required attributes and register the class.
        - `key_sequence` attribute determines...
        - `model_exclude_list` attribute determines...
        """
        # Register the subclass in the global registry using the service name
        _GLOBAL_REGISTRY.register(cls._inference_service_, cls)
        
        must_have_attributes = [
            "key_sequence",
            "model_exclude_list",
            "usage_sequence",
            "input_token_name",
            "output_token_name",
            # "available_models_url",
        ]
        for attr in must_have_attributes:
            if not hasattr(cls, attr):
                from .exceptions import InferenceServiceNotImplementedError

                raise InferenceServiceNotImplementedError(
                    f"Class {cls.__name__} must have a '{attr}' attribute."
                )
        
        # Check that 'available' method exists and is a class method
        if not hasattr(cls, 'available'):
            from .exceptions import InferenceServiceNotImplementedError
            raise InferenceServiceNotImplementedError(
                f"Class {cls.__name__} must have an 'available' method."
            )
        
        # Check that 'available' is a class method by looking in the class __dict__
        # We need to check the raw descriptor, not the bound method
        available_method = None
        for base_cls in cls.__mro__:  # Check the method resolution order
            if 'available' in base_cls.__dict__:
                available_method = base_cls.__dict__['available']
                break
        
        if available_method is not None and not isinstance(available_method, classmethod):
            from .exceptions import InferenceServiceNotImplementedError
            raise InferenceServiceNotImplementedError(
                f"Class {cls.__name__} 'available' method must be a class method (use @classmethod decorator)."
            )
        
 
    @property
    def service_name(self) -> str:
        """
        Returns the name of the service.
        """
        return self._inference_service_
    
    @classmethod
    def get_service_name(cls) -> str:
        """
        Returns the name of the service.
        
        >>> from edsl.inference_services.services import OpenAIService
        >>> OpenAIService.get_service_name()
        'openai'
        """
        return cls._inference_service_

    # @classmethod
    # def get_service_class(cls, service_name: str):
    #     """
    #     Returns the class for a given service name from the registry.
        
    #     Args:
    #         service_name (str): The name of the service
            
    #     Returns:
    #         The inference service class
            
    #     Raises:
    #         KeyError: If the service name is not found in the registry
            
    #     >>> # Create a test service to demonstrate
    #     >>> test_cls = InferenceServiceABC.example(return_class=True)
    #     >>> cls = InferenceServiceABC.get_service_class('test_service')
    #     >>> cls.__name__
    #     'TestInferenceService'
    #     """
    #     return _GLOBAL_REGISTRY.get_service_class(service_name)
      
    @classmethod
    def _should_refresh_coop_config_vars(cls):
        """
        Returns True if config vars have been fetched over 24 hours ago, and False otherwise.
        """

        if cls._last_config_fetch is None:
            return True
        return (datetime.now() - cls._last_config_fetch) > timedelta(hours=24)

    @classmethod
    @abstractmethod
    def get_model_info(cls) -> List[Any]:
        """
        Returns raw model information from the service API without any wrapping.
        Child classes must implement this method to return the raw response data.
        """
        pass
    
    @classmethod
    def get_model_list(cls) -> List[ModelInfo]:
        """
        Returns a list of ModelInfo objects using the unified ModelInfo class.
        This method calls get_model_info() and wraps the results.
        """
        raw_data = cls.get_model_info()
        return [ModelInfo.from_raw(item, cls._inference_service_) for item in raw_data]
    
    # @classmethod
    # @abstractmethod
    # def available(cls) -> list[str]:
    #     """
    #     Returns a list of available models for the service.

    #     >>> example = InferenceServiceABC.example()
    #     >>> example.available()
    #     ['test_model_1', 'test_model_2']
    #     """
    
    def __repr__(self) -> str: 
        return f"<{self.get_service_name()}>"

    @abstractmethod
    def create_model():
        """
        Returns a LanguageModel object.

        >>> example = InferenceServiceABC.example()
        >>> example.create_model(model_name="test_model_1")
        'Model(test_model_1)'
        """
        pass

    @staticmethod
    def to_class_name(s):
        """
        Converts a string to a valid class name.

        >>> InferenceServiceABC.to_class_name("hello world")
        'HelloWorld'
        """

        s = re.sub(r"[^a-zA-Z0-9 ]", "", s)
        s = "".join(word.title() for word in s.split())
        if s and s[0].isdigit():
            s = "Class" + s
        return s
    
    @classmethod
    def example(cls, return_class: bool = False):
        """
        Returns a test implementation of InferenceServiceABC for testing purposes.
        """

        class TestInferenceService(cls):
            """Test implementation of InferenceServiceABC for testing purposes."""
            
            # Required class attributes
            key_sequence = []
            model_exclude_list = []
            usage_sequence = []
            input_token_name = "input_tokens"
            output_token_name = "output_tokens"
            _inference_service_ = "test_service"
            
            def __init__(self):
                self._inference_service_ = "test_service"
                self._last_config_fetch = None

            @classmethod
            def get_model_info(cls) -> List[Any]:
                """Returns raw model info for testing."""
                return [
                    {"id": "test_model_1", "name": "Test Model 1"},
                    {"id": "test_model_2", "name": "Test Model 2"}
                ]
                
            @classmethod
            def available(cls) -> list[str]:
                """Returns a list of available models for the service."""
                return ["test_model_1", "test_model_2"]

            def create_model(self, model_name: str):
                """Returns a mock model object."""
                return f"Model({model_name})"
        if return_class:
            return TestInferenceService
        else:
            return TestInferenceService()


if __name__ == "__main__":
    #from .services import *
    print(_GLOBAL_REGISTRY._services)
    print("ID")
    print(id(_GLOBAL_REGISTRY))
