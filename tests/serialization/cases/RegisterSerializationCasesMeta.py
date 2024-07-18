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

            # Identify and register test methods
            for attr_name, attr_value in dct.items():
                if callable(attr_value) and attr_name.startswith("test_"):
                    cls._tests[object][attr_name] = attr_value

    @classmethod
    def get_registered_tests(cls):
        """Return the registry of registered tests."""
        return cls._tests

    @classmethod
    def generate_data(mcs, data: list[dict]):
        """Generate serialization data by running the registered methods. Add data to list."""

        for object, object_tests in mcs._tests.items():
            print(f"Running {object} tests:")
            for test_name, test_func in object_tests.items():
                print(f"Running {test_name}...")
                case_data = test_func()
                data.append({"class_name": object, "dict": dict(case_data)})
            print()


class SerializationBase(metaclass=RegisterSerializationCasesMeta):
    pass


class ResultsSerializationCases(SerializationBase):
    object = "Results"

    @staticmethod
    def test_survey_creation():
        print("Survey creation test")
        return [("foo", 100), ("bar", 200)]

    @staticmethod
    def test_survey_response():
        print("Survey response test")
        return [("foo", 300), ("bar", 400)]
