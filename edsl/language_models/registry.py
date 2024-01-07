import importlib

DEFAULT_MODEL_CLASS = "edsl.language_models.LanguageModelOpenAIFour"

# TODO: Use a meta-class to register models
model_names_to_classes = {
    "gpt-3.5-turbo": "edsl.language_models.LanguageModelOpenAIThreeFiveTurbo",
    "gpt-4": "edsl.language_models.LanguageModelOpenAIFour",
}


def get_model_class(model_name):
    "Returns the class for a given model name"
    class_path = model_names_to_classes.get(model_name, DEFAULT_MODEL_CLASS)
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls


if __name__ == "__main__":
    model_class = get_model_class("gpt-4")
    model = model_class()
    results = model.execute_model_call("Hello world")
    print(results)
