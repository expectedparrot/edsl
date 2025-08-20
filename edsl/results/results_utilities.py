"""ResultsUtilities module for handling utility and helper methods of Results objects.

This module contains the ResultsUtilities class which provides various utility
operations for Results objects, including summary statistics, cache management,
comparison operations, and other helper functions.
"""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ..results import Results
    from ..caching import Cache

from .exceptions import ResultsError
from ..utilities import dict_hash


class ResultsUtilities:
    """Handles all utility and helper methods for Results objects.

    This class provides various utility operations including summary statistics,
    cache management, comparison operations, and other helper functions.
    """

    def __init__(self, results: "Results"):
        """Initialize the ResultsUtilities with a reference to the Results object.

        Args:
            results: The Results object to provide utilities for
        """
        self._results = results

    def _summary(self) -> dict:
        """Return a dictionary containing summary statistics about the Results object.

        The summary includes:
        - Number of observations (results)
        - Number of unique agents
        - Number of unique models
        - Number of unique scenarios
        - Number of questions in the survey
        - Survey question names (truncated for readability)

        Returns:
            dict: A dictionary containing the summary statistics

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> summary = r._summary()
            >>> isinstance(summary, dict)
            True
            >>> all(key in summary for key in ['observations', 'agents', 'models', 'scenarios', 'questions', 'Survey question names'])
            True
            >>> summary['observations'] > 0
            True
            >>> summary['questions'] > 0
            True
        """
        import reprlib

        d = {
            "observations": len(self._results),
            "agents": len(set(self._results.agents)),
            "models": len(set(self._results.models)),
            "scenarios": len(set(self._results.scenarios)),
            "questions": len(self._results.survey),
            "Survey question names": reprlib.repr(self._results.survey.question_names),
        }
        return d

    def _cache_keys(self) -> List[str]:
        """Return a list of all cache keys from the results.

        This method collects all cache keys by iterating through each result in the data
        and extracting the values from the 'cache_keys' dictionary. These keys can be used
        to identify cached responses and manage the cache effectively.

        Returns:
            List[str]: A list of cache keys from all results.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> all([type(s) == str for s in r._cache_keys()])
            True
        """
        cache_keys = []
        for result in self._results:
            cache_keys.extend(list(result["cache_keys"].values()))
        return cache_keys

    def relevant_cache(self, cache: "Cache") -> "Cache":
        """Return a subset of the cache containing only relevant keys.

        Args:
            cache: The Cache object to subset

        Returns:
            Cache: A new Cache object containing only relevant entries
        """
        cache_keys = self._cache_keys()
        return cache.subset(cache_keys)

    def compare(self, other_results: "Results") -> dict:
        """Compare two Results objects and return the differences.

        Args:
            other_results: Another Results object to compare with

        Returns:
            dict: Dictionary containing differences between the two Results objects
        """
        hashes_0 = [hash(result) for result in self._results]
        hashes_1 = [hash(result) for result in other_results]

        in_self_but_not_other = set(hashes_0).difference(set(hashes_1))
        in_other_but_not_self = set(hashes_1).difference(set(hashes_0))

        indicies_self = [hashes_0.index(h) for h in in_self_but_not_other]
        indices_other = [hashes_1.index(h) for h in in_other_but_not_self]
        return {
            "a_not_b": [self._results[i] for i in indicies_self],
            "b_not_a": [other_results[i] for i in indices_other],
        }

    def __hash__(self) -> int:
        """Generate hash for the Results object.

        Returns:
            int: Hash value for the Results object
        """
        return dict_hash(
            self._results.to_dict(
                sort=True,
                add_edsl_version=False,
                include_cache=False,
                include_cache_info=False,
            )
        )

    def __eq__(self, other) -> bool:
        """Check equality between Results objects.

        Args:
            other: Another object to compare with

        Returns:
            bool: True if objects are equal, False otherwise
        """
        return hash(self._results) == hash(other)

    def code(self):
        """Method for generating code representations.

        Raises:
            ResultsError: This method is not implemented for Results objects.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> try:
            ...     r.code()
            ... except ResultsError as e:
            ...     str(e).startswith("The code() method is not implemented")
            True
        """
        raise ResultsError("The code() method is not implemented for Results objects")

    def _parse_column(self, column: str) -> tuple[str, str]:
        """Parse a column name into a data type and key.

        Args:
            column: Column name to parse

        Returns:
            tuple[str, str]: Data type and key components
        """
        if "." in column:
            parts = column.split(".", 1)
            return (parts[0], parts[1])
        return self._results._cache_manager.key_to_data_type[column], column

    def get_answers(self, question_name: str) -> list:
        """Get the answers for a given question name.

        Args:
            question_name: The name of the question to fetch answers for.

        Returns:
            list: A list of answers, one from each result in the data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> answers = r.get_answers('how_feeling')
            >>> isinstance(answers, list)
            True
            >>> len(answers) == len(r)
            True
        """
        return self._results._cache_manager.fetch_list("answer", question_name)

    def _sample_legacy(self, n: int) -> "Results":
        """Return a random sample of the results using legacy algorithm.

        This method delegates to the ResultsSampler class and is kept for
        backward compatibility. Use sample() instead.

        Args:
            n: The number of samples to return.

        Returns:
            Results: A new Results object with sampled data.

        Examples:
            >>> from edsl.results import Results
            >>> r = Results.example()
            >>> len(r.sample(2))
            2
        """
        from .results_sampler import ResultsSampler

        sampler = ResultsSampler(self._results)
        return sampler.sample_legacy(n)
