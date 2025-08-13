from typing import Dict, List, Optional, TYPE_CHECKING
from .model_info_fetcher import ModelInfoFetcherABC

if TYPE_CHECKING:
    from .inference_service_registry import InferenceServiceRegistry


class SourcePreferenceHandler:
    """
    Handles the logic for iterating through source preferences to find a working model info fetcher.

    This class encapsulates the strategy for trying different sources in order of preference
    until a working source is found that can successfully fetch model information.

    Args:
        registry: The inference service registry instance
        source_preferences: Ordered list of preferred source names to try
        verbose: Enable verbose logging output
    """

    def __init__(
        self,
        registry: "InferenceServiceRegistry",
        source_preferences: List[str],
        verbose: bool = False,
    ):
        self.registry = registry
        self.source_preferences = source_preferences
        self.verbose = verbose
        self._used_source = None

    @property
    def used_source(self) -> Optional[str]:
        """Return the source that was successfully used to fetch data."""
        return self._used_source

    def fetch_model_info_data(self) -> Dict[str, List[str]]:
        """
        Iterate through source preferences to find and fetch model info data.

        Tries each source in the preference order until one succeeds in fetching
        non-empty model information.

        Returns:
            Dictionary mapping service names to lists of model names

        Raises:
            ValueError: If no source can successfully fetch model information
        """
        fetchers = ModelInfoFetcherABC.get_registered_fetchers()

        for source in self.source_preferences:
            if source not in fetchers:
                if self.verbose:
                    print(
                        f"[SOURCE_HANDLER] Fetcher '{source}' not registered. Available: {list(fetchers.keys())}"
                    )
                continue

            if self.verbose:
                print(f"[SOURCE_HANDLER] Trying source: {source}")

            try:
                model_info_fetcher = fetchers[source](self.registry)
                model_info_fetcher.fetch()

                if len(model_info_fetcher) > 0:
                    if self.verbose:
                        print(
                            f"[SOURCE_HANDLER] Successfully fetched data from source: {source}"
                        )
                    self._used_source = source
                    return dict(model_info_fetcher)
                else:
                    if self.verbose:
                        print(f"[SOURCE_HANDLER] Source '{source}' returned empty data")

            except Exception as e:
                if self.verbose:
                    print(
                        f"[SOURCE_HANDLER] Error fetching from source '{source}': {e}"
                    )
                continue

        # If we get here, no source worked
        available_sources = list(fetchers.keys())
        raise ValueError(
            f"Could not fetch model info from any source. "
            f"Tried: {self.source_preferences}. "
            f"Available fetchers: {available_sources}"
        )

    def reset_used_source(self) -> None:
        """Reset the used source to allow re-fetching."""
        self._used_source = None

    def add_source_preference(
        self, source: str, position: Optional[int] = None
    ) -> None:
        """
        Add a new source to the preference list.

        Args:
            source: The source name to add
            position: Optional position to insert at (default: end of list)
        """
        if source not in self.source_preferences:
            if position is None:
                self.source_preferences.append(source)
            else:
                self.source_preferences.insert(position, source)

    def remove_source_preference(self, source: str) -> bool:
        """
        Remove a source from the preference list.

        Args:
            source: The source name to remove

        Returns:
            True if the source was removed, False if it wasn't in the list
        """
        try:
            self.source_preferences.remove(source)
            return True
        except ValueError:
            return False

    def get_source_preferences(self) -> List[str]:
        """Get a copy of the current source preferences."""
        return self.source_preferences.copy()
