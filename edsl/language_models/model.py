import textwrap
from random import random
from typing import Optional, TYPE_CHECKING, List

from ..utilities import PrettyList
from ..config import CONFIG
from .exceptions import LanguageModelValueError

from ..inference_services import (InferenceServicesCollection, 
                                  AvailableModels, InferenceServiceABC, InferenceServiceError, default)

from ..enums import InferenceServiceLiteral

if TYPE_CHECKING:
    from ..dataset import Dataset


def get_model_class(
    model_name,
    registry: Optional[InferenceServicesCollection] = None,
    service_name: Optional[InferenceServiceLiteral] = None,
):
    registry = registry or default
    try:
        factory = registry.create_model_factory(model_name, service_name=service_name)
        return factory
    except (InferenceServiceError, Exception) as e:
        return Model._handle_model_error(model_name, e)

class Meta(type):
    def __repr__(cls):
        return textwrap.dedent(
            f"""\
        Available models: {cls.available()}
        
        To create an instance, you can do: 
        >>> m = Model('gpt-4-1106-preview', temperature=0.5, ...)
        
        To get the default model, you can leave out the model name. 
        To see the available models, you can do:
        >>> Model.available()

        Or to see the models for a specific service, you can do:
        >>> Model.available(service='openai')
        """
        )


