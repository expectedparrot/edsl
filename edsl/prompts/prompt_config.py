"""This file contains the configuration for the prompt generation."""
from enum import Enum

NEGATIVE_INFINITY = float("-inf")


class AttributeTypes(Enum):
    """The types of attributes that a prompt can have."""

    COMPONENT_TYPE = "component_type"
    MODEL = "model"
    QUESTION_TYPE = "question_type"


class ComponentTypes(Enum):
    """The types of attributes that a prompt can have."""

    TEST = "test"
    GENERIC = "generic"
    QUESTION_DATA = "question_data"
    QUESTION_INSTRUCTIONS = "question_instructions"
    AGENT_INSTRUCTIONS = "agent_instructions"
    AGENT_PERSONA = "agent_persona"
    SURVEY_INSTRUCTIONS = "survey_instructions"
    SURVEY_DATA = "survey_data"


names_to_component_types = {v.value: v for k, v in ComponentTypes.__members__.items()}

C2A = {
    ComponentTypes.QUESTION_INSTRUCTIONS: [
        AttributeTypes.QUESTION_TYPE,
        AttributeTypes.MODEL,
    ],
    ComponentTypes.AGENT_INSTRUCTIONS: [AttributeTypes.MODEL],
}
