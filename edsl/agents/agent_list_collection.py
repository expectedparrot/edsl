import textwrap
from collections import defaultdict
from typing import List, Optional

from ..base import ItemCollection

from . import AgentList
from ..results import Results, ResultsList
from ..surveys import Survey
from ..questions import QuestionFreeText

class AgentListCollection(ItemCollection):
    item_class = AgentList

    def combined_agent_list(self) -> 'AgentList':
        """Returns a single agent list with an agent_list_index trait for each agent list in the collection."""
        new_list = []
        for iteration, item in enumerate(self):
            new_list.extend(item.add_trait("agent_list_index", iteration))
        return AgentList(new_list)

    def take_survey(self, survey: 'Survey') -> 'Results':
        """All the agents in the collection are run through the survey. 
        
        The results are returned as a ResultsList, with each Results object containing the results for a single agent list."""
        results = survey.by(self.combined_agent_list()).run(verbose = False)
        d = defaultdict(list)
        for result in results:
            index = result.agent.traits.pop('agent_list_index')
            d[index].append(result)
            # Give the results object for that list same name as the agent list
            #if hasattr(self[index], 'name') and self[index].name is not None:
            #    d[index].name = self[index].name
        results_list = [Results(survey = results.survey, data = d[i]) for i in range(len(self))]
        # append names to results list
        for i, results in enumerate(results_list):
            if hasattr(self[i], 'name') and self[i].name is not None:
                results.name = self[i].name

        return ResultsList(results_list)
    
    def generate_persona_agents(self, agent_generation_prompt: Optional[str] = None, 
                                agent_list_names: Optional[List[str]] = None,
                                collection_name: Optional[str] = None
                                ) -> 'AgentListCollection':
        """Generate persona agents for each agent list in the collection."""
        if agent_list_names is None:
            agent_list_names = ["Persona generated from " + self[i].name for i in range(len(self))]
        if agent_generation_prompt is None:
            agent_generation_prompt = textwrap.dedent("""
            Please write a statement of your economic views, focusing on your recent survey answers.
            It should focus not just on a particular issue but your general approach to policy issues. For example, do you 
            tend to favor active government interventions or take more of a market-knows-best approach?
            """)
        q = QuestionFreeText(question_text = agent_generation_prompt, question_name = "persona")
        persona_results = q.by(self.combined_agent_list()).run(verbose = False)
        persona_agent_list = persona_results.select('agent.agent_name', 'persona', 'agent_list_index').to_agent_list()
        persona_agent_list.give_names('agent_name')
        d = defaultdict(AgentList)
        for agent in persona_agent_list:
            index = agent.traits.pop('agent_list_index')
            d[index].append(agent)
            d[index].name = agent_list_names[index]

        if collection_name is None and hasattr(self, 'name') and self.name is not None:
            collection_name = "Generated from " + self.name

        return AgentListCollection(list(d.values()), name = collection_name)
