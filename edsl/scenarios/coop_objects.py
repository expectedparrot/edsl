from abc import ABC, abstractmethod
from typing import Optional, List
from .scenario_list import ScenarioList


class CoopObjects(ScenarioList, ABC):
    """Base class for Coop object collections.

    This abstract class extends ScenarioList to provide common functionality
    for working with collections of Coop objects.
    """

    def __init__(self, data: Optional[list] = None):
        super().__init__(data)

    @abstractmethod
    def fetch(self) -> List:
        """Fetch each object in the list and return them as EDSL objects.

        Returns:
            list: A list of instantiated EDSL objects

        Example:
            >>> objects = coop.list("some_type")
            >>> fetched_objects = objects.fetch()  # Returns list of appropriate objects
        """
        pass
