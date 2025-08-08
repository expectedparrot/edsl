"""ResultsGrouper module for handling grouping and organizing operations of Results objects.

This module contains the ResultsGrouper class which provides various ways to group
and organize Results data for analysis, including grouping by agents, questions,
and arbitrary column values.
"""

from typing import TYPE_CHECKING, Optional, List
from collections import defaultdict

if TYPE_CHECKING:
    from ..results import Results, Result

from .exceptions import ResultsError


class ResultsGrouper:
    """Handles all grouping and organizing operations for Results objects.
    
    This class provides methods to group and organize Results data in various ways
    for analysis, including grouping by agents, questions, or arbitrary column values.
    """

    def __init__(self, results: "Results"):
        """Initialize the ResultsGrouper with a reference to the Results object.
        
        Args:
            results: The Results object to provide grouping operations for
        """
        self._results = results

    def agent_answers_by_question(self, agent_key_fields: Optional[List[str]] = None, separator: str = ",") -> dict:
        """Returns a dictionary of agent answers.
        
        The keys are the agent names and the values are the answers.
        
        Args:
            agent_key_fields: Optional list of agent fields to use as keys. If None, uses agent_name.
            separator: Separator to use when joining multiple agent key fields.
            
        Returns:
            dict: Dictionary with question names as keys, each containing a dict of agent->answer mappings.
        
        Examples:
            Access through Results instance:
                result = Results.example().agent_answers_by_question()
                sorted(result['how_feeling'].values())
                # ['Great', 'OK', 'OK', 'Terrible']
                sorted(result['how_feeling_yesterday'].values()) 
                # ['Good', 'Great', 'OK', 'Terrible']
        """
        d = {}
        if agent_key_fields is None:
            agent_name_keys = self._results.select('agent.agent_name').to_list()
        else:
            agent_name_keys = [f"{separator}".join(x) for x in self._results.select(*agent_key_fields).to_list()]

        for question in self._results.survey.questions:
            question_name = question.question_name
            answers = self._results.select(question_name).to_list()
            d[question_name] = {k:v for k,v in zip(agent_name_keys, answers)}

        return d

    def bucket_by(self, *columns: str) -> dict[tuple, list["Result"]]:
        """Group Result objects into buckets keyed by the specified column values.

        Each key in the returned dictionary is a tuple containing the values of
        the requested columns (in the same order as supplied).  The associated
        value is a list of ``Result`` instances whose values match that key.

        Args:
            *columns: Names of the columns to group by.  Column identifiers
                follow the same rules used by :meth:`select` – they can be
                specified either as fully-qualified names (e.g. ``"agent.status"``)
                or by bare attribute name when unambiguous.

        Returns:
            dict[tuple, list[Result]]: Mapping from value tuples to lists of
            ``Result`` objects.

        Raises:
            ResultsError: If no columns are provided or an invalid column name is
                supplied.

        Examples:
            Access through Results instance:
                r = Results.example()
                buckets = r.bucket_by('how_feeling')
                list(buckets.keys())
                # [('OK',), ('Great',), ('Terrible',)]
                all(isinstance(v, list) for v in buckets.values())
                # True
        """
        if len(columns) == 0:
            raise ResultsError("You must provide at least one column to bucket_by().")

        # Build buckets using a dictionary that maps key tuples to lists of Result objects
        buckets: dict[tuple, list[Result]] = defaultdict(list)

        for result in self._results.data:
            key_values = []
            for col in columns:
                # Determine data_type and attribute key
                data_type, attr_key = self._results._parse_column(col)
                # Extract the value from the Result object
                value = result.get_value(data_type, attr_key)
                key_values.append(value)
            buckets[tuple(key_values)].append(result)

        return dict(buckets) 