class Model(metaclass=Meta):
    default_model = CONFIG.get("EDSL_DEFAULT_MODEL")
    _registry: InferenceServicesCollection = None  # Class-level registry storage

    @classmethod
    def get_registry(cls) -> InferenceServicesCollection:
        """Get the current registry or initialize with default if None"""
        if cls._registry is None:
            cls._registry = default
        return cls._registry

    @classmethod
    def set_registry(cls, registry: InferenceServicesCollection) -> None:
        """Set a new registry"""
        cls._registry = registry

    @classmethod
    def _handle_model_error(cls, model_name: str, error: Exception):
        """Handle errors from model creation and execution with notebook-aware behavior."""
        if isinstance(error, InferenceServiceError):
            services = [s._inference_service_ for s in cls.get_registry().services]
            message = (
                f"Model '{model_name}' not found in any services.\n"
                "It is likely that our registry is just out of date.\n"
                "Simply adding the service name to your model call should fix this.\n"
                f"Available services are: {services}\n"
                f"To specify a model with a service, use:\n"
                f'Model("{model_name}", service_name="<service_name>")'
            )
        else:
            message = f"An error occurred: {str(error)}"

        # Check if we're in a notebook environment
        try:
            get_ipython()
            print(message)
            return None
        except NameError:
            # Not in a notebook, raise the exception
            if isinstance(error, InferenceServiceError):
                raise InferenceServiceError(message)
            raise error

    def __new__(
        cls,
        model_name: Optional[str] = None,
        service_name: Optional[InferenceServiceLiteral] = None,
        registry: Optional[InferenceServicesCollection] = None,
        *args,
        **kwargs,
    ):
        """Instantiate a new language model.
        >>> Model()
        Model(...)
        """
        # Map index to the respective subclass
        if model_name is None:
            model_name = cls.default_model

        if registry is not None:
            cls.set_registry(registry)

        if isinstance(model_name, int):  # can refer to a model by index
            model_name = cls.available(name_only=True)[model_name]

        try:
            factory = cls.get_registry().create_model_factory(
                model_name, service_name=service_name
            )
            return factory(*args, **kwargs)
        except (InferenceServiceError, Exception) as e:
            return cls._handle_model_error(model_name, e)

    @classmethod
    def add_model(cls, service_name, model_name) -> None:
        cls.get_registry().add_model(service_name, model_name)

    @classmethod
    def service_classes(cls) -> List["InferenceServiceABC"]:
        """Returns a list of service classes.

        >>> Model.service_classes()
        [...]
        """
        return [r for r in cls.services()]

    @classmethod
    def services(cls, name_only: bool = False) -> List[str]:
        """Returns a list of services excluding 'test', sorted alphabetically.

        >>> Model.services()
        [...]
        """
        return PrettyList(
            sorted(
                [
                    [r._inference_service_]
                    for r in cls.get_registry().services
                    if r._inference_service_.lower() != "test"
                ]
            ),
            columns=["Service Name"],
        )

    @classmethod
    def services_with_local_keys(cls) -> set:
        """Returns a list of services for which the user has local keys."""
        return set(cls.key_info().select("service").to_list())

    @classmethod
    def key_info(cls, obscure_api_key: bool = True) -> "Dataset":
        """Returns a dataset of local key information."""
        from ..key_management import KeyLookupCollection
        from ..scenarios import Scenario, ScenarioList

        klc = KeyLookupCollection()
        klc.add_key_lookup(fetch_order=None)
        sl = ScenarioList()
        for service, entry in list(klc.data.values())[0].items():
            sl.append(Scenario({"service": service} | entry.to_dict()))
        if obscure_api_key:
            for service in sl:
                service["api_token"] = (
                    service["api_token"][:4] + "..." + service["api_token"][-4:]
                )
        return sl.to_dataset()

    @classmethod
    def search_models(cls, search_term: str):
        return cls.available(search_term=search_term)

    @classmethod
    def all_known_models(cls) -> "AvailableModels":
        return cls.get_registry().available()

    @classmethod
    def available_with_local_keys(cls):
        services_with_local_keys = set(cls.key_info().select("service").to_list())
        return [
            m
            for m in cls.get_registry().available()
            if m.service_name in services_with_local_keys
        ]

    @classmethod
    def available(
        cls,
        search_term: str = None,
        name_only: bool = False,
        service: Optional[str] = None,
        force_refresh: bool = False,
    ):
        """Get available models

        >>> Model.available()
        [...]
        >>> Model.available(service='openai')
        [...]
        """
        # if search_term is None and service is None:
        #     print("Getting available models...")
        #     print("You have local keys for the following services:")
        #     print(cls.services_with_local_keys())
        #     print("\n")
        #     print("To see models by service, use the 'service' parameter.")
        #     print("E.g., Model.available(service='openai')")
        #     return None

        if service is not None:
            known_services = [x[0] for x in cls.services(name_only=True)]
            if service not in known_services:
                raise LanguageModelValueError(
                    f"Service {service} not found in available services. Available services are: {known_services}"
                )

        full_list = cls.get_registry().available(
            service=service, force_refresh=force_refresh
        )

        if search_term is None:
            if name_only:
                return PrettyList(
                    [m.model_name for m in full_list],
                    columns=["Model Name"],
                )
            else:
                return PrettyList(
                    [[m.model_name, m.service_name] for m in full_list],
                    columns=["Model Name", "Service Name"],
                )
        else:
            filtered_results = [
                m
                for m in full_list
                if search_term in m.model_name or search_term in m.service_name
            ]
            if name_only:
                return PrettyList(
                    [m.model_name for m in filtered_results],
                    columns=["Model Name"],
                )
            else:
                return PrettyList(
                    [[m.model_name, m.service_name] for m in full_list],
                    columns=["Model Name", "Service Name"],
                )

    @classmethod
    def check_models(cls, verbose=False):
        print("Checking all available models...\n")
        for model in cls.available(name_only=True):
            print(f"Now checking: {model}")
            try:
                m = cls(model)
            except Exception as e:
                print(f"Error creating instance of {model}: {e}")
                continue
            try:
                results = m.hello(verbose)
                if verbose:
                    print(f"Results from model call: {results}")
            except Exception as e:
                print(f"Error calling 'hello' on {model}: {e}")
                continue
            print("OK!")
            print("\n")

    @classmethod
    def check_working_models(
        cls,
        service: Optional[str] = None,
        works_with_text: Optional[bool] = None,
        works_with_images: Optional[bool] = None,
    ) -> list[dict]:
        from ..coop import Coop

        c = Coop()
        working_models = c.fetch_working_models()

        if service is not None:
            working_models = [m for m in working_models if m["service"] == service]
        if works_with_text is not None:
            working_models = [
                m for m in working_models if m["works_with_text"] == works_with_text
            ]
        if works_with_images is not None:
            working_models = [
                m for m in working_models if m["works_with_images"] == works_with_images
            ]

        if len(working_models) == 0:
            return []

        else:
            return PrettyList(
                [
                    [
                        m["service"],
                        m["model"],
                        m["works_with_text"],
                        m["works_with_images"],
                        m["usd_per_1M_input_tokens"],
                        m["usd_per_1M_output_tokens"],
                    ]
                    for m in working_models
                ],
                columns=[
                    "Service",
                    "Model",
                    "Works with text",
                    "Works with images",
                    "Price per 1M input tokens (USD)",
                    "Price per 1M output tokens (USD)",
                ],
            )

    @classmethod
    def example(cls, randomize: bool = False) -> "Model":
        """
        Returns an example Model instance.

        >>> Model.example()
        Model(...)

        :param randomize: If True, the temperature is set to a random decimal between 0 and 1.
        """
        temperature = 0.5 if not randomize else round(random(), 2)
        model_name = cls.default_model
        return cls(model_name, temperature=temperature)


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)

