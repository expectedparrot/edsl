"""
Base Widget Class for EDSL

Provides a base class for all EDSL-based widgets that handles common functionality
such as asset loading, naming conventions, and integration with the coop system.
"""

import anywidget
import os
import re
from typing import Optional, Tuple


class EDSLBaseWidget(anywidget.AnyWidget):
    """
    Base class for all EDSL-based widgets.

    Provides common functionality for:
    - Computing widget short names from class names
    - Loading ESM and CSS assets from local files or coop system
    - Standardized asset management
    """

    @classmethod
    def get_widget_short_name(cls) -> str:
        """
        Get the short name for the widget from the mandatory class variable.

        All widgets inheriting from EDSLBaseWidget must define a widget_short_name
        class variable.

        Examples:
            class ResultsViewerWidget(EDSLBaseWidget):
                widget_short_name = "results_viewer"

            class SurveyBuilderWidget(EDSLBaseWidget):
                widget_short_name = "survey_builder"

        Returns:
            str: The short name for the widget

        Raises:
            AttributeError: If widget_short_name is not defined on the class
        """
        if not hasattr(cls, "widget_short_name"):
            raise AttributeError(
                f"Class {cls.__name__} must define a 'widget_short_name' class variable."
            )

        return cls.widget_short_name

    @staticmethod
    def is_widget_short_name_valid(short_name: str) -> tuple[bool, Optional[str]]:
        """
        Check if the widget short name is valid.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        if not short_name:
            return False, "Widget short name cannot be empty."

        if not short_name[0].isalpha():
            return False, "Widget short name must start with a lowercase letter."

        for char in short_name:
            if not (char.islower() or char.isdigit() or char == "_"):
                return (
                    False,
                    f"Widget short name contains invalid character '{char}'. Only lowercase letters, digits, and underscores are allowed.",
                )

        return True, None

    @classmethod
    def validate_widget_short_name(cls):
        """
        Validate that the widget_short_name is properly defined.

        This method can be called during class definition to ensure the
        widget_short_name is set correctly.

        Raises:
            AttributeError: If widget_short_name is not defined or is empty
        """
        if not hasattr(cls, "widget_short_name"):
            class_name = cls.__name__.replace("Widget", "")
            example_short_name = re.sub(
                "([a-z0-9])([A-Z])", r"\1_\2", class_name
            ).lower()
            raise AttributeError(
                f"Class {cls.__name__} must define a 'widget_short_name' class variable. "
                f"Example: widget_short_name = '{example_short_name}'"
            )

        if not isinstance(cls.widget_short_name, str):
            raise AttributeError(
                f"Class {cls.__name__}.widget_short_name must be a string, "
                f"got: {cls.widget_short_name}."
            )

        is_valid, error_message = cls.is_widget_short_name_valid(cls.widget_short_name)
        if not is_valid:
            raise AttributeError(
                f"Class {cls.__name__}.widget_short_name is invalid: {error_message}"
            )

    @classmethod
    def _get_widget_assets(cls) -> Tuple[str, str]:
        """
        Get ESM and CSS content for the widget.

        Tries to load from local files first, falls back to coop system.

        Returns:
            Tuple[str, str]: (esm_content, css_content)
        """
        widget_name = cls.get_widget_short_name()

        # Get the directory where this Python file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        src_dir = os.path.join(current_dir, "src")

        js_file = os.path.join(src_dir, "compiled", "esm_files", f"{widget_name}.js")
        css_file = os.path.join(src_dir, "compiled", "css_files", f"{widget_name}.css")

        # Check if local files exist
        if os.path.exists(js_file) and os.path.exists(css_file):
            try:
                with open(js_file, "r", encoding="utf-8") as f:
                    esm_content = f.read()
                with open(css_file, "r", encoding="utf-8") as f:
                    css_content = f.read()
                return esm_content, css_content
            except Exception as e:
                pass
        else:
            if os.path.exists(src_dir):
                raise FileNotFoundError(
                    f"Widget assets for {widget_name} not found at {js_file} and {css_file}."
                )
            else:
                pass
        # # Fall back to coop mechanism
        return cls._get_widget_assets_from_coop(widget_name)

    @classmethod
    def _get_widget_assets_from_coop(cls, widget_name: str) -> Tuple[str, str]:
        """
        Get widget assets from the coop system.

        Args:
            widget_name: The short name of the widget

        Returns:
            Tuple[str, str]: (esm_content, css_content)
        """
        try:
            from ..coop.coop import Coop

            coop = Coop()
            esm_content, css_content = coop._get_widget_javascript(widget_name)
            return esm_content, css_content
        except Exception as e:
            print(f"Error loading assets from coop: {e}")
            # Return empty strings as fallback
            return "", ""

    @classmethod
    def setup_widget_assets(cls):
        """
        Load widget assets if they haven't been loaded yet.

        This method ensures assets are loaded only once per class.
        """
        if not hasattr(cls, "_esm") or not hasattr(cls, "_css"):
            esm, css = cls._get_widget_assets()
            cls._esm = esm
            cls._css = css

    def __init__(self, **kwargs):
        """
        Initialize the widget and fetch assets on first instance creation.

        Assets are fetched lazily - only when the first instance of a widget class
        is created, not during import.
        """
        # Validate widget_short_name is properly defined
        self.__class__.validate_widget_short_name()

        # Fetch assets only if they haven't been set on the class yet
        self.__class__.setup_widget_assets()

        super().__init__(**kwargs)
