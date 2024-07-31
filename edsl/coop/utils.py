from edsl import (
    Agent,
    AgentList,
    Cache,
    ModelList,
    Notebook,
    Results,
    Scenario,
    ScenarioList,
    Survey,
    Study,
)
from edsl.language_models import LanguageModel
from edsl.questions import QuestionBase
from typing import Literal, Optional, Type, Union

EDSLObject = Union[
    Agent,
    AgentList,
    Cache,
    LanguageModel,
    ModelList,
    Notebook,
    Type[QuestionBase],
    Results,
    Scenario,
    ScenarioList,
    Survey,
    Study,
]

ObjectType = Literal[
    "agent",
    "agent_list",
    "cache",
    "model",
    "model_list",
    "notebook",
    "question",
    "results",
    "scenario",
    "scenario_list",
    "survey",
    "study",
]


RemoteJobStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
]

VisibilityType = Literal[
    "private",
    "public",
    "unlisted",
]


class ObjectRegistry:
    """
    Utility class to map object types to database models.
    """

    objects = [
        {"object_type": "agent", "edsl_class": Agent},
        {"object_type": "agent_list", "edsl_class": AgentList},
        {"object_type": "cache", "edsl_class": Cache},
        {"object_type": "model", "edsl_class": LanguageModel},
        {"object_type": "model_list", "edsl_class": ModelList},
        {"object_type": "notebook", "edsl_class": Notebook},
        {"object_type": "question", "edsl_class": QuestionBase},
        {"object_type": "results", "edsl_class": Results},
        {"object_type": "scenario", "edsl_class": Scenario},
        {"object_type": "scenario_list", "edsl_class": ScenarioList},
        {"object_type": "survey", "edsl_class": Survey},
        {"object_type": "study", "edsl_class": Study},
    ]
    object_type_to_edsl_class = {o["object_type"]: o["edsl_class"] for o in objects}
    edsl_class_to_object_type = {
        o["edsl_class"].__name__: o["object_type"] for o in objects
    }

    @classmethod
    def get_object_type_by_edsl_class(cls, edsl_object: EDSLObject) -> ObjectType:
        if isinstance(edsl_object, type):
            edsl_class_name = edsl_object.__name__
        else:
            edsl_class_name = type(edsl_object).__name__
        if edsl_class_name.startswith("Question"):
            edsl_class_name = "QuestionBase"
        object_type = cls.edsl_class_to_object_type.get(edsl_class_name)
        if object_type is None:
            raise ValueError(f"Object type not found for {edsl_object=}")
        return object_type

    @classmethod
    def get_edsl_class_by_object_type(cls, object_type: ObjectType) -> EDSLObject:
        EDSL_object = cls.object_type_to_edsl_class.get(object_type)
        if EDSL_object is None:
            raise ValueError(f"EDSL class not found for {object_type=}")
        return EDSL_object

    @classmethod
    def get_registry(
        cls,
        subclass_registry: Optional[dict] = None,
        exclude_classes: Optional[list] = None,
    ) -> dict:
        """
        Return the registry of objects.

        Exclude objects that are already registered in subclass_registry.
        This allows the user to isolate Coop-only objects.

        Also exclude objects if their class name is in the exclude_classes list.
        """

        if subclass_registry is None:
            subclass_registry = {}
        if exclude_classes is None:
            exclude_classes = []

        return {
            class_name: o["edsl_class"]
            for o in cls.objects
            if (class_name := o["edsl_class"].__name__) not in subclass_registry
            and class_name not in exclude_classes
        }
