"""This module contains the LanguageModel class, which is an abstract base class for all language models."""

from __future__ import annotations
import warnings
from functools import wraps
import asyncio
import json
import time
import os

from typing import Coroutine, Any, Callable, Type, List, get_type_hints

from abc import ABC, abstractmethod, ABCMeta

from rich.table import Table

from edsl.config import CONFIG

from edsl.utilities.utilities import clean_json
from edsl.utilities.decorators import sync_wrapper, jupyter_nb_handler
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version
from edsl.language_models.repair import repair
from edsl.exceptions.language_models import LanguageModelAttributeTypeError
from edsl.enums import InferenceServiceType
from edsl.Base import RichPrintingMixin, PersistenceMixin
from edsl.data.Cache import Cache
from edsl.enums import service_to_api_keyname


from edsl.exceptions import MissingAPIKeyError
from edsl.language_models.RegisterLanguageModelsMeta import RegisterLanguageModelsMeta


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


class LanguageModel(
    RichPrintingMixin, PersistenceMixin, ABC, metaclass=RegisterLanguageModelsMeta
):
    """ABC for LLM subclasses.

    TODO:

    1) Need better, more descriptive names for functions

    get_model_response_no_cache  (currently called async_execute_model_call)

    get_model_response (currently called async_get_raw_response; uses cache & adds tracking info)
      Calls:
        - async_execute_model_call
        - _updated_model_response_with_tracking

    get_answer (currently called async_get_response)
        This parses out the answer block and does some error-handling.
        Calls:
            - async_get_raw_response
            - parse_response


    """

    _model_ = None

    __rate_limits = None
    __default_rate_limits = {
        "rpm": 10_000,
        "tpm": 2_000_000,
    }  # TODO: Use the OpenAI Teir 1 rate limits
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
    def api_token(self) -> str:
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

        >>> LanguageModel.example().has_valid_api_key()
        True

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
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict())

    def __eq__(self, other):
        """Check is two models are the same.

        >>> m1 = LanguageModel.example()
        >>> m2 = LanguageModel.example()
        >>> m1 == m2
        True

        """
        return self.model == other.model and self.parameters == other.parameters

    def set_rate_limits(self, rpm=None, tpm=None) -> None:
        """Set the rate limits for the model.

        >>> m = LanguageModel.example()
        >>> m.set_rate_limits(rpm=100, tpm=1000)
        >>> m.RPM
        80.0
        """
        self._set_rate_limits(rpm=rpm, tpm=tpm)

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
        """Model's tokens-per-minute limit.

        >>> m = LanguageModel.example()
        >>> m.TPM
        1600000.0
        """
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
    async def async_execute_model_call(user_prompt: str, system_prompt: str):
        """Execute the model call and returns the result as a coroutine.

        >>> m = LanguageModel.example(test_model = True)
        >>> m.execute_model_call("Hello, model!", "You are a helpful agent.")
        {'message': '{"answer": "Hello world"}'}

        """
        pass

    async def remote_async_execute_model_call(
        self, user_prompt: str, system_prompt: str
    ):
        """Execute the model call and returns the result as a coroutine, using Coop."""
        from edsl.coop import Coop

        client = Coop()
        response_data = await client.remote_async_execute_model_call(
            self.to_dict(), user_prompt, system_prompt
        )
        return response_data

    @jupyter_nb_handler
    def execute_model_call(self, *args, **kwargs) -> Coroutine:
        """Execute the model call and returns the result as a coroutine.

        >>> m = LanguageModel.example(test_model = True)
        >>> m.execute_model_call(user_prompt = "Hello, model!", system_prompt = "You are a helpful agent.")

        """

        async def main():
            results = await asyncio.gather(
                self.async_execute_model_call(*args, **kwargs)
            )
            return results[0]  # Since there's only one task, return its result

        return main()

    @abstractmethod
    def parse_response(raw_response: dict[str, Any]) -> str:
        """Parse the response and returns the response text.

        >>> m = LanguageModel.example(test_model = True)
        >>> m
        Model(model_name = 'test', temperature = 0.5)

        What is returned by the API is model-specific and often includes meta-data that we do not need.
        For example, here is the results from a call to GPT-4:
        To actually tract the response, we need to grab
        data["choices[0]"]["message"]["content"].
        """
        raise NotImplementedError

    def _update_response_with_tracking(
        self, response: dict, start_time: int, cached_response=False, cache_key=None
    ):
        """Update the response with tracking information.

        >>> m = LanguageModel.example()
        >>> m._update_response_with_tracking(response={"response": "Hello"}, start_time=0, cached_response=False, cache_key=None)
        {'response': 'Hello', 'elapsed_time': ..., 'timestamp': ..., 'cached_response': False, 'cache_key': None}


        """
        end_time = time.time()
        ## TODO: This 'cached_response' field is important for some reason.
        response.update(
            {
                # "elapsed_time": end_time - start_time,
                # "timestamp": end_time,
                #                "cached_response": cached_response,
                # "cache_key": cache_key,
            }
        )
        return response

    async def async_get_raw_response(
        self,
        user_prompt: str,
        system_prompt: str,
        cache,
        iteration: int = 0,
        encoded_image=None,
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

        >>> from edsl import Cache
        >>> m = LanguageModel.example(test_model = True)
        >>> m.get_raw_response(user_prompt = "Hello", system_prompt = "hello", cache = Cache())
        {'message': '{"answer": "Hello world"}', 'elapsed_time': ..., 'timestamp': ..., 'cached_response': False, 'cache_key': '24ff6ac2bc2f1729f817f261e0792577'}
        """
        start_time = time.time()

        cache_call_params = {
            "model": str(self.model),
            "parameters": self.parameters,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "iteration": iteration,
        }

        if encoded_image:
            import hashlib

            image_hash = hashlib.md5(encoded_image.encode()).hexdigest()
            cache_call_params["user_prompt"] = f"{user_prompt} {image_hash}"

        cached_response = cache.fetch(**cache_call_params)

        if cached_response:
            response = json.loads(cached_response)
            cache_used = True
            cache_key = None
        else:
            remote_call = hasattr(self, "remote") and self.remote
            f = (
                self.remote_async_execute_model_call
                if remote_call
                else self.async_execute_model_call
            )
            params = {"user_prompt": user_prompt, "system_prompt": system_prompt}
            if encoded_image:
                params["encoded_image"] = encoded_image
            response = await f(**params)
            cache_key = cache.store(
                user_prompt=user_prompt,
                model=str(self.model),
                parameters=self.parameters,
                system_prompt=system_prompt,
                response=response,
                iteration=iteration,
            )
            cache_used = False

        # print("Cached used: ", cache_used)
        return response, cache_used, cache_key
        # return self._update_response_with_tracking(
        #     response=response,
        #     start_time=start_time,
        #     cached_response=cache_used,
        #     cache_key=cache_key,
        # ), cache_used

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
        self,
        user_prompt: str,
        system_prompt: str,
        cache: Cache,
        iteration: int = 1,
        encoded_image=None,
    ) -> dict:
        """Get response, parse, and return as string.

        :param user_prompt: The user's prompt.
        :param system_prompt: The system's prompt.
        :param iteration: The iteration number.
        :param cache: The cache to use.
        :param encoded_image: The encoded image to use.

        """
        params = {
            "user_prompt": user_prompt,
            "system_prompt": system_prompt,
            "iteration": iteration,
            "cache": cache,
        }
        if encoded_image:
            params["encoded_image"] = encoded_image

        # breakpoint()
        raw_response, cache_used, cache_key = await self.async_get_raw_response(
            **params
        )
        response = self.parse_response(raw_response)

        try:
            dict_response = json.loads(response)
        except json.JSONDecodeError as e:
            # TODO: Turn into logs to generate issues
            dict_response, success = await repair(response, str(e))
            if not success:
                raise Exception(
                    f"""Even the repair failed. The error was: {e}. The response was: {response}."""
                )

        dict_response.update(
            {
                "cached_used": cache_used,
                "cache_key": cache_key,
                "usage": raw_response.get("usage", {}),
                "raw_model_response": raw_response,
            }
        )
        return dict_response

    get_response = sync_wrapper(async_get_response)

    def cost(self, raw_response: dict[str, Any]) -> float:
        """Return the dollar cost of a raw response."""
        raise NotImplementedError

    #######################
    # SERIALIZATION METHODS
    #######################
    def _to_dict(self) -> dict[str, Any]:
        return {"model": self.model, "parameters": self.parameters}

    @add_edsl_version
    def to_dict(self) -> dict[str, Any]:
        """Convert instance to a dictionary.

        >>> m = LanguageModel.example()
        >>> m.to_dict()
        {'model': 'gpt-4-1106-preview', 'parameters': {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'logprobs': False, 'top_logprobs': 3}, 'edsl_version': '...', 'edsl_class_name': 'LanguageModel'}
        """
        return self._to_dict()

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> Type[LanguageModel]:
        """Convert dictionary to a LanguageModel child instance."""
        from edsl.language_models.registry import get_model_class

        model_class = get_model_class(data["model"])
        # data["use_cache"] = True
        return model_class(**data)

    #######################
    # DUNDER METHODS
    #######################
    def print(self):
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __repr__(self) -> str:
        """Return a string representation of the object."""
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
    def example(cls, test_model: bool = False, canned_response: str = "Hello world"):
        """Return a default instance of the class.

        >>> from edsl.language_models import LanguageModel
        >>> m = LanguageModel.example(test_model = True, canned_response = "WOWZA!")
        >>> isinstance(m, LanguageModel)
        True
        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText(question_text = "What is your name?", question_name = 'example')
        >>> q.by(m).run(cache = False).select('example').first()
        'WOWZA!'
        """
        from edsl import Model

        class TestLanguageModelGood(LanguageModel):
            use_cache = False
            _model_ = "test"
            _parameters_ = {"temperature": 0.5}
            _inference_service_ = InferenceServiceType.TEST.value

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                # return {"message": """{"answer": "Hello, world"}"""}
                return {"message": f'{{"answer": "{canned_response}"}}'}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        if test_model:
            m = TestLanguageModelGood()
            return m
        else:
            return Model(skip_api_key_check=True)


if __name__ == "__main__":
    """Run the module's test suite."""
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    # from edsl.language_models import LanguageModel

    # from edsl.language_models import LanguageModel
    # print(LanguageModel.example())
