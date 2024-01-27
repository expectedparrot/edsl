import pytest
from edsl.Base import RegisterSubclassesMeta, Base
from edsl.questions import QuestionMultipleChoice


class TestBaseModels:
    def test_register_subclasses_meta(self):
        assert RegisterSubclassesMeta.get_registry().keys() == {
            "Survey",
            "Agent",
            "AgentList",
            "Scenario",
        }
        methods = [
            "example",
            "to_dict",
            "from_dict",
            "code",
        ]
        for method in methods:
            with pytest.raises(NotImplementedError):
                getattr(Base, method)()


def create_test_function(child_class):
    @staticmethod
    def base_test_func():
        e = child_class()
        e.show_methods()
        e.show_methods(show_docstrings=False)
        assert hasattr(e, "example")
        assert hasattr(e, "to_dict")
        d = {
            child_class.__name__: child_class,
            "QuestionMultipleChoice": QuestionMultipleChoice,
        }
        assert eval(repr(e), d) == e

    return base_test_func


def create_file_operations_test(child_class):
    import tempfile

    @staticmethod
    def test_file_operations_func():
        e = child_class()
        file = tempfile.NamedTemporaryFile().name
        e.save(file)
        new_w = child_class.load(file)
        assert new_w == e

    return test_file_operations_func


# Dynamically adding test methods for each question type
for child_class_name, child_class in RegisterSubclassesMeta._registry.items():
    base_test_method_name = f"test_Base_{child_class_name}"
    base_test_method = create_test_function(child_class)
    setattr(TestBaseModels, base_test_method_name, base_test_method)

    base_test_method_name = f"test_file_operations_{child_class_name}"
    base_test_method = create_file_operations_test(child_class)
    setattr(TestBaseModels, base_test_method_name, base_test_method)
