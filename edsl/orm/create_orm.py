from .agents_orm import AgentMappedObject, AgentListMappedObject

from ..agents.agent import Agent
from ..agents.agent_list import AgentList

def create_orm(object):
    if isinstance(object, Agent):
        return AgentMappedObject.from_edsl_object(object)
    elif isinstance(object, AgentList):
        return AgentListMappedObject.from_edsl_object(object)
    else:
        raise ValueError(f"Unsupported object type: {type(object)}")