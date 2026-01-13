import textwrap
from collections import defaultdict
from typing import List, Optional, TYPE_CHECKING

from edsl.base import ItemCollection
from ..agent_list import AgentList

if TYPE_CHECKING:
    from edsl.language_models import LanguageModel
    from edsl.surveys import Survey
    from edsl.results import Results


class PersonaGenerator:
    """Handles the generation of persona agents from existing agent collections.

    This class encapsulates the logic for creating persona-based agents that reflect
    the characteristics and survey responses of existing agents.
    """

    DEFAULT_PROMPT = textwrap.dedent(
        """
        Please write a statement of your economic views, focusing on your recent survey answers.
        It should focus not just on a particular issue but your general approach to policy issues. For example, do you 
        tend to favor active government interventions or take more of a market-knows-best approach?
        """
    )

    def __init__(
        self,
        agent_generation_prompt: Optional[str] = None,
        agent_list_names: Optional[List[str]] = None,
        collection_name: Optional[str] = None,
    ):
        """Initialize the PersonaGenerator with configuration options.

        Args:
            agent_generation_prompt (Optional[str]): The prompt used to generate persona descriptions.
                If None, uses the default economic views prompt.
            agent_list_names (Optional[List[str]]): Names for the generated agent lists.
                If None, names will be generated based on source list names.
            collection_name (Optional[str]): Name for the new collection.
                If None, will be generated based on source collection name.

        Example:
            >>> generator = PersonaGenerator(
            ...     agent_generation_prompt="Describe your personality.",
            ...     collection_name="Generated Personas"
            ... )
            >>> isinstance(generator, PersonaGenerator)
            True
        """
        self.agent_generation_prompt = agent_generation_prompt or self.DEFAULT_PROMPT
        self.agent_list_names = agent_list_names
        self.collection_name = collection_name

    def generate_from_collection(
        self, source_collection: "AgentListCollection"
    ) -> "AgentListCollection":
        """Generate persona agents from a source AgentListCollection.

        Args:
            source_collection (AgentListCollection): The collection to generate personas from.

        Returns:
            AgentListCollection: A new collection containing the generated persona agents.
        """
        # Set up default names if not provided
        agent_list_names = self._get_agent_list_names(source_collection)
        collection_name = self._get_collection_name(source_collection)

        # Generate persona responses from all agents
        from edsl.questions import QuestionFreeText

        q = QuestionFreeText(
            question_text=self.agent_generation_prompt, question_name="persona"
        )
        persona_results = q.by(source_collection.combined_agent_list()).run(
            verbose=False
        )

        # Convert results to agent list and organize by original list index
        persona_agent_list = persona_results.select(
            "agent.agent_name", "persona", "agent_list_index"
        ).to_agent_list()
        persona_agent_list.give_names("agent_name")

        # Group agents by their original list index
        grouped_agents = defaultdict(AgentList)
        for agent in persona_agent_list:
            index = agent.traits.pop("agent_list_index")
            grouped_agents[index].append(agent)
            grouped_agents[index].name = agent_list_names[index]

        return AgentListCollection(list(grouped_agents.values()), name=collection_name)

    def _get_agent_list_names(
        self, source_collection: "AgentListCollection"
    ) -> List[str]:
        """Generate default names for agent lists if not provided."""
        if self.agent_list_names is not None:
            return self.agent_list_names
        names = []
        for i in range(len(source_collection)):
            agent_list = source_collection[i]
            if hasattr(agent_list, "name") and agent_list.name is not None:
                names.append(f"Persona generated from {agent_list.name}")
            else:
                names.append(f"Persona generated from Agent List {i}")
        return names

    def _get_collection_name(
        self, source_collection: "AgentListCollection"
    ) -> Optional[str]:
        """Generate default collection name if not provided."""
        if self.collection_name is not None:
            return self.collection_name
        if hasattr(source_collection, "name") and source_collection.name is not None:
            return f"Generated from {source_collection.name}"
        return None


