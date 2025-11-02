"""Module for generating descriptions of scenario lists using natural language."""

from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


def describe_scenario_list_with_vibes(
    scenario_list: "ScenarioList",
    *,
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_sample_values: int = 5,
) -> Dict[str, str]:
    """Generate a title and description for a scenario list.

    This function uses an LLM to analyze an existing scenario list and generate
    a descriptive title and detailed description of what the scenario list represents.

    Args:
        scenario_list: The ScenarioList instance to describe
        model: OpenAI model to use for generation (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.7)
        max_sample_values: Maximum number of sample values to include per key (default: 5)

    Returns:
        dict: Dictionary with keys:
            - "proposed_title": A single sentence title for the scenario list
            - "description": A paragraph-length description of the scenario list
    """
    from .vibe_describer import VibeDescribe

    # Collect all unique keys across all scenarios
    all_keys = set()
    for scenario in scenario_list.data:
        all_keys.update(scenario.keys())

    # Sample values for each key
    sample_values = {}
    for key in all_keys:
        values = []
        seen = set()
        for scenario in scenario_list.data:
            if key in scenario:
                value = scenario[key]
                # Convert to string for comparison and storage
                value_str = str(value)
                if value_str not in seen:
                    values.append(value)
                    seen.add(value_str)
                    if len(values) >= max_sample_values:
                        break
        sample_values[key] = values

    # Prepare data for the describer
    scenario_data = {
        "keys": sorted(list(all_keys)),
        "sample_values": sample_values,
        "num_scenarios": len(scenario_list.data),
    }

    # Include codebook if present
    if scenario_list.codebook:
        scenario_data["codebook"] = scenario_list.codebook

    # Create the describer
    describer = VibeDescribe(model=model, temperature=temperature)

    # Generate description
    return describer.describe_scenario_list(scenario_data)
