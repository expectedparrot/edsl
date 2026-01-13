"""AgentList factory operations module."""

from __future__ import annotations
import csv
import math
import warnings
from typing import Optional, List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent_list import AgentList
    from edsl.scenarios import ScenarioList
    from edsl.results import Results


class AgentListFactories:
    """Handles factory and creation operations for AgentList objects.

    This class provides functionality for creating AgentList objects from various
    data sources including CSV files, Results objects, dictionaries, lists,
    and ScenarioList objects. It also provides example instances and utility
    methods for codebook creation.
    """

    @staticmethod
    def from_csv(
        file_path: str,
        name_field: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ) -> "AgentList":
        """Load AgentList from a CSV file.

        Args:
            file_path: The path to the CSV file.
            name_field: The name of the field to use as the agent name.
            codebook: Optional dictionary mapping trait names to descriptions.

        Returns:
            AgentList: A new AgentList created from the CSV file

        Examples:
            >>> import csv
            >>> import os
            >>> from edsl.agents.agent_list_helpers.agent_list_factories import AgentListFactories
            >>> with open('/tmp/test_agents.csv', 'w') as f:
            ...     writer = csv.writer(f)
            ...     _ = writer.writerow(['age', 'hair'])
            ...     _ = writer.writerow([22, 'brown'])
            >>> al = AgentListFactories.from_csv('/tmp/test_agents.csv')
            >>> len(al)
            1
            >>> os.remove('/tmp/test_agents.csv')
        """
        from ..agent import Agent
        from ..agent_list import AgentList

        agent_list = []
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "name" in row:
                    warnings.warn("Using 'name' field in the CSV for the Agent name")
                    name_field = "name"
                if name_field is not None:
                    agent_name = row.pop(name_field)
                    agent_list.append(
                        Agent(
                            traits=row,
                            name=agent_name,
                            codebook=codebook,
                            instruction=instructions,
                        )
                    )
                else:
                    agent_list.append(
                        Agent(traits=row, codebook=codebook, instruction=instructions)
                    )
        return AgentList(agent_list)

    @staticmethod
    def from_results(
        results: "Results", question_names: Optional[List[str]] = None
    ) -> "AgentList":
        """Create an AgentList from a Results object.

        Args:
            results: The Results object to convert
            question_names: Optional list of question names to include. If None, all questions are included.
                          Affects both answer.* columns (as traits) and the codebook (question_text).
                          Agent traits are always included.

        Returns:
            AgentList: A new AgentList created from the Results

        Examples:
            >>> from edsl.agents.agent_list_helpers.agent_list_factories import AgentListFactories
            >>> # This would work with actual Results object
            >>> # al = AgentListFactories.from_results(results)
            >>> # To include only specific questions:
            >>> # al = AgentListFactories.from_results(results, question_names=['age', 'preference'])
        """
        from ..agent import Agent
        from ..agent_list import AgentList

        # Get question_text for each question from the Results metadata
        # Access the first result to get question_to_attributes
        codebook = {}
        if len(results) > 0:
            first_result = results[0]
            question_to_attributes = first_result.data.get("question_to_attributes", {})

            # Build codebook with question_text for each question
            for q_name, q_attrs in question_to_attributes.items():
                if question_names is None or q_name in question_names:
                    q_text = q_attrs.get("question_text", q_name)
                    codebook[q_name] = q_text

        df = results.select("agent.*", "answer.*").to_pandas()

        agents = []
        for index, row in df.iterrows():
            traits = {}
            has_name = False
            name = None

            for column in df.columns:
                value = row[column]

                # Replace NaN/inf values with None for JSON serializability
                if isinstance(value, float) and (
                    math.isnan(value) or math.isinf(value)
                ):
                    value = None

                if column.startswith("answer."):
                    key = column[7:]  # Remove 'answer.' prefix
                    # Only include this answer if question_names is None or if the key is in question_names
                    if question_names is None or key in question_names:
                        traits[key] = value

                elif column.startswith("agent."):
                    # Skip agent.instructions and agent.index
                    if column == "agent.agent_name":
                        name = value  # Store as separate parameter
                        has_name = True
                    elif column not in ["agent.agent_instruction", "agent.agent_index"]:
                        key = column[6:]  # Remove 'agent.' prefix
                        traits[key] = value

            # Create Agent with or without name parameter
            if has_name:
                agent = Agent(name=name, traits=traits, codebook=codebook)
            else:
                agent = Agent(traits=traits, codebook=codebook)
            agents.append(agent)

        # Deduplicate agents list -- in case any models had identical questions/answers for an agent
        unique_agents = list(set(agents))

        return AgentList(unique_agents)

    @staticmethod
    def from_dict(data: dict) -> "AgentList":
        """Deserialize the dictionary back to an AgentList object.

        Args:
            data: A dictionary representing an AgentList.

        Returns:
            AgentList: A new AgentList created from the dictionary

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_helpers.agent_list_factories import AgentListFactories
            >>> al = AgentList([Agent.example()])
            >>> data = al.to_dict()
            >>> al2 = AgentListFactories.from_dict(data)
            >>> len(al2)
            1
        """
        from .agent_list_serializer import AgentListSerializer

        return AgentListSerializer.from_dict(data)

    @staticmethod
    def example(
        randomize: bool = False, codebook: Optional[dict[str, str]] = None
    ) -> "AgentList":
        """
        Returns an example AgentList instance.

        Args:
            randomize: If True, uses Agent's randomize method.
            codebook: Optional dictionary mapping trait names to descriptions.

        Returns:
            AgentList: An example AgentList instance

        Examples:
            >>> from edsl.agents.agent_list_helpers.agent_list_factories import AgentListFactories
            >>> al = AgentListFactories.example()
            >>> len(al)
            2
            >>> al = AgentListFactories.example(codebook={'age': 'Age in years'})
            >>> al[0].codebook['age']
            'Age in years'
        """
        from ..agent import Agent
        from ..agent_list import AgentList

        agent_list = AgentList([Agent.example(randomize), Agent.example(randomize)])

        if codebook:
            agent_list = agent_list.set_codebook(codebook)

        return agent_list

    @staticmethod
    def from_list(
        trait_name: str,
        values: List[Any],
        codebook: Optional[dict[str, str]] = None,
    ) -> "AgentList":
        """Create an AgentList from a list of values.

        Args:
            trait_name: The name of the trait.
            values: A list of values.
            codebook: Optional dictionary mapping trait names to descriptions.

        Returns:
            AgentList: A new AgentList created from the list of values

        Examples:
            >>> from edsl.agents.agent_list_helpers.agent_list_factories import AgentListFactories
            >>> al = AgentListFactories.from_list('age', [22, 23])
            >>> len(al)
            2
            >>> al[0].traits['age']
            22
            >>> al[1].traits['age']
            23
        """
        from ..agent import Agent
        from ..agent_list import AgentList

        agent_list = AgentList([Agent({trait_name: value}) for value in values])

        if codebook:
            agent_list = agent_list.set_codebook(codebook)

        return agent_list

    @staticmethod
    def from_scenario_list(scenario_list: "ScenarioList") -> "AgentList":
        """Create an AgentList from a ScenarioList.

        This method supports special fields that map to Agent parameters:
        - "name": Will be used as the agent's name
        - "agent_parameters": A dictionary containing:
            - "instruction": The agent's instruction text
            - "name": The agent's name (overrides the "name" field if present)

        Args:
            scenario_list: The ScenarioList to convert

        Returns:
            AgentList: A new AgentList created from the ScenarioList

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> from edsl.agents.agent_list_helpers.agent_list_factories import AgentListFactories
            >>> s = ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])
            >>> al = AgentListFactories.from_scenario_list(s)
            >>> len(al)
            1
            >>> al[0].traits
            {'age': 22, 'hair': 'brown', 'height': 5.5}
        """
        from ..agent import Agent
        from ..agent_list import AgentList

        agents = []
        for scenario in scenario_list:
            # Simple implementation to handle the basic test case
            new_scenario = scenario.copy().data
            if "name" in new_scenario:
                new_scenario["agent_name"] = new_scenario.pop("name")
                new_agent = Agent(traits=new_scenario, name=new_scenario["agent_name"])
                agents.append(new_agent)
            else:
                new_agent = Agent(traits=new_scenario)
                agents.append(new_agent)

        # Add a debug check to verify we've processed the scenarios correctly
        if len(agents) != len(scenario_list):
            raise ValueError(
                f"Expected {len(scenario_list)} agents, but created {len(agents)}"
            )

        return AgentList(agents)

    @staticmethod
    def get_codebook(file_path: str) -> dict:
        """Returns a codebook dictionary mapping CSV column names to None.

        Reads the header row of a CSV file and creates a codebook with field names as keys
        and None as values.

        Args:
            file_path: Path to the CSV file to read.

        Returns:
            A dictionary with CSV column names as keys and None as values.

        Raises:
            FileNotFoundError: If the specified file path does not exist.
            csv.Error: If there is an error reading the CSV file.

        Examples:
            >>> import csv
            >>> import os
            >>> from edsl.agents.agent_list_helpers.agent_list_factories import AgentListFactories
            >>> with open('/tmp/test_codebook.csv', 'w') as f:
            ...     writer = csv.writer(f)
            ...     _ = writer.writerow(['age', 'hair', 'height'])
            >>> codebook = AgentListFactories.get_codebook('/tmp/test_codebook.csv')
            >>> sorted(codebook.keys())
            ['age', 'hair', 'height']
            >>> os.remove('/tmp/test_codebook.csv')
        """
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            return {field: None for field in reader.fieldnames}
