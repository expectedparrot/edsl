from typing import List, Optional, Dict, TYPE_CHECKING
from collections import UserList
import uuid

from ..base import ItemCollection
from ..results import Results

if TYPE_CHECKING:
    from ..agents import AgentList

class ResultsList(ItemCollection): 
    item_class = Results

    def create_agents(self, agent_name_fields: Optional[List[str]] = None, name: Optional[str] = None) -> 'AgentList':
        # Lazy import to avoid circular dependency
        from ..agents import AgentList
        
        if agent_name_fields is None:
            agent_name_fields = ["last_name", "first_name"]

        list_of_lists = []
        for item in self:
            al = AgentList.from_results(item).with_names(*agent_name_fields)
            list_of_lists.append(al)

        if len(list_of_lists) == 1:
            joined_agents = list_of_lists[0]
        else:
            joined_agents = AgentList.join(*list_of_lists)

        if name is not None:
            joined_agents.name = name
        elif hasattr(self, 'name') and self.name is not None:
            joined_agents.name = "Created from " + self.name
        
        return joined_agents
    
    def agent_answers_by_question(self, agent_key_fields: Optional[List[str]] = None, separator: str = ",") -> Dict[str, Dict[str, str]]:
        """Returns a dictionary of agent answers.
        
        The keys are the agent names and the values are the answers.
        """
        return {item.name: item.agent_answers_by_question(agent_key_fields, separator) for item in self}
