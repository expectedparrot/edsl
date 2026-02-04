"""Module for generating descriptions of Results objects using natural language."""

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from ..results import Results


def describe_results_with_vibes(
    results: "Results",
    *,
    model: str = "gpt-4o",
    temperature: float = 0.7,
) -> Dict[str, str]:
    """Generate a title and description for a Results object.

    This function uses an LLM to analyze a Results object (including its Survey,
    AgentList, and ScenarioList) and generate a descriptive title and detailed
    description of what the research/study is about.

    Args:
        results: The Results instance to describe
        model: OpenAI model to use for generation (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)

    Returns:
        dict: Dictionary with keys:
            - "proposed_title": A single sentence title for the results
            - "description": A paragraph-length description of the results
    """
    from .vibe_describer import VibeDescribe

    # Extract survey questions
    questions = []
    if results.survey and hasattr(results.survey, "questions"):
        for question in results.survey.questions:
            q_dict = question.to_dict()
            # Extract the relevant fields for the describer
            question_data = {
                "question_name": q_dict.get("question_name"),
                "question_text": q_dict.get("question_text"),
                "question_type": q_dict.get("question_type"),
            }
            if "question_options" in q_dict and q_dict["question_options"]:
                question_data["question_options"] = q_dict["question_options"]
            questions.append(question_data)

    # Extract agent information
    agents_info = {}
    if len(results) > 0:
        # Get unique agents and their traits
        unique_agents = {}
        for result in results:
            agent = result.get("agent")
            if agent:
                agent_key = str(agent)  # Use string representation as key
                if agent_key not in unique_agents:
                    # Convert traits to a simple dict
                    traits = getattr(agent, "traits", {})
                    # Handle traits that might be objects - convert to dict
                    if hasattr(traits, "__dict__"):
                        traits_dict = traits.__dict__
                    elif hasattr(traits, "to_dict"):
                        traits_dict = traits.to_dict()
                    else:
                        traits_dict = dict(traits) if traits else {}

                    # Ensure traits values are JSON serializable
                    serializable_traits = {}
                    for k, v in traits_dict.items():
                        try:
                            import json

                            json.dumps(v)  # Test serialization
                            serializable_traits[k] = v
                        except (TypeError, ValueError):
                            serializable_traits[k] = str(v)

                    agent_data = {
                        "name": str(getattr(agent, "name", None)),
                        "traits": serializable_traits,
                        "instruction": (
                            str(getattr(agent, "instruction", None))
                            if getattr(agent, "instruction", None)
                            else None
                        ),
                    }
                    unique_agents[agent_key] = agent_data

        agents_info = {
            "num_agents": len(unique_agents),
            "agent_traits": (
                list(unique_agents.values())
                if len(unique_agents) <= 5
                else list(unique_agents.values())[:5]
            ),
        }

    # Extract scenario information
    scenarios_info = {}
    if len(results) > 0:
        # Get unique scenarios
        unique_scenarios = {}
        for result in results:
            scenario = result.get("scenario")
            if scenario:
                scenario_key = str(scenario)  # Use string representation as key
                if scenario_key not in unique_scenarios:
                    # Convert scenario to a simple dict
                    if hasattr(scenario, "to_dict"):
                        scenario_data = scenario.to_dict()
                    elif hasattr(scenario, "__dict__"):
                        scenario_data = scenario.__dict__
                    elif hasattr(scenario, "__iter__") and not isinstance(
                        scenario, str
                    ):
                        try:
                            scenario_data = dict(scenario)
                        except (TypeError, ValueError):
                            scenario_data = {"scenario_repr": str(scenario)}
                    else:
                        scenario_data = {"scenario_repr": str(scenario)}

                    # Filter out internal fields and ensure JSON serializable
                    filtered_data = {}
                    for k, v in scenario_data.items():
                        if not k.startswith("scenario_"):
                            # Ensure value is JSON serializable
                            try:
                                import json

                                json.dumps(v)  # Test serialization
                                filtered_data[k] = v
                            except (TypeError, ValueError):
                                filtered_data[k] = str(v)

                    unique_scenarios[scenario_key] = filtered_data

        scenarios_info = {
            "num_scenarios": len(unique_scenarios),
            "scenario_examples": (
                list(unique_scenarios.values())
                if len(unique_scenarios) <= 5
                else list(unique_scenarios.values())[:5]
            ),
        }

    # Extract basic results statistics
    results_stats = {
        "num_observations": len(results),
        "num_questions": len(questions),
        "question_names": [
            q["question_name"] for q in questions[:10]
        ],  # Limit to first 10
    }

    # Create the describer with additional results context
    describer = VibeDescribe(model=model, temperature=temperature)

    # Generate description for results (not just survey)
    return describer.describe_results(
        questions=questions,
        agents_info=agents_info,
        scenarios_info=scenarios_info,
        results_stats=results_stats,
    )
