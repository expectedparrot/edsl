"""Create AgentDelta objects from comparison analysis.

This module provides functionality to analyze differences between two agents' results
and generate an AgentDelta that can update Agent A to make its answers more similar
to Agent B's answers.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Dict, Any, List

if TYPE_CHECKING:
    from edsl import Results, Agent
    from edsl.agents import AgentDelta
    from .result_pair_comparison import ResultPairComparison


def create_agent_delta_from_comparison(
    results_comparison: "ResultPairComparison",
    agent: Optional["Agent"] = None,
    model: Optional[Any] = None,
    custom_analysis_prompt: Optional[str] = None,
    custom_delta_prompt: Optional[str] = None,
) -> tuple["AgentDelta", "Results"]:
    """Create an AgentDelta by analyzing differences between two agents' responses.

    This function performs a two-step analysis:
    1. Analyzes the differences in responses to understand patterns
    2. Generates specific trait updates that would make Agent A more like Agent B

    Args:
        results_comparison: ResultPairComparison object containing the comparison
        agent: Optional agent whose traits should be updated. If None, extracts
               the agent from result_A in the comparison.
        model: Optional EDSL Model to use for analysis. If None, uses default.
        custom_analysis_prompt: Optional custom prompt for the analysis step
        custom_delta_prompt: Optional custom prompt for the delta generation step

    Returns:
        Tuple of (AgentDelta, Results) where Results contains both the analysis
        and the suggested trait updates

    Examples:
        >>> from edsl import Agent, Results
        >>> from edsl.comparisons import ResultPairComparison, create_agent_delta_from_comparison
        >>> # rc = ResultPairComparison(result_a, result_b)
        >>> # Agent is automatically extracted from result_a
        >>> # delta, results = create_agent_delta_from_comparison(rc)
        >>> # updated_agent = result_a.agent.apply_delta(delta)

        >>> # Or provide agent explicitly
        >>> # delta, results = create_agent_delta_from_comparison(rc, agent=my_agent)
    """
    from edsl import QuestionFreeText, QuestionDict, Survey
    from edsl.agents import AgentDelta

    # Extract agent from result_A if not provided
    if agent is None:
        if hasattr(results_comparison.result_A, "agent"):
            agent = results_comparison.result_A.agent
        else:
            raise ValueError(
                "Could not extract agent from result_A. "
                "Please provide the agent parameter explicitly."
            )

    # Get the comparison digest
    digest = results_comparison.delta_digest(highlight_differences=True)

    # Extract agent traits to use as keys for the delta
    trait_keys = list(agent.traits.keys())
    if not trait_keys:
        raise ValueError("Agent has no traits to update")

    # Get trait types for better type hints
    trait_types = []
    trait_descriptions = []
    for key in trait_keys:
        value = agent.traits[key]
        # Infer type from current value
        if isinstance(value, bool):
            trait_types.append("bool")
        elif isinstance(value, int):
            trait_types.append("int")
        elif isinstance(value, float):
            trait_types.append("float")
        elif isinstance(value, list):
            trait_types.append("list")
        else:
            trait_types.append("str")

        # Get description from codebook if available
        if hasattr(agent, "codebook") and key in agent.codebook:
            trait_descriptions.append(agent.codebook[key])
        else:
            trait_descriptions.append(f"Updated value for {key}")

    # Create the analysis prompt
    if custom_analysis_prompt is None:
        analysis_prompt = f"""Below is a comparison between two agents' responses to a survey. 
Agent A and Agent B answered the same questions, and we want to understand what 
changes to Agent A's persona would make its answers more similar to Agent B's answers.

{digest}

Based on the differences highlighted above, please:
1. Identify the key patterns in how Agent A's answers differ from Agent B's answers
2. Suggest specific changes to Agent A's persona, background, or characteristics that would 
   make its responses more aligned with Agent B
3. Explain your reasoning for each suggested change

