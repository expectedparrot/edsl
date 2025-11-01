import pytest
import json
import warnings

from edsl.base import RegisterSubclassesMeta, Base
from edsl.questions import QuestionMultipleChoice
from edsl.scenarios import Scenario, ScenarioList
from edsl.surveys import Survey
from edsl.language_models import LanguageModel


class EvalReprFail(Warning):
    "Warning for when eval(repr(e), d) == e fails"


class SaveLoadFail(Warning):
    "Warning for save and load fail"


class TestBaseModels:
    def test_register_subclasses_meta(self):

        for key, value in RegisterSubclassesMeta.get_registry().items():
            assert key in [
                "BaseMacro",
                "Macro",
                "MacroRunOutput",
                "CompositeMacro",
                "Result",
                "Results",
                "Survey",
                "Agent",
                "AgentList",
                "AgentBlueprint",
                "AgentDelta",
                "AgentListDeltas",
                "Scenario",
                "ScenarioList",
                "AgentList",
                "Jobs",
                "Cache",
                "Notebook",
                "ModelList",
                "FileStore",
                "HTMLFileStore",
                "CSVFileStore",
                "PDFFileStore",
                "PNGFileStore",
                "SQLiteFileStore",
                "AgentTraits",
                "RunParameters",
                "SQLList",
                "CoopObjects",
                "CoopJobsObjects",
                "CoopRegularObjects",
                "CoopProlificFilters",
                "Service",
                "FileStoreList",
                "CompareResultsToGold",
                "PerformanceDelta",
                "ResultPairComparison"
            ]

        from edsl.base.exceptions import BaseNotImplementedError

        methods = [
            "example",
            "to_dict",
            "from_dict",
            "code",
        ]
        for method in methods:
            with pytest.raises(BaseNotImplementedError):
                getattr(Base, method)()


def create_test_function(child_class):

    @staticmethod
    def base_test_func():
        from edsl.agents import Agent
        from edsl.questions.question_registry import Question
        from edsl.caching import CacheEntry
        from edsl.language_models import Model
        from edsl.surveys.rules import RuleCollection
        from edsl.surveys.rules import Rule
        from edsl.agents import AgentList
        from edsl.language_models import ModelList
        from edsl.scenarios import FileStore
        from edsl.prompts import Prompt
        from edsl.results import Results
        from edsl.results import Result

        e = child_class.example()
        e.show_methods()
        e.show_methods(show_docstrings=False)
        assert hasattr(e, "example")
        assert hasattr(e, "to_dict")
        d = {
            child_class.__name__: child_class,
            "Agent": Agent,
            "Survey": Survey,
            "QuestionMultipleChoice": QuestionMultipleChoice,
            "CacheEntry": CacheEntry,
            "Question": Question,
            "Model": Model,
            "RuleCollection": RuleCollection,
            "Rule": Rule,
            "LanguageModel": LanguageModel,
            "AgentList": AgentList,
            "ModelList": ModelList,
            "Scenario": Scenario,
            "ScenarioList": ScenarioList,
            "FileStore": FileStore,
            "Prompt": Prompt,
            "Results": Results,
            "Result": Result,
        }

        try:
            if child_class.__class__.__name__ not in [
                "FileStore",
                "AgentTraits",
                "RegisterSubclassesMeta",
            ]:
                assert eval(repr(e), d) == e
        except:
            # breakpoint()
            raise EvalReprFail(f"Failed for {child_class.__class__.__name__}")
        #     warnings.warn(f"Failure with {child_class}:", EvalReprFail)

        # # can serialize to json

        # _ = json.dumps(e.to_dict())

    return base_test_func


def create_file_operations_test(child_class):
    import tempfile

    @staticmethod
    def test_file_operations_func():
        print(f"Now testing {child_class}")
        e = child_class.example()
        # e.print()
        try:
            _ = json.dumps(e.to_dict())
        except:
            warnings.warn(f"JSON failure with {child_class}:", EvalReprFail)

        file = tempfile.NamedTemporaryFile().name
        e.save(file, compress=True)
        try:
            new_w = child_class.load(file + ".json.gz")
        except:
            print(f"Failure at {file}")
            warnings.warn(f"Load failure with {child_class}:", SaveLoadFail)
            raise
        try:
            # Check to see if they are equal by comparing their dictionaries
            assert new_w.to_dict() == e.to_dict()
        except:
            warnings.warn(
                f"Equality failure with (new_w != e) {child_class}:", EvalReprFail
            )
            print("Equality failure - at new_w and e")
            breakpoint()
            raise

    return test_file_operations_func


# Dynamically adding test methods for each question type
for child_class_name, child_class in RegisterSubclassesMeta._registry.items():

    # Skip testing abstract base classes
    if child_class_name in ["CoopObjects"]:
        continue

    base_test_method_name = f"test_Base_{child_class_name}"
    base_test_method = create_test_function(child_class)
    setattr(TestBaseModels, base_test_method_name, base_test_method)

    base_test_method_name = f"test_file_operations_{child_class_name}"
    base_test_method = create_file_operations_test(child_class)
    setattr(TestBaseModels, base_test_method_name, base_test_method)
