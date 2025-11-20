from __future__ import annotations
from abc import ABCMeta
import inspect

from .exceptions import QuestionMissingTypeError, QuestionBadTypeError


class RegisterQuestionsMeta(ABCMeta):
    """Metaclass to register output elements in a registry i.e., those that have a parent."""

    _registry = {}  # Initialize the registry as a dictionary

    def __call__(cls, *args, **kwargs):
        """
        Create a new instance with enhanced error handling for initialization.

        This method intercepts question instantiation and provides helpful,
        EDSL-specific error messages for common initialization mistakes.
        """
        from .exceptions import QuestionInitializationError
        import re

        try:
            # Attempt normal object creation
            return super().__call__(*args, **kwargs)
        except TypeError as e:
            error_msg = str(e)

            # Check if this is an "unexpected keyword argument" error
            if "unexpected keyword argument" in error_msg:
                # Extract the invalid parameter name from the error message
                match = re.search(r"unexpected keyword argument '([^']+)'", error_msg)
                invalid_param = match.group(1) if match else "unknown"

                # Get valid parameters by inspecting the __init__ method
                try:
                    init_signature = inspect.signature(cls.__init__)
                    valid_params = [
                        param_name
                        for param_name in init_signature.parameters.keys()
                        if param_name != "self"
                    ]
                except Exception:
                    valid_params = ["question_name", "question_text"]  # fallback

                # Create enhanced error message
                question_type = getattr(cls, "question_type", cls.__name__)

                raise QuestionInitializationError(
                    f"Unknown parameter '{invalid_param}' for {cls.__name__}",
                    question_type=question_type,
                    invalid_parameter=invalid_param,
                    valid_parameters=valid_params,
                ) from e

            elif "missing" in error_msg and "required positional argument" in error_msg:
                # Handle missing required parameters
                try:
                    init_signature = inspect.signature(cls.__init__)
                    valid_params = [
                        param_name
                        for param_name in init_signature.parameters.keys()
                        if param_name != "self"
                    ]
                except Exception:
                    valid_params = ["question_name", "question_text"]  # fallback

                question_type = getattr(cls, "question_type", cls.__name__)

                raise QuestionInitializationError(
                    f"Missing required parameters for {cls.__name__}: {error_msg}",
                    question_type=question_type,
                    valid_parameters=valid_params,
                    suggested_fix="Ensure you provide all required parameters",
                ) from e

            else:
                # For other TypeErrors, still convert to EDSL exception but with less specific info
                try:
                    init_signature = inspect.signature(cls.__init__)
                    valid_params = [
                        param_name
                        for param_name in init_signature.parameters.keys()
                        if param_name != "self"
                    ]
                except Exception:
                    valid_params = []

                question_type = getattr(cls, "question_type", cls.__name__)

                raise QuestionInitializationError(
                    f"Failed to initialize {cls.__name__}: {error_msg}",
                    question_type=question_type,
                    valid_parameters=valid_params,
                ) from e

    def __init__(cls, name, bases, dct):
        """Initialize the class and adds it to the registry if it's not the base class."""
        super(RegisterQuestionsMeta, cls).__init__(name, bases, dct)
        if (
            name != "QuestionBase"
            and name != "QuestionFunctional"
            and name != "QuestionAddTwoNumbers"
        ):
            ## Enforce that all questions have a question_type class attribute
            ## and it comes from our enum of valid question types.
            required_attributes = [
                "question_type",
                "_response_model",
                "response_validator_class",
            ]
            for attr in required_attributes:
                if not hasattr(cls, attr):
                    raise QuestionMissingTypeError(
                        f"Question must have a {attr} class attribute"
                    )

            init_signature = inspect.signature(cls.__init__)
            init_params = [p for p in init_signature.parameters if p != "self"]
            required_params = [
                "question_presentation",
                "answering_instructions",
                "question_name",
                "question_text",
            ]
            for param in required_params:
                if param not in init_params:
                    raise QuestionBadTypeError(
                        f"Question type {name} must have a question_presentation parameter in its __init__ method"
                    )

        if name != "QuestionBase":
            RegisterQuestionsMeta._registry[name] = cls

    @classmethod
    def get_registered_classes(cls):
        """Return the registry of registered classes."""
        return cls._registry

    @classmethod
    def question_types_to_classes(
        cls,
    ):
        """Return a dictionary of question types to classes."""
        d = {}
        for classname, cls in cls._registry.items():
            if hasattr(cls, "question_type"):
                d[cls.question_type] = cls
            else:
                from .exceptions import QuestionMissingTypeError

                raise QuestionMissingTypeError(
                    f"Class {classname} does not have a question_type class attribute"
                )
        return d


if __name__ == "__main__":
    import doctest

    doctest.testmod()
