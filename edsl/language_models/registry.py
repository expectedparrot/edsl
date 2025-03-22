from abc import ABCMeta
from typing import Any, List, Callable, TYPE_CHECKING
import inspect

if TYPE_CHECKING:
    from .language_model import LanguageModel
from .exceptions import (
    LanguageModelAttributeTypeError,
    LanguageModelImplementationError,
    LanguageModelTypeError,
    LanguageModelRegistryError
)
from edsl.enums import InferenceServiceType


class RegisterLanguageModelsMeta(ABCMeta):
    """Metaclass to register output elements in a registry i.e., those that have a parent."""

    _registry = {}  # Initialize the registry as a dictionary
    REQUIRED_CLASS_ATTRIBUTES = ["_model_", "_parameters_", "_inference_service_"]

    def __init__(cls, name, bases, dct):
        """Register the class in the registry if it has a _model_ attribute."""
        super(RegisterLanguageModelsMeta, cls).__init__(name, bases, dct)
        # if name != "LanguageModel":
        if (model_name := getattr(cls, "_model_", None)) is not None:
            RegisterLanguageModelsMeta.check_required_class_variables(
                cls, RegisterLanguageModelsMeta.REQUIRED_CLASS_ATTRIBUTES
            )

            ## Check that model name is valid
            # if not LanguageModelType.is_value_valid(model_name):
            #     acceptable_values = [item.value for item in LanguageModelType]
            #     raise LanguageModelAttributeTypeError(
            #         f"""A LanguageModel's model must be one of {LanguageModelType} values, which are
            #         {acceptable_values}. You passed {model_name}."""
            #     )

            if not InferenceServiceType.is_value_valid(
                inference_service := getattr(cls, "_inference_service_", None)
            ):
                acceptable_values = [item.value for item in InferenceServiceType]
                raise LanguageModelAttributeTypeError(
                    f"""A LanguageModel's model must have an _inference_service_ value from 
                    {acceptable_values}. You passed {inference_service}."""
                )

            # LanguageModel children have to implement the async_execute_model_call method
            RegisterLanguageModelsMeta.verify_method(
                candidate_class=cls,
                method_name="async_execute_model_call",
                expected_return_type=dict[str, Any],
                required_parameters=[("user_prompt", str), ("system_prompt", str)],
                must_be_async=True,
            )
            # LanguageModel children have to implement the parse_response method
            RegisterLanguageModelsMeta._registry[model_name] = cls

    @classmethod
    def get_registered_classes(cls):
        """Return the registry."""
        return cls._registry

    @staticmethod
    def check_required_class_variables(
        candidate_class: "LanguageModel", required_attributes: List[str] = None
    ):
        """Check if a class has the required attributes.

        >>> class M:
        ...     _model_ = "m"
        ...     _parameters_ = {}
        >>> RegisterLanguageModelsMeta.check_required_class_variables(M, ["_model_", "_parameters_"])
        >>> class M2:
        ...     _model_ = "m"
        """
        required_attributes = required_attributes or []
        for attribute in required_attributes:
            if not hasattr(candidate_class, attribute):
                raise LanguageModelRegistryError(
                    f"Class {candidate_class.__name__} does not have required attribute {attribute}"
                )

    @staticmethod
    def verify_method(
        candidate_class: "LanguageModel",
        method_name: str,
        expected_return_type: Any,
        required_parameters: List[tuple[str, Any]] = None,
        must_be_async: bool = False,
    ):
        """Verify that a method is defined in a class, has the correct return type, and has the correct parameters."""
        RegisterLanguageModelsMeta._check_method_defined(candidate_class, method_name)

        required_parameters = required_parameters or []
        method = getattr(candidate_class, method_name)
        # signature = inspect.signature(method)

        RegisterLanguageModelsMeta._check_return_type(method, expected_return_type)

        if must_be_async:
            RegisterLanguageModelsMeta._check_is_coroutine(method)

        # Check the parameters
        # params = signature.parameters
        # for param_name, param_type in required_parameters:
        #     RegisterLanguageModelsMeta._verify_parameter(
        #         params, param_name, param_type, method_name
        #     )

    @staticmethod
    def _check_method_defined(cls, method_name):
        """Check if a method is defined in a class.

        Example:
        >>> class M:
        ...     def f(self): pass
        >>> RegisterLanguageModelsMeta._check_method_defined(M, "f")
        """
        if not hasattr(cls, method_name):
            raise LanguageModelImplementationError(f"{method_name} method must be implemented.")

    @staticmethod
    def _check_is_coroutine(func: Callable):
        """Check to make sure it's a coroutine function.

        Example:

        >>> async def async_f(): pass
        >>> RegisterLanguageModelsMeta._check_is_coroutine(async_f)
        """
        if not inspect.iscoroutinefunction(func):
            raise LanguageModelTypeError(
                f"A LangugeModel class with method {func.__name__} must be an asynchronous method."
            )

    @staticmethod
    def _verify_parameter(params, param_name, param_type, method_name):
        """Verify that a parameter is defined in a method and has the correct type."""
        pass
        # if param_name not in params:
        #     raise TypeError(
        #         f"""Parameter "{param_name}" of method "{method_name}" must be defined.
        #         """
        #     )
        # if params[param_name].annotation != param_type:
        #     raise TypeError(
        #         f"""Parameter "{param_name}" of method "{method_name}" must be of type {param_type.__name__}.
        #         Got {params[param_name].annotation} instead.
        #         """
        #     )

    @staticmethod
    def _check_return_type(method, expected_return_type):
        """
        Check if the return type of a method is as expected.

        Example:
        """
        pass
        # if inspect.isroutine(method):
        #     # return_type = inspect.signature(method).return_annotation
        #     return_type = get_type_hints(method)["return"]
        #     if return_type != expected_return_type:
        #         raise TypeError(
        #             f"Return type of {method.__name__} must be {expected_return_type}. Got {return_type}."
        #         )

    @classmethod
    def model_names_to_classes(cls):
        """Return a dictionary of model names to classes."""
        d = {}
        for classname, cls in cls._registry.items():
            if hasattr(cls, "_model_"):
                d[cls._model_] = cls
            else:
                raise LanguageModelRegistryError(
                    f"Class {classname} does not have a _model_ class attribute."
                )
        return d
