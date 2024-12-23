import textwrap
from random import random
from edsl.config import CONFIG
from functools import lru_cache
from edsl.utilities.PrettyList import PrettyList
from typing import Optional


def get_model_class(model_name, registry=None):
    from edsl.inference_services.registry import default

    registry = registry or default
    factory = registry.create_model_factory(model_name)
    return factory


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
        """
        )


class Model(metaclass=Meta):
    default_model = CONFIG.get("EDSL_DEFAULT_MODEL")

    def __new__(
        cls, model_name=None, registry=None, service_name=None, *args, **kwargs
    ):
        # Map index to the respective subclass
        if model_name is None:
            model_name = (
                cls.default_model
            )  # when model_name is None, use the default model, set in the config file
        from edsl.inference_services.registry import default

        registry = registry or default

        if isinstance(model_name, int):  # can refer to a model by index
            model_name = cls.available(name_only=True)[model_name]

        factory = registry.create_model_factory(model_name, service_name=service_name)
        return factory(*args, **kwargs)

    @classmethod
    def add_model(cls, service_name, model_name):
        from edsl.inference_services.registry import default

        registry = default
        registry.add_model(service_name, model_name)

    @classmethod
    def service_classes(cls, registry=None):
        from edsl.inference_services.registry import default

        registry = registry or default
        return [r for r in registry.services]

    @classmethod
    def services(cls, registry=None):
        from edsl.inference_services.registry import default

        registry = registry or default
        return PrettyList(
            [r._inference_service_ for r in registry.services], columns=["Service Name"]
        )

    @classmethod
    def key_info(cls):
        from edsl.language_models.key_management import KeyLookupCollection
        from edsl.scenarios import Scenario, ScenarioList

        klc = KeyLookupCollection()
        klc.add_key_lookup(fetch_order=None)
        sl = ScenarioList()
        for service, entry in list(klc.data.values())[0].items():
            sl.append(Scenario({"service": service} | entry.to_dict()))
        return sl.to_dataset()

    @classmethod
    def available(
        cls,
        search_term: str = None,
        name_only: bool = False,
        registry=None,
        service: Optional[str] = None,
    ):
        from edsl.inference_services.registry import default

        registry = registry or default
        # full_list = registry.available()

        if service is not None:
            if service not in cls.services(registry=registry):
                raise ValueError(f"Service {service} not found in available services.")

        # import time
        # start = time.time()
        full_list = registry.available(service=service)
        # end = time.time()
        # print(f"Time taken to get available models: {end-start}")

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
    def example(cls, randomize: bool = False) -> "Model":
        """
        Returns an example Model instance.

        :param randomize: If True, the temperature is set to a random decimal between 0 and 1.
        """
        temperature = 0.5 if not randomize else round(random(), 2)
        model_name = cls.default_model
        return cls(model_name, temperature=temperature)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    available = Model.available()
    m = Model("gpt-4-1106-preview")
    results = m.execute_model_call("Hello world")
    print(results)
