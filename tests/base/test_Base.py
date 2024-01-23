import pytest
from edsl.Base import RegisterSubclassesMeta
from edsl.questions import QuestionMultipleChoice


class TestBaseModels:
    pass


def create_test_function(child_class):
    @staticmethod
    def base_test_func():
        e = child_class()
        assert hasattr(e, "example")
        assert hasattr(e, "to_dict")
        d = {
            child_class.__name__: child_class,
            "QuestionMultipleChoice": QuestionMultipleChoice,
        }
        assert eval(repr(e), d) == e

    return base_test_func


# Dynamically adding test methods for each question type
for child_class_name, child_class in RegisterSubclassesMeta._registry.items():
    base_test_method_name = f"test_Base_{child_class_name}"
    base_test_method = create_test_function(child_class)
    setattr(TestBaseModels, base_test_method_name, base_test_method)
