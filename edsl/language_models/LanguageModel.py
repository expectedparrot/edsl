from __future__ import annotations
from functools import wraps
import io
import asyncio
import json
import time
import inspect
from typing import Coroutine
from abc import ABC, abstractmethod, ABCMeta
from rich.console import Console
from rich.table import Table


from edsl.trackers.TrackerAPI import TrackerAPI
from queue import Queue
from typing import Any, Callable, Type, List
from edsl.data import CRUDOperations, CRUD
from edsl.exceptions import LanguageModelResponseNotJSONError
from edsl.language_models.schemas import model_prices
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler

from edsl.language_models.repair import repair
from typing import get_type_hints

from edsl.exceptions.language_models import LanguageModelAttributeTypeError
from edsl.enums import LanguageModelType, InferenceServiceType

from edsl.Base import RichPrintingMixin, PersistenceMixin


def handle_key_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
            assert True == False
        except KeyError as e:
            # Handle the KeyError exception
            return f"""KeyError occurred: {e}. This is most likely because the model you are using 
            returned a JSON object we were not expecting."""

    return wrapper


class RegisterLanguageModelsMeta(ABCMeta):
    "Metaclass to register output elements in a registry i.e., those that have a parent"
    _registry = {}  # Initialize the registry as a dictionary
    REQUIRED_CLASS_ATTRIBUTES = ["_model_", "_parameters_", "_inference_service_"]

    def __init__(cls, name, bases, dct):
        super(RegisterLanguageModelsMeta, cls).__init__(name, bases, dct)
        # if name != "LanguageModel":
        if (model_name := getattr(cls, "_model_", None)) is not None:
            RegisterLanguageModelsMeta.check_required_class_variables(
                cls, RegisterLanguageModelsMeta.REQUIRED_CLASS_ATTRIBUTES
            )

            ## Check that model name is valid
            if not LanguageModelType.is_value_valid(model_name):
                acceptable_values = [item.value for item in LanguageModelType]
                raise LanguageModelAttributeTypeError(
                    f"""A LanguageModel's model must be one of {LanguageModelType} values, which are
                    {acceptable_values}. You passed {model_name}."""
                )

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
            # breakpoint()
            # RegisterLanguageModelsMeta._registry[name] = cls
            RegisterLanguageModelsMeta._registry[model_name] = cls

    @classmethod
    def get_registered_classes(cls):
        return cls._registry

    @staticmethod
    def check_required_class_variables(
        candidate_class: LanguageModel, required_attributes: List[str] = None
    ):
        """Checks if a class has the required attributes
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
        """Checks if a method is defined in a class
        >>> class M:
        ...     def f(self): pass
        >>> RegisterLanguageModelsMeta._check_method_defined(M, "f")
        >>> RegisterLanguageModelsMeta._check_method_defined(M, "g")
        Traceback (most recent call last):
        ...
        NotImplementedError: g method must be implemented
        """
        if not hasattr(cls, method_name):
            raise NotImplementedError(f"{method_name} method must be implemented")

    @staticmethod
    def _check_is_coroutine(func: Callable):
        """
        Checks to make sure it's a coroutine function
        >>> def f(): pass
        >>> RegisterLanguageModelsMeta._check_is_coroutine(f)
        Traceback (most recent call last):
        ...
        TypeError: A LangugeModel class with method f must be an asynchronous method
        """
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"A LangugeModel class with method {func.__name__} must be an asynchronous method"
            )

    @staticmethod
    def _verify_parameter(params, param_name, param_type, method_name):
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
        Checks if the return type of a method is as expected
        >>> class M:
        ...     async def f(self) -> str: pass
        >>> RegisterLanguageModelsMeta._check_return_type(M.f, str)
        >>> class N:
        ...     async def f(self) -> int: pass
        >>> RegisterLanguageModelsMeta._check_return_type(N.f, str)
        Traceback (most recent call last):
        ...
        TypeError: Return type of f must be <class 'str'>. Got <class 'int'>
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
        d = {}
        for classname, cls in cls._registry.items():
            if hasattr(cls, "_model_"):
                d[cls._model_] = cls
            else:
                raise Exception(
                    f"Class {classname} does not have a _model_ class attribute"
                )
        return d


class LanguageModel(
    RichPrintingMixin, PersistenceMixin, ABC, metaclass=RegisterLanguageModelsMeta
):
    """ABC for LLM subclasses."""

    _model_ = None

    def __init__(self, crud: CRUDOperations = CRUD, **kwargs):
        """
        Attributes:
        - all attributes inherited from subclasses
        - lock: lock for this model to ensure TODO
        - api_queue: queue that records messages about API calls the model makes. Used by `InterviewManager` to update details about state of model.
        """
        self.model = getattr(self, "_model_", None)
        default_parameters = getattr(self, "_parameters_", None)
        parameters = self._overide_default_parameters(kwargs, default_parameters)
        self.parameters = parameters

        for key, value in parameters.items():
            setattr(self, key, value)

        for key, value in kwargs.items():
            if key not in parameters:
                setattr(self, key, value)

        # for key, value in kwargs.items():
        # setattr(self, key, value)
        self.api_queue = Queue()
        self.crud = crud

    @staticmethod
    def _overide_default_parameters(passed_parameter_dict, default_parameter_dict):
        """Returns a dictionary of parameters, with passed parameters taking precedence over defaults.

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
    async def async_execute_model_call():
        pass

    @jupyter_nb_handler
    def execute_model_call(self, *args, **kwargs) -> Coroutine:
        async def main():
            results = await asyncio.gather(
                self.async_execute_model_call(*args, **kwargs)
            )
            return results[0]  # Since there's only one task, return its result

        return main()

    @abstractmethod
    def parse_response(raw_response: dict[str, Any]) -> str:
        """Parses the API response and returns the response text.
        What is returned by the API is model-specific and often includes meta-data that we do not need.
        For example, here is the results from a call to GPT-4:

        {
            "id": "chatcmpl-8eORaeuVb4po9WQRjKEFY6w7v6cTm",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "logprobs": None,
                    "message": {
                        "content": "Hello! How can I assist you today? If you have any questions or need information on a particular topic, feel free to ask.",
                        "role": "assistant",
                        "function_call": None,
                        "tool_calls": None,
                    },
                }
            ],
            "created": 1704637774,
            "model": "gpt-4-1106-preview",
            "object": "chat.completion",
            "system_fingerprint": "fp_168383a679",
            "usage": {"completion_tokens": 27, "prompt_tokens": 13, "total_tokens": 40},
        }

        To actually tract the response, we need to grab
            data["choices[0]"]["message"]["content"].
        """
        raise NotImplementedError

    def _update_response_with_tracking(
        self, response, start_time, cached_response=False
    ):
        end_time = time.time()
        response["elapsed_time"] = end_time - start_time
        response["timestamp"] = end_time
        self._post_tracker_event(response)
        response["cached_response"] = cached_response
        return response

    async def async_get_raw_response(
        self, user_prompt: str, system_prompt: str = ""
    ) -> dict[str, Any]:
        """This is some middle-ware that handles the caching of responses.
        If the cache isn't being used, it just returns a 'fresh' call to the LLM,
        but appends some tracking information to the response (using the _update_response_with_tracking method).
        But if cache is being used, it first checks the database to see if the response is already there.
        If it is, it returns the cached response, but again appends some tracking information.
        If it isn't, it calls the LLM, saves the response to the database, and returns the response with tracking information.

        If self.use_cache is True, then attempts to retrieve the response from the database;
        if not in the DB, calls the LLM and writes the response to the DB."""
        start_time = time.time()

        if not self.use_cache:
            response = await self.async_execute_model_call(user_prompt, system_prompt)
            return self._update_response_with_tracking(response, start_time, False)

        cached_response = self.crud.get_LLMOutputData(
            model=str(self.model),
            parameters=str(self.parameters),
            system_prompt=system_prompt,
            prompt=user_prompt,
        )

        if cached_response:
            response = json.loads(cached_response)
            cache_used = True
        else:
            response = await self.async_execute_model_call(user_prompt, system_prompt)
            self._save_response_to_db(user_prompt, system_prompt, response)
            cache_used = False

        return self._update_response_with_tracking(response, start_time, cache_used)

    get_raw_response = sync_wrapper(async_get_raw_response)

    def _save_response_to_db(self, prompt, system_prompt, response):
        try:
            output = json.dumps(response)
        except json.JSONDecodeError:
            raise LanguageModelResponseNotJSONError
        self.crud.write_LLMOutputData(
            model=str(self.model),
            parameters=str(self.parameters),
            system_prompt=system_prompt,
            prompt=prompt,
            output=output,
        )

    async def async_get_response(self, user_prompt: str, system_prompt: str = ""):
        """Get response, parse, and return as string."""
        raw_response = await self.async_get_raw_response(user_prompt, system_prompt)
        response = self.parse_response(raw_response)
        try:
            dict_response = json.loads(response)
        except json.JSONDecodeError as e:
            print("Could not load JSON. Trying to repair.")
            print(response)
            dict_response, success = await repair(response, str(e))
            if not success:
                raise Exception("Even the repair failed.")
        return dict_response

    get_response = sync_wrapper(async_get_response)

    #######################
    # USEFUL METHODS
    #######################
    def _post_tracker_event(self, raw_response: dict[str, Any]) -> None:
        """Parses the API response and sends usage details to the API Queue."""
        usage = raw_response.get("usage", {})
        usage.update(
            {
                "cached_response": raw_response.get("cached_response", None),
                "elapsed_time": raw_response.get("elapsed_time", None),
                "timestamp": raw_response.get("timestamp", None),
            }
        )
        event = TrackerAPI.APICallDetails(details=usage)
        self.api_queue.put(event)

    def cost(self, raw_response: dict[str, Any]) -> float:
        """Returns the dollar cost of a raw response."""
        keys = raw_response["usage"].keys()
        prices = model_prices.get(self.model)
        return sum([prices.get(key, 0.0) * raw_response["usage"][key] for key in keys])

    #######################
    # SERIALIZATION METHODS
    #######################
    def to_dict(self) -> dict[str, Any]:
        """Converts instance to a dictionary."""
        return {"model": self.model, "parameters": self.parameters}

    @classmethod
    def from_dict(cls, data: dict) -> Type[LanguageModel]:
        """Converts dictionary to a LanguageModel child instance."""
        from edsl.language_models.registry import get_model_class

        model_class = get_model_class(data["model"])
        data["use_cache"] = True
        return model_class(**data)

    #######################
    # DUNDER METHODS
    #######################
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model = '{self.model}', parameters={self.parameters})"

    def __add__(self, other_model: Type[LanguageModel]) -> Type[LanguageModel]:
        """Combine two models into a single model (other_model takes precedence over self)"""
        print(
            f"""Warning: one model is replacing another. If you want to run both models, use a single `by` e.g., 
              by(m1, m2, m3) not by(m1).by(m2).by(m3)."""
        )
        return other_model or self

    def rich_print(self):
        """Displays an object as a table."""
        table = Table(title="Language Model")
        table.add_column("Attribute", style="bold")
        table.add_column("Value")

        to_display = self.__dict__.copy()
        for attr_name, attr_value in to_display.items():
            table.add_row(attr_name, repr(attr_value))

        return table

    @classmethod
    def example(cls):
        "Returns a default instance of the class"
        from edsl import Model

        return Model(Model.available()[0])


if __name__ == "__main__":
    # import doctest
    # doctest.testmod()
    from edsl.language_models import LanguageModel

    print(LanguageModel.example())
