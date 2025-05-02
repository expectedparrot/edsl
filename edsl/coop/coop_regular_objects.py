from typing import List

from .coop_objects import CoopObjects


class CoopRegularObjects(CoopObjects):
    """ScenarioList of regular Coop objects returned by the .list() method.

    This class provides specialized functionality for working with regular
    Coop objects like questions, surveys, scenarios, etc.
    """

    def fetch(self) -> List:
        """Fetch each object in the list and return them as EDSL objects.

        Returns:
            list: A list of EDSL objects (e.g., Survey, Question, etc.)

        Example:
            >>> objects = coop.list("survey")
            >>> surveys = objects.fetch()  # Returns list of Survey objects
        """
        from ..coop import Coop

        c = Coop()
        return [c.get(obj["uuid"]) for obj in self]
