import textwrap

DEFAULT_MODEL_CLASS = "edsl.language_models.LanguageModelOpenAIFour"

## All models must be imported here
from edsl.language_models.model_interfaces.LanguageModelOpenAIThreeFiveTurbo import (
    LanguageModelOpenAIThreeFiveTurbo,
)
from edsl.language_models.model_interfaces.LanguageModelOpenAIFour import (
    LanguageModelOpenAIFour,
)
from edsl.language_models.LanguageModel import RegisterLanguageModelsMeta
from edsl.language_models.model_interfaces.GeminiPro import GeminiPro

meta_class_registry = RegisterLanguageModelsMeta.get_registered_classes()

# For compatibility with older versions of EDSL
get_model_class = (
    lambda model_name: RegisterLanguageModelsMeta.model_names_to_classes().get(
        model_name
    )
)


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
    default_model = "gpt-4-1106-preview"

    def __new__(cls, model_name=None, *args, **kwargs):
        # Map index to the respective subclass
        get_model_classes = RegisterLanguageModelsMeta.model_names_to_classes()

        if cls.default_model not in get_model_classes:
            raise ValueError(f"Default model {cls.default_model} not found")

        if model_name is None:
            model_name = cls.default_model
            print(f"No model name provided, using default model: {model_name}")

        subclass = get_model_classes.get(model_name, None)
        if subclass is None:
            raise ValueError(f"No model registered with name {model_name}")

        # Create an instance of the selected subclass
        instance = object.__new__(subclass)
        instance.__init__(*args, **kwargs)
        return instance

    @classmethod
    def available(cls):
        return list(RegisterLanguageModelsMeta.model_names_to_classes().keys())


if __name__ == "__main__":
    available = Model.available()
    m = Model("gpt-4-1106-preview")
    results = m.execute_model_call("Hello world")
    print(results)
