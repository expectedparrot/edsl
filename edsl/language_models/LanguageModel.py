"""This module contains the LanguageModel class, which is an abstract base class for all language models."""
from __future__ import annotations
import warnings
from functools import wraps
import asyncio
import json
import time
import inspect
import os

from typing import Coroutine, Any, Callable, Type, List, get_type_hints

from abc import ABC, abstractmethod, ABCMeta

from rich.table import Table

from edsl.config import CONFIG
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.language_models.repair import repair
from edsl.exceptions.language_models import LanguageModelAttributeTypeError
from edsl.enums import InferenceServiceType
from edsl.Base import RichPrintingMixin, PersistenceMixin
from edsl.data.Cache import Cache
from edsl.enums import service_to_api_keyname

from edsl.exceptions import MissingAPIKeyError


def handle_key_error(func):
    """Handle KeyError exceptions."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
            assert True == False
        except KeyError as e:
            return f"""KeyError occurred: {e}. This is most likely because the model you are using 
            returned a JSON object we were not expecting."""

    return wrapper


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
            RegisterLanguageModelsMeta.verify_method(
                candidate_class=cls,
                method_name="parse_response",
                expected_return_type=str,
                required_parameters=[("raw_response", dict[str, Any])],
                must_be_async=False,
            )
            RegisterLanguageModelsMeta._registry[model_name] = cls

    @classmethod
    def get_registered_classes(cls):
        """Return the registry."""
        return cls._registry

    @staticmethod
    def check_required_class_variables(
        candidate_class: LanguageModel, required_attributes: List[str] = None
    ):
        """Check if a class has the required attributes.

        >>> class M:
        ...     _model_ = "m"
        ...     _parameters_ = {}
        >>> RegisterLanguageModelsMeta.check_required_class_variables(M, ["_model_", "_parameters_"])
        >>> class M2:
        ...     _model_ = "m"
        >>> RegisterLanguageModelsMeta.check_required_class_variables(M2, ["_model_", "_parameters_"])
        Traceback (most recent call last):
        ...
        Exception: Class M2 does not have required attribute _parameters_
        """
        required_attributes = required_attributes or []
        for attribute in required_attributes:
            if not hasattr(candidate_class, attribute):
                raise Exception(
                    f"Class {candidate_class.__name__} does not have required attribute {attribute}"
                )

    @staticmethod
    def verify_method(
        candidate_class: LanguageModel,
        method_name: str,
        expected_return_type: Any,
        required_parameters: List[tuple[str, Any]] = None,
        must_be_async: bool = False,
    ):
        """Verify that a method is defined in a class, has the correct return type, and has the correct parameters."""
        RegisterLanguageModelsMeta._check_method_defined(candidate_class, method_name)

        required_parameters = required_parameters or []
        method = getattr(candidate_class, method_name)
        signature = inspect.signature(method)

        RegisterLanguageModelsMeta._check_return_type(method, expected_return_type)

        if must_be_async:
            RegisterLanguageModelsMeta._check_is_coroutine(method)

        # Check the parameters
        params = signature.parameters
        for param_name, param_type in required_parameters:
            RegisterLanguageModelsMeta._verify_parameter(
                params, param_name, param_type, method_name
            )

    @staticmethod
    def _check_method_defined(cls, method_name):
        """Check if a method is defined in a class.

        Example:
        >>> class M:
        ...     def f(self): pass
        >>> RegisterLanguageModelsMeta._check_method_defined(M, "f")
        >>> RegisterLanguageModelsMeta._check_method_defined(M, "g")
        Traceback (most recent call last):
        ...
        NotImplementedError: g method must be implemented.
        """
        if not hasattr(cls, method_name):
            raise NotImplementedError(f"{method_name} method must be implemented.")

    @staticmethod
    def _check_is_coroutine(func: Callable):
        """Check to make sure it's a coroutine function.

        Example:

        >>> def f(): pass
        >>> RegisterLanguageModelsMeta._check_is_coroutine(f)
        Traceback (most recent call last):
        ...
        TypeError: A LangugeModel class with method f must be an asynchronous method.
        """
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"A LangugeModel class with method {func.__name__} must be an asynchronous method."
            )

    @staticmethod
    def _verify_parameter(params, param_name, param_type, method_name):
        """Verify that a parameter is defined in a method and has the correct type."""
        if param_name not in params:
            raise TypeError(
                f"""Parameter "{param_name}" of method "{method_name}" must be defined.
                """
            )
        if params[param_name].annotation != param_type:
            raise TypeError(
                f"""Parameter "{param_name}" of method "{method_name}" must be of type {param_type.__name__}.
                Got {params[param_name].annotation} instead.
                """
            )

    @staticmethod
    def _check_return_type(method, expected_return_type):
        """
        Check if the return type of a method is as expected.

        Example:
        >>> class M:
        ...     async def f(self) -> str: pass
        >>> RegisterLanguageModelsMeta._check_return_type(M.f, str)
        >>> class N:
        ...     async def f(self) -> int: pass
        >>> RegisterLanguageModelsMeta._check_return_type(N.f, str)
        Traceback (most recent call last):
        ...
        TypeError: Return type of f must be <class 'str'>. Got <class 'int'>.
        """
        if inspect.isroutine(method):
            # return_type = inspect.signature(method).return_annotation
            return_type = get_type_hints(method)["return"]
            if return_type != expected_return_type:
                raise TypeError(
                    f"Return type of {method.__name__} must be {expected_return_type}. Got {return_type}."
                )

    @classmethod
    def model_names_to_classes(cls):
        """Return a dictionary of model names to classes."""
        d = {}
        for classname, cls in cls._registry.items():
            if hasattr(cls, "_model_"):
                d[cls._model_] = cls
            else:
                raise Exception(
                    f"Class {classname} does not have a _model_ class attribute."
                )
        return d


class LanguageModel(
    RichPrintingMixin, PersistenceMixin, ABC, metaclass=RegisterLanguageModelsMeta
):
    """ABC for LLM subclasses."""

    _model_ = None

    __rate_limits = None
    # TODO: Use the OpenAI Teir 1 rate limits
    __default_rate_limits = {"rpm": 10_000, "tpm": 2_000_000}
    _safety_factor = 0.8

    def __init__(self, **kwargs):
        """Initialize the LanguageModel."""
        self.model = getattr(self, "_model_", None)
        default_parameters = getattr(self, "_parameters_", None)
        parameters = self._overide_default_parameters(kwargs, default_parameters)
        self.parameters = parameters
        self.remote = False

        for key, value in parameters.items():
            setattr(self, key, value)

        for key, value in kwargs.items():
            if key not in parameters:
                setattr(self, key, value)

        if "use_cache" in kwargs:
            warnings.warn(
                "The use_cache parameter is deprecated. Use the Cache class instead."
            )

        if skip_api_key_check := kwargs.get("skip_api_key_check", False):
            # Skip the API key check. Sometimes this is useful for testing.
            self._api_token = None

    @property
    def api_token(self):
        if not hasattr(self, "_api_token"):
            key_name = service_to_api_keyname.get(self._inference_service_, "NOT FOUND")
            self._api_token = os.getenv(key_name)
            if (
                self._api_token is None
                and self._inference_service_ != "test"
                and not self.remote
            ):
                raise MissingAPIKeyError(
                    f"""The key for service: `{self._inference_service_}` is not set.
                    Need a key with name {key_name} in your .env file.
                    """
                )
        return self._api_token

    def __getitem__(self, key):
        return getattr(self, key)

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    def hello(self, verbose=False):
        """Runs a simple test to check if the model is working."""
        token = self.api_token
        masked = token[: min(8, len(token))] + "..."
        if verbose:
            print(f"Current key is {masked}")
        return self.execute_model_call(
            user_prompt="Hello, model!", system_prompt="You are a helpful agent."
        )

    def has_valid_api_key(self) -> bool:
        """Check if the model has a valid API key.

        This method is used to check if the model has a valid API key.
        """
        from edsl.enums import service_to_api_keyname
        import os

        if self._model_ == "test":
            return True

        key_name = service_to_api_keyname.get(self._inference_service_, "NOT FOUND")
        key_value = os.getenv(key_name)
        return key_value is not None

    def __hash__(self):
        """Allow the model to be used as a key in a dictionary."""
        return hash(self.model + str(self.parameters))

    def __eq__(self, other):
        """Check is two models are the same.

        >>> m1 = LanguageModel.example()
        >>> m2 = LanguageModel.example()
        >>> m1 == m2
        True

        """
        return self.model == other.model and self.parameters == other.parameters

    def _set_rate_limits(self, rpm=None, tpm=None) -> None:
        """Set the rate limits for the model.

        If the model does not have rate limits, use the default rate limits."""
        if rpm is not None and tpm is not None:
            self.__rate_limits = {"rpm": rpm, "tpm": tpm}
            return

        if self.__rate_limits is None:
            if hasattr(self, "get_rate_limits"):
                self.__rate_limits = self.get_rate_limits()
            else:
                self.__rate_limits = self.__default_rate_limits

    @property
    def RPM(self):
        """Model's requests-per-minute limit."""
        self._set_rate_limits()
        return self._safety_factor * self.__rate_limits["rpm"]

    @property
    def TPM(self):
        """Model's tokens-per-minute limit."""
        self._set_rate_limits()
        return self._safety_factor * self.__rate_limits["tpm"]

    @staticmethod
    def _overide_default_parameters(passed_parameter_dict, default_parameter_dict):
        """Return a dictionary of parameters, with passed parameters taking precedence over defaults.

        >>> LanguageModel._overide_default_parameters(passed_parameter_dict={"temperature": 0.5}, default_parameter_dict={"temperature":0.9})
        {'temperature': 0.5}
        >>> LanguageModel._overide_default_parameters(passed_parameter_dict={"temperature": 0.5}, default_parameter_dict={"temperature":0.9, "max_tokens": 1000})
        {'temperature': 0.5, 'max_tokens': 1000}
        """
        parameters = dict({})
        for parameter, default_value in default_parameter_dict.items():
            if parameter in passed_parameter_dict:
                parameters[parameter] = passed_parameter_dict[parameter]
            else:
                parameters[parameter] = default_value
        return parameters

    @abstractmethod
    async def async_execute_model_call(user_prompt, system_prompt):
        """Execute the model call and returns the result as a coroutine."""
        pass

    async def remote_async_execute_model_call(self, user_prompt, system_prompt):
        """Execute the model call and returns the result as a coroutine, using Coop."""
        from edsl.coop import Coop

        client = Coop()
        response_data = await client.remote_async_execute_model_call(
            self.to_dict(), user_prompt, system_prompt
        )
        return response_data

    @jupyter_nb_handler
    def execute_model_call(self, *args, **kwargs) -> Coroutine:
        """Execute the model call and returns the result as a coroutine."""

        async def main():
            results = await asyncio.gather(
                self.async_execute_model_call(*args, **kwargs)
            )
            return results[0]  # Since there's only one task, return its result

        return main()

    @abstractmethod
    def parse_response(raw_response: dict[str, Any]) -> str:
        """Parse the API response and returns the response text.

        What is returned by the API is model-specific and often includes meta-data that we do not need.
        For example, here is the results from a call to GPT-4:
        To actually tract the response, we need to grab
        data["choices[0]"]["message"]["content"].
        """
        raise NotImplementedError

    def _update_response_with_tracking(
        self, response, start_time, cached_response=False, cache_key=None
    ):
        """Update the response with tracking information and post it to the API Queue."""
        end_time = time.time()
        response["elapsed_time"] = end_time - start_time
        response["timestamp"] = end_time
        response["cached_response"] = cached_response
        response["cache_key"] = cache_key
        return response

    async def async_get_raw_response(
        self,
        user_prompt: str,
        system_prompt: str,
        cache,
        iteration: int = 0,
    ) -> dict[str, Any]:
        """Handle caching of responses.

        :param user_prompt: The user's prompt.
        :param system_prompt: The system's prompt.
        :param iteration: The iteration number.
        :param cache: The cache to use.

        If the cache isn't being used, it just returns a 'fresh' call to the LLM,
        but appends some tracking information to the response (using the _update_response_with_tracking method).
        But if cache is being used, it first checks the database to see if the response is already there.
        If it is, it returns the cached response, but again appends some tracking information.
        If it isn't, it calls the LLM, saves the response to the database, and returns the response with tracking information.

        If self.use_cache is True, then attempts to retrieve the response from the database;
        if not in the DB, calls the LLM and writes the response to the DB.
        """
        start_time = time.time()

        cached_response = cache.fetch(
            model=str(self.model),
            parameters=self.parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            iteration=iteration,
        )

        if cache_used := (cached_response is not None):
            # print("Cache used")
            response = json.loads(cached_response)
        else:
            # print("Cache not used")
            # print(f"Cache data is: {cache.data}")
            if hasattr(self, "remote") and self.remote:
                response = await self.remote_async_execute_model_call(
                    user_prompt, system_prompt
                )
            else:
                response = await self.async_execute_model_call(
                    user_prompt, system_prompt
                )

        if not cache_used:
            cache_key = cache.store(
                user_prompt=user_prompt,
                model=str(self.model),
                parameters=self.parameters,
                system_prompt=system_prompt,
                response=response,
                iteration=iteration,
            )
        else:
            cache_key = None
        return self._update_response_with_tracking(
            response=response,
            start_time=start_time,
            cached_response=cache_used,
            cache_key=cache_key,
        )

    get_raw_response = sync_wrapper(async_get_raw_response)

    def simple_ask(
        self,
        question: "QuestionBase",
        system_prompt="You are a helpful agent pretending to be a human.",
        top_logprobs=2,
    ):
        """Ask a question and return the response."""
        self.logprobs = True
        self.top_logprobs = top_logprobs
        return self.execute_model_call(
            user_prompt=question.human_readable(), system_prompt=system_prompt
        )

    async def async_get_response(
        self, user_prompt: str, system_prompt: str, cache: Cache, iteration: int = 1
    ) -> dict:
        """Get response, parse, and return as string.

        :param user_prompt: The user's prompt.
        :param system_prompt: The system's prompt.
        :param iteration: The iteration number.
        :param cache: The cache to use.

        """
        raw_response = await self.async_get_raw_response(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            iteration=iteration,
            cache=cache,
        )
        response = self.parse_response(raw_response)
        try:
            dict_response = json.loads(response)
        except json.JSONDecodeError as e:
            # TODO: Turn into logs to generate issues
            dict_response, success = await repair(response, str(e))
            if not success:
                raise Exception("Even the repair failed.")

        dict_response["cached_response"] = raw_response["cached_response"]
        dict_response["usage"] = raw_response.get("usage", {})
        dict_response["raw_model_response"] = raw_response
        return dict_response

    get_response = sync_wrapper(async_get_response)

    def cost(self, raw_response: dict[str, Any]) -> float:
        """Return the dollar cost of a raw response."""
        raise NotImplementedError
        # keys = raw_response["usage"].keys()
        # prices = model_prices.get(self.model)
        # return sum([prices.get(key, 0.0) * raw_response["usage"][key] for key in keys])

    #######################
    # SERIALIZATION METHODS
    #######################
    def to_dict(self) -> dict[str, Any]:
        """Convert instance to a dictionary."""
        return {"model": self.model, "parameters": self.parameters}

    @classmethod
    def from_dict(cls, data: dict) -> Type[LanguageModel]:
        """Convert dictionary to a LanguageModel child instance."""
        from edsl.language_models.registry import get_model_class

        model_class = get_model_class(data["model"])
        data["use_cache"] = True
        return model_class(**data)

    #######################
    # DUNDER METHODS
    #######################
    def __repr__(self) -> str:
        """Return a string representation of the object."""
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))
        param_string = ", ".join(
            f"{key} = {value}" for key, value in self.parameters.items()
        )
        return (
            f"Model(model_name = '{self.model}'"
            + (f", {param_string}" if param_string else "")
            + ")"
        )

    def __add__(self, other_model: Type[LanguageModel]) -> Type[LanguageModel]:
        """Combine two models into a single model (other_model takes precedence over self)."""
        print(
            f"""Warning: one model is replacing another. If you want to run both models, use a single `by` e.g., 
              by(m1, m2, m3) not by(m1).by(m2).by(m3)."""
        )
        return other_model or self

    def rich_print(self):
        """Display an object as a table."""
        table = Table(title="Language Model")
        table.add_column("Attribute", style="bold")
        table.add_column("Value")

        to_display = self.__dict__.copy()
        for attr_name, attr_value in to_display.items():
            table.add_row(attr_name, repr(attr_value))

        return table

    @classmethod
    def example(cls):
        """Return a default instance of the class."""
        from edsl import Model

        return Model(skip_api_key_check=True)


if __name__ == "__main__":
    """Run the module's test suite."""
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    from edsl.language_models import LanguageModel

    print(LanguageModel.example())
