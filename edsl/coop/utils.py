from edsl import (
    Agent,
    AgentList,
    Cache,
    Jobs,
    Notebook,
    Results,
    Scenario,
    ScenarioList,
    Survey,
    Study,
)
from edsl.questions import QuestionBase
from typing import Literal, Type, Union

EDSLObject = Union[
    Agent,
    AgentList,
    Cache,
    Jobs,
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
    "job",
    "question",
    "notebook",
    "results",
    "scenario",
    "scenario_list",
    "survey",
    "study",
]

ObjectPage = Literal[
    "agents",
    "agentlists",
    "caches",
    "jobs",
    "notebooks",
    "questions",
    "results",
    "scenarios",
    "scenariolists",
    "surveys",
    "studies",
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
        {
            "object_type": "agent",
            "edsl_class": Agent,
            "object_page": "agents",
        },
        {
            "object_type": "agent_list",
            "edsl_class": AgentList,
            "object_page": "agentlists",
        },
        {
            "object_type": "cache",
            "edsl_class": Cache,
            "object_page": "caches",
        },
        {
            "object_type": "job",
            "edsl_class": Jobs,
            "object_page": "jobs",
        },
        {
            "object_type": "question",
            "edsl_class": QuestionBase,
            "object_page": "questions",
        },
        {
            "object_type": "notebook",
            "edsl_class": Notebook,
            "object_page": "notebooks",
        },
        {
            "object_type": "results",
            "edsl_class": Results,
            "object_page": "results",
        },
        {
            "object_type": "scenario",
            "edsl_class": Scenario,
            "object_page": "scenarios",
        },
        {
            "object_type": "scenario_list",
            "edsl_class": ScenarioList,
            "object_page": "scenariolists",
        },
        {
            "object_type": "survey",
            "edsl_class": Survey,
            "object_page": "surveys",
        },
        {
            "object_type": "study",
            "edsl_class": Study,
            "object_page": "studies",
        },
    ]
    object_type_to_edsl_class = {o["object_type"]: o["edsl_class"] for o in objects}
    edsl_class_to_object_type = {
        o["edsl_class"].__name__: o["object_type"] for o in objects
    }
    object_type_to_object_page = {o["object_type"]: o["object_page"] for o in objects}

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
    def get_object_page_by_object_type(cls, object_type: ObjectType) -> ObjectPage:
        return cls.object_type_to_object_page.get(object_type)