class AgentListCollection(ItemCollection):
    """Collection of AgentList objects with operations for managing multiple agent lists.

    This class extends ItemCollection to provide specialized functionality for working
    with collections of AgentList objects, including combining them, running surveys
    across all agents, and generating persona-based agents.

    Attributes:
        item_class: The class type for items in this collection (AgentList).

    Example:
        >>> from edsl.agents import AgentList
        >>> collection = AgentListCollection([AgentList.example(), AgentList.example()])
        >>> len(collection)
        2
    """

    item_class = AgentList

    def combined_agent_list(self) -> "AgentList":
        """Returns a single agent list with an agent_list_index trait for each agent list in the collection.

        Each agent in the combined list will have an 'agent_list_index' trait indicating
        which original agent list it came from.

        Returns:
            AgentList: A single AgentList containing all agents from all lists in the collection,
                      with each agent having an 'agent_list_index' trait.

        Example:
            >>> collection = AgentListCollection.example()
            >>> combined = collection.combined_agent_list()
            >>> isinstance(combined, AgentList)
            True
            >>> # All agents should have the agent_list_index trait
            >>> all(hasattr(agent, 'traits') for agent in combined)
            True
        """
        new_list = []
        for iteration, item in enumerate(self):
            new_list.extend(item.add_trait("agent_list_index", iteration))
        return AgentList(new_list)

    def take_survey(
        self, survey: "Survey", model: Optional["LanguageModel"] = None
    ) -> "Results":
        """All the agents in the collection are run through the survey.

        The results are returned as a ResultsList, with each Results object containing
        the results for a single agent list.

        Args:
            survey (Survey): The survey to be administered to all agents in the collection.

        Returns:
            ResultsList: A list of Results objects, one for each agent list in the collection.
                        Each Results object contains the survey responses from agents in that list.
        """
        from edsl.language_models import Model
        from edsl.results import Results, ResultsList

        if model is None:
            model = Model()
        results = survey.by(self.combined_agent_list()).by(model).run(verbose=False)
        d = defaultdict(list)
        for result in results:
            index = result.agent.traits.pop("agent_list_index")
            d[index].append(result)
        results_list = [
            Results(survey=results.survey, data=d[i]) for i in range(len(self))
        ]
        # Set names on results using event-based method (Results is immutable)
        for i in range(len(results_list)):
            if hasattr(self[i], "name") and self[i].name is not None:
                results_list[i] = results_list[i].set_name(self[i].name)

        return ResultsList(results_list)

    def generate_persona_agents(
        self,
        agent_generation_prompt: Optional[str] = None,
        agent_list_names: Optional[List[str]] = None,
        collection_name: Optional[str] = None,
    ) -> "AgentListCollection":
        """Generate persona agents for each agent list in the collection.

        This method creates new agents based on the existing agents' characteristics,
        using a prompt to generate persona descriptions that reflect their survey responses.

        Args:
            agent_generation_prompt (Optional[str]): The prompt used to generate persona descriptions.
                If None, uses a default prompt about economic views and policy approaches.
            agent_list_names (Optional[List[str]]): Names for the generated agent lists.
                If None, generates names based on existing list names.
            collection_name (Optional[str]): Name for the new collection.
                If None and this collection has a name, generates a name based on it.

        Returns:
            AgentListCollection: A new collection containing the generated persona agents,
                                organized into agent lists corresponding to the original lists.

        """
        generator = PersonaGenerator(
            agent_generation_prompt=agent_generation_prompt,
            agent_list_names=agent_list_names,
            collection_name=collection_name,
        )
        return generator.generate_from_collection(self)

    @classmethod
    def example(cls) -> "AgentListCollection":
        """Create an example AgentListCollection for testing and demonstration purposes.

        Returns:
            AgentListCollection: A collection containing two example AgentList objects.

        Example:
            >>> collection = AgentListCollection.example()
            >>> isinstance(collection, AgentListCollection)
            True
            >>> len(collection) == 2
            True
            >>> collection.name == "Example AgentListCollection"
            True
        """
        return cls(
            [AgentList.example(), AgentList.example()],
            name="Example AgentListCollection",
        )
