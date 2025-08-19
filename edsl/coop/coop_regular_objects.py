from typing import List, Optional

from .coop_objects import CoopObjects


class CoopRegularObjects(CoopObjects):
    """ScenarioList of regular Coop objects returned by the .list() method.

    This class provides specialized functionality for working with regular
    Coop objects like questions, surveys, scenarios, etc.
    """

    def __init__(
        self,
        data: Optional[list] = None,
        codebook: Optional[dict[str, str]] = None,
        current_page: Optional[int] = None,
        total_pages: Optional[int] = None,
        page_size: Optional[int] = None,
        total_count: Optional[int] = None,
    ):
        super().__init__(data, codebook)
        self.current_page = current_page
        """The current page of the search results."""
        self.total_pages = total_pages
        """The total number of pages in the search results."""
        self.page_size = page_size
        """The number of objects per page."""
        self.total_count = total_count
        """The total number of objects that match the query (including those not in the current page)."""

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
        return [
            c.pull(obj["uuid"], expected_object_type=obj["object_type"]) for obj in self
        ]
