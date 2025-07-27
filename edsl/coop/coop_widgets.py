"""
Coop Widget Manager Singleton Module

This module implements a singleton pattern to cache widget ESM and CSS values,
ensuring they are only fetched once per session and reused for better performance.
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field


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
    
    _instance: Optional['CoopWidgetManager'] = None
    
    def __new__(cls) -> 'CoopWidgetManager':
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the singleton instance."""
        # Only initialize once
        if not hasattr(self, '_initialized'):
            self._cache: Dict[str, WidgetAssets] = {}
            self._scenarios_loaded = False
            self._initialized = True
    
    def get_widget_assets(self, widget_name: str) -> Tuple[str, str]:
        """
        Get ESM and CSS assets for a widget, loading scenarios and caching if not already done.
        
        Args:
            widget_name: Name of the widget (e.g., "results_viewer")
            
        Returns:
            Tuple of (esm_content, css_content)
            
        Raises:
            ValueError: If widget_name is not supported
            ImportError: If ScenarioList cannot be imported
            Exception: If loading scenarios fails
        """
        # Load scenarios if not already loaded
        if not self._scenarios_loaded:
            self._load_scenarios()
        
        # Check cache
        if widget_name not in self._cache:
            raise ValueError(
                f"Widget '{widget_name}' is not supported. "
                f"Available widgets: {list(self._cache.keys())}"
            )
        
        assets = self._cache[widget_name]
        return assets.esm, assets.css
    
    def _load_scenarios(self) -> None:
        """
        Load widget scenarios from ScenarioList and populate cache.
        
        Raises:
            ImportError: If ScenarioList cannot be imported
            Exception: If loading scenarios fails
        """
        # Check if already loaded
        if self._scenarios_loaded:
            return
        
        try:
            from ..scenarios import ScenarioList
            from ..config import CONFIG
        except ImportError:
            raise ImportError("Cannot import ScenarioList from scenarios module or CONFIG from config module")
        
        try:
            # Pull the scenario list with the UUID from config
            widget_uuid = CONFIG.EDSL_WIDGET_SCENARIO_UUID
            scenario_list = ScenarioList.pull(widget_uuid)
            # Populate cache from scenarios
            for scenario in scenario_list:
                widget_name = scenario["widget_name"]
                esm_content = scenario["esm"]
                css_content = scenario["css"]
                
                self._cache[widget_name] = WidgetAssets(esm=esm_content, css=css_content)
            
            self._scenarios_loaded = True
            
        except Exception as e:
            raise Exception(f"Failed to load widget scenarios: {str(e)}")
    
    def add_widget(self, widget_name: str, esm_content: str, css_content: str) -> None:
        """
        Add a new widget to the cache with ESM and CSS content.
        
        Args:
            widget_name: Name of the widget
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
            self._scenarios_loaded = False
        elif widget_name in self._cache:
            del self._cache[widget_name]
    
    def force_reload_scenarios(self) -> None:
        """
        Force reload scenarios from ScenarioList, bypassing cache.
        
        This method is useful for testing or when you want to refresh
        the widget data from the server.
        
        Raises:
            ImportError: If ScenarioList cannot be imported
            Exception: If loading scenarios fails
        """
        # Clear existing cache and reset loaded flag
        self._cache.clear()
        self._scenarios_loaded = False
        
        # Force load scenarios
        self._load_scenarios()
    
    def get_supported_widgets(self) -> list:
        """
        Get list of supported widget names.
        
        Returns:
            List of supported widget names
        """
        # Load scenarios if not already loaded
        if not self._scenarios_loaded:
            self._load_scenarios()
        
        return list(self._cache.keys())
    
    def is_cached(self, widget_name: str) -> bool:
        """
        Check if widget assets are already cached.
        
        Args:
            widget_name: Name of the widget
            
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
        # Load scenarios if not already loaded
        if not self._scenarios_loaded:
            self._load_scenarios()
        
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
        widget_name: Name of the widget
        
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


def force_reload_widget_scenarios() -> None:
    """
    Convenience function to force reload scenarios from ScenarioList.
    
    This is useful for testing or refreshing widget data from the server.
    
    Raises:
        ImportError: If ScenarioList cannot be imported
        Exception: If loading scenarios fails
    """
    viz = get_coop_widget_manager()
    viz.force_reload_scenarios() 