import pytest

# from edsl import Agent, Scenario

from edsl.Base import RegisterSubclassesMeta
from edsl.questions import QuestionMultipleChoice


class TestBaseModels:
    pass


## The repr test is excluded for Survey because it is not working
## for some reason.

exclude_repr_test = ["Survey"]


def create_test_function(child_class):
    @staticmethod
    def test_func():
        print(f"Now testing: {child_class}")
        try:
            e = child_class()
            assert hasattr(e, "example")
            assert hasattr(e, "to_dict")
            d = {
                child_class.__name__: child_class,
                "QuestionMultipleChoice": QuestionMultipleChoice,
            }
            if child_class.__name__ not in exclude_repr_test:
                assert eval(repr(e), d) == e
        except Exception as e:
            pytest.fail(f"Error running {child_class}: {e}")

    return test_func


# Dynamically adding test methods for each question type
for child_class_name, child_class in RegisterSubclassesMeta._registry.items():
    test_method_name = f"test_{child_class_name}"
    print("Now testing: ", child_class_name)
    test_method = create_test_function(child_class)
    setattr(TestBaseModels, test_method_name, test_method)
