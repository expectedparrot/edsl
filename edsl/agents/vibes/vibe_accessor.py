"""
AgentList Vibe Accessor: Provides a namespace for vibe-based agent list methods.

This module provides the AgentListVibeAccessor class that enables the
`agent_list.vibe.filter()`, `agent_list.vibe.edit()`, and `agent_list.vibe.describe()`
interface pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent_list import AgentList
    from ...scenarios import Scenario
    from ...surveys import Survey


class AgentListVibeAccessor:
    """
    Accessor class for vibe-based agent list methods.

    This class provides a namespace for all vibe-related agent list methods,
    enabling the `agent_list.vibe.*` interface pattern.

    Examples
    --------
    >>> from edsl.agents import AgentList
    >>> agents = AgentList.example()  # doctest: +SKIP
    >>> agents.vibe.filter("Keep only people over 30")  # doctest: +SKIP
    >>> agents.vibe.edit("Make all agents 10 years older")  # doctest: +SKIP
    >>> agents.vibe.describe()  # doctest: +SKIP
    """

    def __init__(self, agent_list: "AgentList"):
        """
        Initialize the accessor with an agent list instance.

        Args:
            agent_list: The AgentList instance to operate on
        """
        self._agent_list = agent_list

    def filter(
        self,
        criteria: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        show_expression: bool = False,
    ) -> "AgentList":
        """Filter the agent list using natural language criteria.

        This method uses an LLM to generate a filter expression based on
        natural language criteria, then applies it using the agent list's filter method.

        Parameters:
            criteria: Natural language description of the filtering criteria.
                Examples:
                - "Keep only people over 30"
                - "Only engineers"
                - "Agents in Boston"
                - "Remove anyone under 25"
            model: OpenAI model to use for generating the filter (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.1 for consistent logic)
            show_expression: If True, prints the generated filter expression

        Returns:
            AgentList: A new AgentList containing only agents that match the criteria

        Examples:
            Basic filtering:

            >>> from edsl import Agent, AgentList
            >>> agents = AgentList([  # doctest: +SKIP
            ...     Agent(traits={"name": "Alice", "age": 30}),  # doctest: +SKIP
            ...     Agent(traits={"name": "Bob", "age": 25})  # doctest: +SKIP
            ... ])  # doctest: +SKIP
            >>> filtered = agents.vibe.filter("Keep only people over 25")  # doctest: +SKIP
            >>> len(filtered)  # doctest: +SKIP
            2

            With expression display:

            >>> filtered = agents.vibe.filter(  # doctest: +SKIP
            ...     "Only engineers",
            ...     show_expression=True
            ... )
            Generated filter expression: occupation == 'engineer'

            Complex criteria:

            >>> filtered = agents.vibe.filter("Keep people aged 25-35 from Boston")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - Uses LLM to generate Python expressions with operators: ==, !=, >, <, >=, <=, in, and, or, not
            - The generated expression is applied using the agent list's built-in filter() method
            - Supports complex boolean logic and range operations
            - Agent traits are accessed directly (e.g., age, occupation, city)
        """
        from edsl.dataset.vibes.vibe_filter import VibeFilter

        # Get trait names and sample data
        trait_names = self._agent_list.all_traits

        # Get a few sample agents' traits to help the LLM understand the data structure
        sample_dicts = []
        for agent in self._agent_list[:5]:  # First 5 agents
            sample_dicts.append(dict(agent.traits))

        # Create the filter generator
        filter_gen = VibeFilter(model=model, temperature=temperature)

        # Generate the filter expression
        filter_expr = filter_gen.create_filter(trait_names, sample_dicts, criteria)

        if show_expression:
            print(f"Generated filter expression: {filter_expr}")

        # Use the agent list's built-in filter method which returns AgentList
        return self._agent_list.filter(filter_expr)

    def edit(
        self,
        edit_instructions: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
    ) -> "AgentList":
        """Edit the agent list using natural language instructions.

        This method uses an LLM to modify an existing agent list based on natural language
        instructions. It can modify agent traits, add or remove traits, change trait values,
        filter agents, or make other modifications as requested.

        Args:
            edit_instructions: Natural language description of the edits to apply.
                Examples:
                - "Make all agents 10 years older"
                - "Add an 'education' trait to all agents"
                - "Remove agents under age 25"
                - "Translate all text traits to Spanish"
                - "Make the agents more diverse in background"
            model: OpenAI model to use for editing (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)

        Returns:
            AgentList: A new AgentList instance with the edited agents

        Examples:
            Basic usage:

            >>> from edsl import Agent, AgentList
            >>> agents = AgentList([  # doctest: +SKIP
            ...     Agent(traits={"name": "Alice", "age": 25, "job": "student"}),  # doctest: +SKIP
            ...     Agent(traits={"name": "Bob", "age": 30, "job": "teacher"})  # doctest: +SKIP
            ... ])  # doctest: +SKIP
            >>> edited = agents.vibe.edit("Make all agents 5 years older")  # doctest: +SKIP
            >>> edited[0].traits["age"]  # doctest: +SKIP
            30

            Adding traits:

            >>> edited = agents.vibe.edit("Add 'education_level' trait to all agents")  # doctest: +SKIP
            >>> "education_level" in edited[0].traits  # doctest: +SKIP
            True

            Complex edits:

            >>> edited = agents.vibe.edit(  # doctest: +SKIP
            ...     "Make the agents more diverse in terms of background and experience"
            ... )

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - Uses structured LLM output to ensure consistent agent definitions
            - Can add, modify, or remove agent traits
            - Can filter agents based on criteria
            - Maintains agent names when possible
            - Returns a completely new AgentList instance
        """
        from ..vibes import AgentVibeEdit
        from ..agent import Agent

        # Convert current agents to dict format
        current_agents = []
        for agent in self._agent_list.data:
            agent_dict = {"traits": dict(agent.traits)}
            if hasattr(agent, "name") and agent.name:
                agent_dict["name"] = agent.name
            current_agents.append(agent_dict)

        # Create the editor
        editor = AgentVibeEdit(model=model, temperature=temperature)

        # Edit the agent list
        edited_data = editor.edit_agent_list(current_agents, edit_instructions)

        # Convert each edited agent definition to an Agent object
        agents = []
        for agent_def in edited_data["agents"]:
            agent_traits = agent_def["traits"]
            agent_name = agent_def.get("name")

            # Create the agent with traits and optional name
            agent = Agent(traits=agent_traits, name=agent_name)
            agents.append(agent)

        return self._agent_list.__class__(agents)

    def describe(
        self,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_sample_values: int = 5,
    ) -> "Scenario":
        """Generate a title and description for the agent list.

        This method uses an LLM to analyze the agent list and generate
        a descriptive title and detailed description of what the agent list represents.

        Args:
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            max_sample_values: Maximum number of sample values to include per trait (default: 5)

        Returns:
            Scenario: Scenario with keys:
                - "proposed_title": A single sentence title for the agent list
                - "description": A paragraph-length description of the agent list

        Examples:
            Basic usage:

            >>> from edsl import Agent, AgentList
            >>> agents = AgentList([  # doctest: +SKIP
            ...     Agent(name="Alice", traits={"age": 30, "occupation": "engineer"}),  # doctest: +SKIP
            ...     Agent(name="Bob", traits={"age": 25, "occupation": "teacher"})  # doctest: +SKIP
            ... ])  # doctest: +SKIP
            >>> description = agents.vibe.describe()  # doctest: +SKIP
            >>> print(description["proposed_title"])  # doctest: +SKIP
            >>> print(description["description"])  # doctest: +SKIP

            Using a different model:

            >>> agents = AgentList.from_vibes("Software engineers")  # doctest: +SKIP
            >>> description = agents.vibe.describe(model="gpt-4o-mini")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - The title will be a single sentence that captures the agent list's essence
            - The description will be a paragraph explaining what the population represents
            - Analyzes all unique traits and samples values to understand the population theme
            - If agents have names, they will be included in the analysis
        """
        # Import here to avoid circular imports
        from .vibe_describer import AgentListVibeDescribe
        from ...scenarios import Scenario

        # Return empty scenario if no agents
        if not self._agent_list:
            return Scenario(
                {
                    "proposed_title": "Empty Agent List",
                    "description": "This agent list contains no agents.",
                }
            )

        # Collect all traits present across all agents
        all_traits = set()
        for agent in self._agent_list:
            all_traits.update(agent.traits.keys())
        traits = list(all_traits)

        # Sample values for each trait (up to max_sample_values)
        sample_values = {}
        for trait in traits:
            values = []
            for agent in self._agent_list:
                if trait in agent.traits and len(values) < max_sample_values:
                    value = agent.traits[trait]
                    if value not in values:  # Avoid duplicates
                        values.append(value)
            sample_values[trait] = values

        # Sample agent names if they exist
        agent_names = []
        for agent in self._agent_list:
            if (
                hasattr(agent, "name")
                and agent.name
                and len(agent_names) < max_sample_values
            ):
                if agent.name not in agent_names:
                    agent_names.append(agent.name)

        # Prepare data for the describer
        agent_data = {
            "traits": traits,
            "sample_values": sample_values,
            "num_agents": len(self._agent_list),
        }

        if agent_names:
            agent_data["agent_names"] = agent_names

        # Create describer and generate description
        describer = AgentListVibeDescribe(model=model, temperature=temperature)
        result = describer.describe_agent_list(agent_data)

        # Return as a Scenario object
        return Scenario(result)

    def design(
        self,
        survey: "Survey",
        *,
        model: str = "gpt-4o",
        temperature: float = 0.3,
        show_reasoning: bool = False,
    ) -> "AgentList":
        """Optimize agent list for survey-specific responses.

        This method analyzes a survey and optimizes agents to provide accurate,
        contextually appropriate responses. It:
        1. Analyzes survey questions to determine relevant traits per agent
        2. Filters agents to keep only relevant traits (simple filtering, no value modification)
        3. Generates optimized traits_presentation_template with selected traits
        4. Creates survey-specific instructions emphasizing accuracy

        Args:
            survey: The Survey object to optimize agents for
            model: OpenAI model for analysis (default: "gpt-4o")
            temperature: Temperature for LLM calls (default: 0.3 for consistent analysis)
            show_reasoning: If True, print trait selection reasoning

        Returns:
            AgentList: New agent list with optimized agents for the survey

        Examples:
            Basic usage:

            >>> from edsl import Agent, AgentList, Survey
            >>> agents = AgentList([  # doctest: +SKIP
            ...     Agent(traits={"age": 30, "occupation": "teacher", "city": "Boston"}),
            ...     Agent(traits={"age": 25, "occupation": "engineer", "city": "SF"})
            ... ])
            >>> survey = Survey([...])  # Workplace survey questions  # doctest: +SKIP
            >>> optimized = agents.vibe.design(survey)  # doctest: +SKIP

            With reasoning display:

            >>> optimized = agents.vibe.design(survey, show_reasoning=True)  # doctest: +SKIP
            === Survey Analysis ===
            Survey Type: Workplace satisfaction and experience survey

            Trait Relevance Reasoning:
              occupation: Highly relevant - survey asks about work experience
              age: Somewhat relevant - provides context for career stage
              city: Not relevant - survey doesn't ask about location

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - Uses LLM to analyze trait relevance and generate optimizations
            - Returns completely new agents (doesn't modify originals)
            - Focuses on accuracy over naturalness in responses
            - Handles edge cases gracefully (empty traits, LLM failures, etc.)
        """
        from .agent_list_survey_designer import AgentListSurveyDesigner

        # Create the designer
        designer = AgentListSurveyDesigner(model=model, temperature=temperature)

        # Design and return optimized agent list
        return designer.design_for_survey(
            agent_list=self._agent_list, survey=survey, show_reasoning=show_reasoning
        )