Please provide a structured analysis."""
    else:
        analysis_prompt = (
            custom_analysis_prompt.format(digest=digest)
            if "{digest}" in custom_analysis_prompt
            else custom_analysis_prompt + f"\n\n{digest}"
        )

    # Create the delta prompt
    if custom_delta_prompt is None:
        # Build trait context
        trait_context_lines = ["Current Agent A traits:"]
        for key, value in agent.traits.items():
            desc = agent.codebook.get(key, key) if hasattr(agent, "codebook") else key
            trait_context_lines.append(f"- {desc}: {value}")
        trait_context = "\n".join(trait_context_lines)

        delta_prompt = f"""Based on your analysis of the differences between Agent A and Agent B, 
please suggest specific updated values for Agent A's traits that would make its answers 
more similar to Agent B's answers.

{trait_context}

For each trait, provide the NEW value that would make Agent A more like Agent B.
You should update values to reflect the personality, background, or characteristics 
that would lead to responses more aligned with Agent B.

If a trait doesn't need to change, use the same value as the current value.
Provide specific, concrete values rather than vague suggestions."""
    else:
        delta_prompt = custom_delta_prompt

    # Create the questions
    q_analysis = QuestionFreeText(
        question_name="persona_analysis", question_text=analysis_prompt
    )

    q_delta = QuestionDict(
        question_name="trait_updates",
        question_text=delta_prompt,
        answer_keys=trait_keys,
        value_types=trait_types,
        value_descriptions=trait_descriptions,
    )

    # Run the survey
    survey = Survey(questions=[q_analysis, q_delta])
    if model is not None:
        results = survey.by(model).run()
    else:
        results = survey.run()

    # Extract the trait updates from the results
    trait_updates_dict = results.select("trait_updates").first()

    # Create the AgentDelta
    delta = AgentDelta(trait_updates_dict)

    return delta, results


def analyze_and_update_agent(
    results_comparison: "ResultPairComparison",
    agent: Optional["Agent"] = None,
    model: Optional[Any] = None,
    custom_analysis_prompt: Optional[str] = None,
    custom_delta_prompt: Optional[str] = None,
    apply_delta: bool = True,
) -> tuple["Agent", "AgentDelta", "Results"]:
    """Analyze differences and update an agent in one step.

    This is a convenience function that combines delta creation and application.
    The agent is automatically extracted from result_A if not provided.

    Args:
        results_comparison: ResultPairComparison object containing the comparison
        agent: Optional agent whose traits should be updated.
               If None, automatically extracted from result_A.
        model: Optional EDSL Model to use for analysis
        custom_analysis_prompt: Optional custom prompt for analysis
        custom_delta_prompt: Optional custom prompt for delta generation
        apply_delta: If True, applies the delta to create an updated agent.
                    If False, returns the original agent unchanged.

    Returns:
        Tuple of (updated_agent, delta, analysis_results)
        If apply_delta is False, updated_agent will be the same as the input agent.

    Examples:
        Auto-extract agent from result_A:

        >>> from edsl.comparisons import ResultPairComparison, analyze_and_update_agent
        >>> # rc = ResultPairComparison(result_a, result_b)
        >>> # updated_agent, delta, results = analyze_and_update_agent(rc)

        Provide agent explicitly:

        >>> from edsl import Agent
        >>> # agent_a = Agent(traits={'age': 30, 'occupation': 'teacher'})
        >>> # updated_agent, delta, results = analyze_and_update_agent(rc, agent=agent_a)
    """
    delta, results = create_agent_delta_from_comparison(
        results_comparison=results_comparison,
        agent=agent,
        model=model,
        custom_analysis_prompt=custom_analysis_prompt,
        custom_delta_prompt=custom_delta_prompt,
    )

    # Extract agent if not provided (for applying delta)
    if agent is None:
        agent = results_comparison.result_A.agent

    if apply_delta:
        updated_agent = agent.apply_delta(delta)
    else:
        updated_agent = agent

    return updated_agent, delta, results


def batch_create_agent_deltas(
    comparisons: List["ResultPairComparison"],
    agents: Optional[List[Optional["Agent"]]] = None,
    model: Optional[Any] = None,
) -> List[tuple["AgentDelta", "Results"]]:
    """Create AgentDeltas for multiple comparisons in batch.

    Agents are automatically extracted from each comparison's result_A if not provided.

    Args:
        comparisons: List of ResultPairComparison objects
        agents: Optional list of agents to update. If None, agents are extracted
                from each comparison's result_A. If provided, must match length.
        model: Optional EDSL Model to use for all analyses

    Returns:
        List of (delta, results) tuples, one for each comparison

    Raises:
        ValueError: If agents list is provided but length doesn't match comparisons

    Examples:
        Auto-extract agents from comparisons:

        >>> from edsl.comparisons import batch_create_agent_deltas
        >>> # comparisons = [rc1, rc2, rc3]
        >>> # deltas_and_results = batch_create_agent_deltas(comparisons)

        Provide explicit agents:

        >>> # agents = [agent1, agent2, agent3]
        >>> # deltas_and_results = batch_create_agent_deltas(comparisons, agents=agents)
    """
    if agents is not None and len(comparisons) != len(agents):
        raise ValueError(
            f"Number of comparisons ({len(comparisons)}) must match "
            f"number of agents ({len(agents)})"
        )

    results = []
    for i, comparison in enumerate(comparisons):
        agent = agents[i] if agents is not None else None
        delta, analysis_results = create_agent_delta_from_comparison(
            results_comparison=comparison,
            agent=agent,
            model=model,
        )
        results.append((delta, analysis_results))

    return results


def create_agent_list_deltas_from_comparisons(
    comparisons: Dict[str, "ResultPairComparison"],
    agents: Optional[Dict[str, "Agent"]] = None,
    model: Optional[Any] = None,
) -> tuple["AgentListDeltas", Dict[str, "Results"]]:
    """Create an AgentListDeltas from multiple named comparisons.

    This function takes dictionaries mapping agent names to their comparisons,
    then creates a single AgentListDeltas object that can be applied to an AgentList.
    Agents are automatically extracted from each comparison's result_A if not provided.

    Args:
        comparisons: Dict mapping agent names to ResultPairComparison objects
        agents: Optional dict mapping agent names to Agent objects. If None,
                agents are extracted from each comparison's result_A.
        model: Optional EDSL Model to use for all analyses

    Returns:
        Tuple of (AgentListDeltas, dict of Results by agent name)

    Raises:
        ValueError: If agents dict is provided but names don't match comparisons

    Examples:
        Auto-extract agents from comparisons:

        >>> from edsl.comparisons import create_agent_list_deltas_from_comparisons
        >>> # comparisons = {'alice': rc_alice, 'bob': rc_bob}
        >>> # list_deltas, all_results = create_agent_list_deltas_from_comparisons(comparisons)

        Provide explicit agents:

        >>> # agents = {'alice': agent_alice, 'bob': agent_bob}
        >>> # list_deltas, all_results = create_agent_list_deltas_from_comparisons(
        >>> #     comparisons, agents=agents
        >>> # )
    """
    from edsl.agents import AgentListDeltas

    comparison_names = set(comparisons.keys())

    # Validate matching names if agents provided
    if agents is not None:
        agent_names = set(agents.keys())
        if comparison_names != agent_names:
            missing_in_agents = comparison_names - agent_names
            missing_in_comparisons = agent_names - comparison_names
            error_parts = ["Agent names in comparisons and agents dict don't match."]
            if missing_in_agents:
                error_parts.append(f"Missing agents: {sorted(missing_in_agents)}")
            if missing_in_comparisons:
                error_parts.append(
                    f"Missing comparisons: {sorted(missing_in_comparisons)}"
                )
            raise ValueError(" ".join(error_parts))

    # Create deltas for each agent
    deltas_dict = {}
    results_dict = {}

    for agent_name in comparison_names:
        agent = agents.get(agent_name) if agents is not None else None
        delta, results = create_agent_delta_from_comparison(
            results_comparison=comparisons[agent_name],
            agent=agent,
            model=model,
        )
        deltas_dict[agent_name] = delta
        results_dict[agent_name] = results

    # Create AgentListDeltas
    list_deltas = AgentListDeltas(deltas_dict)

    return list_deltas, results_dict


__all__ = [
    "create_agent_delta_from_comparison",
    "analyze_and_update_agent",
    "batch_create_agent_deltas",
    "create_agent_list_deltas_from_comparisons",
]
