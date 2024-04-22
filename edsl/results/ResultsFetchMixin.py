"""Mixin for fetching data from results."""
from functools import partial
from itertools import chain


class ResultsFetchMixin:
    """Mixin for fetching data from results."""

    def _fetch_list(self, data_type, key) -> list:
        """
        Return a list of values from the data for a given data type and key.

        Uses the filtered data, not the original data.

        Example:
        >>> r = Results.create_example()
        >>> r._fetch_list('answer', 'how_feeling')
        ['Bad', 'Bad', 'Great', 'Great']
        """
        returned_list = []
        for row in self.data:
            returned_list.append(row.sub_dicts[data_type].get(key, None))

        return returned_list


if __name__ == "__main__":
    from edsl.results import Results

    r = Results.example()
