"""Handler for extracting scenario lists from HTML tables using LLM."""

from typing import TYPE_CHECKING, Dict, Any, Optional

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


def extract_from_html_with_vibes(
    html_content: str,
    *,
    model: str = "gpt-4o",
    temperature: float = 0.0,
    instructions: str = "",
    max_rows: Optional[int] = None,
) -> tuple["ScenarioList", Dict[str, Any]]:
    """Extract a ScenarioList from HTML containing a table.

    This function uses an LLM to analyze HTML content, identify and extract
    table data, and convert it into a structured ScenarioList.

    Args:
        html_content: HTML string containing one or more tables
        model: OpenAI model to use for extraction (default: "gpt-4o")
        temperature: Temperature for generation (default: 0.0 for consistent extraction)
        instructions: Additional instructions for extraction (e.g., "Extract only the first table",
            "Ignore the header row if it contains metadata")

    Returns:
        tuple: (ScenarioList, metadata_dict) where metadata_dict contains:
            - "headers": List of column headers
            - "notes": Extraction notes
            - "num_scenarios": Number of scenarios extracted

    Examples:
        >>> html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"  # doctest: +SKIP
        >>> sl, metadata = extract_from_html_with_vibes(html)  # doctest: +SKIP
        >>> len(sl)  # doctest: +SKIP
        1
        >>> sl[0]["name"]  # doctest: +SKIP
        'Alice'
        >>> metadata["headers"]  # doctest: +SKIP
        ['name', 'age']
    """
    from .vibe_extractor import VibeExtract
    from ..scenario import Scenario
    from ..scenario_list import ScenarioList

    # Create the extractor
    extractor = VibeExtract(model=model, temperature=temperature)

    # Extract table data
    result = extractor.extract_table_from_html(
        html_content=html_content,
        instructions=instructions,
        max_rows=max_rows,
    )

    # Create scenarios from extracted data
    scenarios = [Scenario(data) for data in result["scenarios"]]

    # Create scenario list
    scenario_list = ScenarioList(scenarios)

    # Prepare metadata
    metadata = {
        "headers": result["headers"],
        "notes": result["notes"],
        "num_scenarios": result["num_scenarios"],
    }

    return scenario_list, metadata
