from __future__ import annotations

"""Container class for lists of ResultPairComparison objects."""

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .persona_viewers import FullTraitsTable, PersonaViewer


class ResultPairComparisonList:
    """A list of ResultPairComparison objects with additional analysis methods.

    This class wraps a list of ResultPairComparison objects and provides
    methods for analyzing and visualizing the personas/agents involved.
    """

    def __init__(self, comparisons: List, agent_name: str = None):
        """Initialize with a list of ResultPairComparison objects.

        Args:
            comparisons: List of ResultPairComparison objects
            agent_name: Optional name of the agent these comparisons belong to
        """
        self.comparisons = comparisons
        self.agent_name = agent_name

    def __len__(self):
        return len(self.comparisons)

    def __getitem__(self, index):
        return self.comparisons[index]

    def __iter__(self):
        return iter(self.comparisons)

    def show_full_traits(self) -> "FullTraitsTable":
        """Create an interactive HTML table showing all traits from agent traits.

        Returns:
            FullTraitsTable object that displays all trait information with navigation
        """
        from .persona_viewers import FullTraitsTable

        return FullTraitsTable(self.comparisons, self.agent_name)

    def show_personas(self) -> "PersonaViewer":
        """Create an interactive viewer showing just the persona trait from candidates.

        Returns:
            PersonaViewer object that displays persona text with navigation
        """
        from .persona_viewers import PersonaViewer

        return PersonaViewer(self.comparisons, self.agent_name)
