"""
Base Widget Class for EDSL

Provides a base class for all EDSL-based widgets that handles common functionality
such as asset loading, naming conventions, and integration with the coop system.
"""

import anywidget
import os
import re
from typing import Tuple


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
        Compute the short name for the widget from the class name.

        Converts CamelCase class names to snake_case and removes 'Widget' suffix.

        Examples:
            ResultsViewerWidget -> results_viewer
            SurveyBuilderWidget -> survey_builder
            DataVisualizationWidget -> data_visualization

        Returns:
            str: The short name for the widget
        """
        class_name = cls.__name__

        # Remove 'Widget' suffix if present
        if class_name.endswith("Widget"):
            class_name = class_name[:-6]

        # Convert CamelCase to snake_case
        # Insert underscores before uppercase letters (except the first one)
        snake_case = re.sub("([a-z0-9])([A-Z])", r"\1_\2", class_name)
        return snake_case.lower()

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
            # print(f"No local widget assets found for {widget_name} at {js_file} and {css_file}")
            pass
        # Fall back to coop mechanism
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
        # Fetch assets only if they haven't been set on the class yet
        self.__class__.setup_widget_assets()

        super().__init__(**kwargs)
