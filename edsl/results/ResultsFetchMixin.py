"""Mixin for fetching data from results."""

from functools import partial
from itertools import chain


class ResultsFetchMixin:
    """Mixin for fetching data from results."""

    def _fetch_list(self, data_type: str, key: str) -> list:
        """
        Return a list of values from the data for a given data type and key.

        Uses the filtered data, not the original data.

        Example:

        >>> from edsl.results import Results
        >>> r = Results.example()
        >>> r._fetch_list('answer', 'how_feeling')
        ['OK', 'Great', 'Terrible', 'OK']
        """
        returned_list = []
        for row in self.data:
            returned_list.append(row.sub_dicts[data_type].get(key, None))

        return returned_list


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
