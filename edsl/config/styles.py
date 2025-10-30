"""Rich text styling configuration for EDSL.

This module provides consistent styling for Rich formatted output across the package.
The styles are designed to work well in both light and dark themed terminals/notebooks.
"""

from typing import Dict


# Style mappings for Rich text formatting
# These styles are chosen to provide good contrast in both light and dark themes
RICH_STYLES: Dict[str, str] = {
    # Primary structural elements
    "primary": "bold blue",  # Main object names, headers
    "secondary": "bold green",  # Secondary headers, emphasized keys
    # Text content
    "default": "default",  # Regular text that adapts to theme
    "key": "green",  # Dictionary keys, column names
    "value": "default",  # Values, data content
    # Status and metadata
    "dim": "dim",  # Muted text, ellipsis indicators
    "highlight": "bold",  # Important information
    # Specific use cases
    "number": "default",  # Numeric values
    "string": "default",  # String values
    "bracket": "default",  # Brackets, parentheses
}


def get_style(name: str) -> str:
    """Get a style string by name.

    Args:
        name: The style name from RICH_STYLES

    Returns:
        The Rich style string

    Raises:
        KeyError: If the style name doesn't exist
    """
    return RICH_STYLES[name]


def get_style_safe(name: str, default: str = "default") -> str:
    """Get a style string by name with a fallback.

    Args:
        name: The style name from RICH_STYLES
        default: Default style to return if name not found

    Returns:
        The Rich style string or default if not found
    """
    return RICH_STYLES.get(name, default)
