"""
Coop Widget Manager Singleton Module

This module implements a singleton pattern to cache widget ESM and CSS values,
ensuring they are only fetched once per session and reused for better performance.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class WidgetAssets:
    """Container for widget ESM and CSS assets."""

    esm: str
    css: str


class CoopWidgetManager:
    """
    Singleton class for managing and caching widget visualization assets.

    This class ensures that ESM and CSS content for widgets is only fetched
    once per session and then cached for subsequent use, improving performance
    and reducing unnecessary network requests.
    """

    _instance: Optional["CoopWidgetManager"] = None

    def __new__(cls) -> "CoopWidgetManager":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the singleton instance."""
        # Only initialize once
        if not hasattr(self, "_initialized"):
            self._cache: Dict[str, WidgetAssets] = {}
            self._initialized = True

    def get_widget_assets(self, widget_name: str) -> Tuple[str, str]:
        """
        Get ESM and CSS assets for a widget, loading from coop if not already cached.

        Args:
            widget_name: Short name of the widget (e.g., "results_viewer")

        Returns:
            Tuple of (esm_content, css_content)

        Raises:
            ValueError: If widget_name is not supported
            ImportError: If Coop cannot be imported
            Exception: If loading widget fails
        """
        # Check cache first
        if widget_name in self._cache:
            assets = self._cache[widget_name]
            return assets.esm, assets.css

        # Load widget from coop
        try:
            from .coop import Coop

            coop = Coop()
        except ImportError:
            raise ImportError("Cannot import Coop from coop module")

        try:
            # Get widget data from coop
            widget_data = coop.get_widget(widget_name)

            # Extract ESM and CSS content
            esm_content = widget_data.get("esm_code", "")
            css_content = widget_data.get("css_code", "")

            # Cache the assets
            self._cache[widget_name] = WidgetAssets(esm=esm_content, css=css_content)

            return esm_content, css_content

        except Exception as e:
            raise Exception(f"Failed to load widget '{widget_name}': {str(e)}")

    def add_widget(self, widget_name: str, esm_content: str, css_content: str) -> None:
        """
        Add a new widget to the cache with ESM and CSS content.

        Args:
            widget_name: Short name of the widget
            esm_content: ESM JavaScript content
            css_content: CSS content
        """
        self._cache[widget_name] = WidgetAssets(esm=esm_content, css=css_content)

    def clear_cache(self, widget_name: Optional[str] = None) -> None:
        """
        Clear cached assets for a specific widget or all widgets.

        Args:
            widget_name: Widget to clear from cache. If None, clears all cached assets.
        """
        if widget_name is None:
            self._cache.clear()
        elif widget_name in self._cache:
            del self._cache[widget_name]

    def force_reload_widget(self, widget_name: str) -> None:
        """
        Force reload a specific widget from coop, bypassing cache.

        This method is useful for testing or when you want to refresh
        the widget data from the server.

        Args:
            widget_name: Short name of the widget to reload

        Raises:
            ImportError: If Coop cannot be imported
            Exception: If loading widget fails
        """
        # Remove from cache if present
        if widget_name in self._cache:
            del self._cache[widget_name]

        # Force load widget
        self.get_widget_assets(widget_name)

    def is_cached(self, widget_name: str) -> bool:
        """
        Check if widget assets are already cached.

        Args:
            widget_name: Short name of the widget

        Returns:
            True if assets are cached, False otherwise
        """
        return widget_name in self._cache

    def get_cache_stats(self) -> Dict[str, bool]:
        """
        Get cache statistics showing which widgets are cached.

        Returns:
            Dictionary mapping widget names to their cache status
        """

        return {
            widget: True  # All widgets in cache are by definition cached
            for widget in self._cache.keys()
        }


# Convenience function for easy access to the singleton
def get_coop_widget_manager() -> CoopWidgetManager:
    """
    Get the CoopWidgetManager singleton instance.

    Returns:
        CoopWidgetManager singleton instance
    """
    return CoopWidgetManager()


# Example usage functions
def get_widget_javascript(widget_name: str) -> Tuple[str, str]:
    """
    Convenience function to get widget JavaScript assets.

    Args:
        widget_name: Short name of the widget

    Returns:
        Tuple of (esm_content, css_content)
    """
    viz = get_coop_widget_manager()
    return viz.get_widget_assets(widget_name)


def clear_widget_cache(widget_name: Optional[str] = None) -> None:
    """
    Convenience function to clear widget cache.

    Args:
        widget_name: Widget to clear from cache. If None, clears all.
    """
    viz = get_coop_widget_manager()
    viz.clear_cache(widget_name)


def force_reload_widget(widget_name: str) -> None:
    """
    Convenience function to force reload a specific widget from coop.

    This is useful for testing or refreshing widget data from the server.

    Args:
        widget_name: Short name of the widget to reload

    Raises:
        ImportError: If Coop cannot be imported
        Exception: If loading widget fails
    """
    viz = get_coop_widget_manager()
    viz.force_reload_widget(widget_name)
