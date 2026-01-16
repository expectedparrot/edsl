"""Strategy definitions for storytelling approaches."""

from typing import Dict


# Strategy instructions for different approaches
STRATEGIES: Dict[str, str] = {
    "baseline": "",  # No special instructions

    "level_k_0": """
STRATEGIC APPROACH:
Pick the most obvious, straightforward approach. Tell your story in the most natural way without overthinking how it might be perceived.
""",

    "level_k_1": """
STRATEGIC APPROACH:
Anticipate what the judge might expect. Think about what patterns or tells a skeptical evaluator might look for, and adjust your storytelling accordingly.
""",

    "level_k_2": """
STRATEGIC APPROACH:
Think about what the judge thinks you'll do. Consider that the judge is also trying to anticipate your strategy, so you may need to subvert their expectations.
""",

    "source_heavy": """
STRATEGIC APPROACH:
Emphasize credible sources throughout your story. Cite specific publications, researchers, institutions, or documents. Make your sources sound authoritative and verifiable.
""",

    "source_light": """
STRATEGIC APPROACH:
Minimize explicit source references. Let the story speak for itself through its internal coherence and detail rather than relying on external authority.
""",

    "detail_granular": """
STRATEGIC APPROACH:
Include highly specific details: exact dates, precise numbers, full names, specific locations, and technical terminology. Specificity often correlates with truth.
""",

    "detail_general": """
STRATEGIC APPROACH:
Keep details somewhat general. Use approximate timeframes, round numbers, and general descriptions. Sometimes too much specificity can seem rehearsed.
""",

    "style_logical": """
STRATEGIC APPROACH:
Use a logical, analytical tone. Structure your story with clear cause-and-effect relationships. Present information methodically and emphasize the reasoning behind claims.
""",

    "style_emotional": """
STRATEGIC APPROACH:
Use an emotional, narrative tone. Focus on the human element, the surprise factor, and the story arc. Make the judge feel the wonder or strangeness of the fact.
""",
}


def get_strategy_instructions(strategy: str) -> str:
    """Get the strategy instructions for a given strategy name.

    Args:
        strategy: Name of the strategy

    Returns:
        The strategy instruction text, or empty string if not found

    Raises:
        ValueError: If strategy is not recognized
    """
    if strategy not in STRATEGIES:
        available = ", ".join(STRATEGIES.keys())
        raise ValueError(f"Unknown strategy '{strategy}'. Available: {available}")

    return STRATEGIES[strategy]


def get_available_strategies() -> list[str]:
    """Get list of all available strategy names."""
    return list(STRATEGIES.keys())
