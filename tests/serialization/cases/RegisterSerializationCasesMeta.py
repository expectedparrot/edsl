from abc import ABCMeta
from edsl import Agent, Model, Results, Survey


class RegisterSerializationCasesMeta(ABCMeta):
    _tests = {}

    def __init__(cls, name, bases, dct):
        """Initialize the class and add its examples to the registry."""

        super().__init__(name, bases, dct)

        if name != "SerializationBase":
            object = dct.get("object", "default")

            # Create a dict for object tests
            if object not in cls._tests:
                cls._tests[object] = {}

            # Register the class and its test methods
            cls._tests[object][name] = {"class": cls, "methods": []}
            for attr_name, attr_value in dct.items():
                if callable(attr_value) and attr_name.startswith("test_"):
                    cls._tests[object][name]["methods"].append(attr_name)

    @classmethod
    def get_registered_tests(cls):
        """Return the registry of registered tests."""
        return cls._tests

    @classmethod
    def generate_data(mcs, data: list[dict]):
        """Generate serialization data by running the registered methods. Add data to list."""

        for object, object_tests in mcs._tests.items():
            print(f"Running {object} tests:")
            for class_name, class_info in object_tests.items():
                print(f"Running tests for {class_name}:")
                test_class = class_info["class"]
                instance = test_class()
                for method_name in class_info["methods"]:
                    print(f"Running {method_name}...")
                    test_method = getattr(instance, method_name)
                    test_method()  # Call test method directly
            print()


class SerializationBase(metaclass=RegisterSerializationCasesMeta):
    pass


class ResultsSerializationCases(SerializationBase):
    object = "Results"

    def test_survey_creation(self):
        print("Survey creation test")
        return [("foo", 100), ("bar", 200)]

    def test_survey_response(self):
        print("Survey response test")
        return [("foo", 300), ("bar", 400)]
