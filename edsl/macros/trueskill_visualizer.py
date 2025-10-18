#!/usr/bin/env python3
"""
TrueSkill Visualization Helper

This module provides utilities to convert TrueSkill rankings to JSON format
and generate HTML visualizations.
"""

import json
import webbrowser
import tempfile
import os
from pathlib import Path
from typing import List, Dict, Any, Union
from edsl import ScenarioList


def trueskill_to_json(
    scenario_list: ScenarioList,
    item_field: str = "item",
    rank_field: str = "rank",
    mu_field: str = "mu",
    sigma_field: str = "sigma",
    conservative_field: str = "conservative_rating",
) -> str:
    """
    Convert a TrueSkill-ranked ScenarioList to JSON format for visualization.

    Args:
        scenario_list: The ranked ScenarioList from TrueSkillApp
        item_field: Field name containing the item identifier
        rank_field: Field name containing the rank
        mu_field: Field name containing the skill estimate (mu)
        sigma_field: Field name containing the uncertainty (sigma)
        conservative_field: Field name containing the conservative rating

    Returns:
        JSON string containing the data in the format expected by the visualization
    """
    data = []
    for scenario in scenario_list:
        item_data = {
            "item": scenario.get(item_field, ""),
            "rank": scenario.get(rank_field, 0),
            "mu": scenario.get(mu_field, 0.0),
            "sigma": scenario.get(sigma_field, 0.0),
            "conservative_rating": scenario.get(conservative_field, 0.0),
        }
        data.append(item_data)

    return json.dumps(data, indent=2)


def create_visualization_html(
    data: Union[str, List[Dict[str, Any]]],
    title: str = "TrueSkill Rankings Visualization",
    output_file: str = None,
) -> str:
    """
    Create an HTML visualization with the provided TrueSkill data.

    Args:
        data: Either a JSON string or a list of dictionaries containing TrueSkill data
        title: Title for the visualization
        output_file: Optional output file path. If None, creates a temporary file.

    Returns:
        Path to the created HTML file
    """
    if isinstance(data, str):
        json_data = data
    else:
        json_data = json.dumps(data, indent=2)

    # Read the base HTML template
    current_dir = Path(__file__).parent
    template_path = current_dir / "trueskill_visualization.html"

    with open(template_path, "r") as f:
        html_content = f.read()

    # Replace the sample data with actual data
    html_content = html_content.replace(
        "const sampleData = [",
        f'const sampleData = {json_data.split("[", 1)[1] if json_data.startswith("[") else json_data}',
    )

    # Replace the title
    html_content = html_content.replace(
        "<title>TrueSkill Rankings Visualization</title>", f"<title>{title}</title>"
    ).replace("<h1>TrueSkill Rankings Visualization</h1>", f"<h1>{title}</h1>")

    # Determine output file
    if output_file is None:
        fd, output_file = tempfile.mkstemp(suffix=".html", prefix="trueskill_viz_")
        os.close(fd)

    # Write the HTML file
    with open(output_file, "w") as f:
        f.write(html_content)

    return output_file


def visualize_trueskill(
    scenario_list: ScenarioList,
    title: str = "TrueSkill Rankings Visualization",
    open_browser: bool = True,
    item_field: str = "item",
    rank_field: str = "rank",
    mu_field: str = "mu",
    sigma_field: str = "sigma",
    conservative_field: str = "conservative_rating",
) -> str:
    """
    Create and optionally open a TrueSkill visualization in the browser.

    Args:
        scenario_list: The ranked ScenarioList from TrueSkillApp
        title: Title for the visualization
        open_browser: Whether to automatically open the visualization in browser
        item_field: Field name containing the item identifier
        rank_field: Field name containing the rank
        mu_field: Field name containing the skill estimate (mu)
        sigma_field: Field name containing the uncertainty (sigma)
        conservative_field: Field name containing the conservative rating

    Returns:
        Path to the created HTML file
    """
    # Convert to JSON
    json_data = trueskill_to_json(
        scenario_list, item_field, rank_field, mu_field, sigma_field, conservative_field
    )

    # Create HTML visualization
    html_file = create_visualization_html(json_data, title)

    # Open in browser if requested
    if open_browser:
        webbrowser.open(f"file://{os.path.abspath(html_file)}")
        print(f"Visualization opened in browser: {html_file}")
    else:
        print(f"Visualization saved to: {html_file}")

    return html_file


if __name__ == "__main__":
    # Example usage with the food health ranking
    from food_health_true_skill import app, sl

    print("Running TrueSkill ranking...")
    ranked = app.output({"input_items": sl})
    print(f"Ranked {len(ranked)} items")

    print("Creating visualization...")
    html_file = visualize_trueskill(
        ranked, title="Food Health Rankings - TrueSkill", open_browser=True
    )

    print(f"Visualization created: {html_file}")
