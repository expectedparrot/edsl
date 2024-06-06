from edsl import Agent, AgentList, Cache, Jobs, Results, Scenario, ScenarioList, Survey
from edsl.questions import QuestionBase
from typing import Literal, Type, Union

EDSLObject = Union[
    Agent,
    AgentList,
    Cache,
    Jobs,
    Type[QuestionBase],
    Results,
    Scenario,
    ScenarioList,
    Survey,
]

ObjectType = Literal[
    "agent",
    "agent_list",
    "cache",
    "job",
    "question",
    "results",
    "scenario",
    "scenario_list",
    "survey",
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
        {"object_type": "job", "edsl_class": Jobs},
        {"object_type": "question", "edsl_class": QuestionBase},
        {"object_type": "results", "edsl_class": Results},
        {"object_type": "scenario", "edsl_class": Scenario},
        {"object_type": "scenario_list", "edsl_class": ScenarioList},
        {"object_type": "survey", "edsl_class": Survey},
    ]
    object_type_to_edsl_class = {
        item["object_type"]: item["edsl_class"] for item in objects
    }
    edsl_class_to_object_type = {
        item["edsl_class"].__name__: item["object_type"] for item in objects
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
