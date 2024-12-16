# table_renderers.py
from abc import ABC, abstractmethod

from typing import Protocol, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from edsl.results.table_data_class import TableData

from edsl.results.table_renderers import DataTablesRenderer, PandasStyleRenderer


class TableRenderer(Protocol):
    """Table renderer protocol"""

    def render_html(self, table_data: TableData) -> str:
        pass


# Modified TableDisplay class
class TableDisplay:
    def __init__(
        self,
        headers: List[str],
        data: List[List[Any]],
        tablefmt: Optional[str] = None,
        raw_data_set: Any = None,
        renderer: Optional[TableRenderer] = None,
    ):
        self.headers = headers
        self.data = data
        self.tablefmt = tablefmt
        self.raw_data_set = raw_data_set

        self.renderer_class = renderer or PandasStyleRenderer

        # Handle printing parameters from raw_data_set
        if hasattr(raw_data_set, "print_parameters"):
            self.printing_parameters = (
                raw_data_set.print_parameters if raw_data_set.print_parameters else {}
            )
        else:
            self.printing_parameters = {}

    def _repr_html_(self):
        table_data = TableData(
            headers=self.headers,
            data=self.data,
            parameters=self.printing_parameters,
            raw_data_set=self.raw_data_set,
        )
        return self.renderer_class(table_data).render_html()

    def __repr__(self):
        from tabulate import tabulate

        return tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)

    @classmethod
    def from_dictionary(cls, dictionary, tablefmt=None, renderer=None):
        headers = list(dictionary.keys())
        data = [list(dictionary.values())]
        return cls(headers, data, tablefmt, renderer=renderer)

    @classmethod
    def from_dictionary_wide(cls, dictionary, tablefmt=None, renderer=None):
        headers = ["key", "value"]
        data = [[k, v] for k, v in dictionary.items()]
        return cls(headers, data, tablefmt, renderer=renderer)

    @classmethod
    def from_dataset(cls, dataset, tablefmt=None, renderer=None):
        headers, data = dataset._tabular()
        return cls(headers, data, tablefmt, dataset, renderer=renderer)

    def long(self):
        """Convert to long format"""
        new_header = ["row", "key", "value"]
        new_data = []
        for index, row in enumerate(self.data):
            new_data.extend([[index, k, v] for k, v in zip(self.headers, row)])
        return TableDisplay(new_header, new_data, self.tablefmt, renderer=self.renderer)


# Example usage:
if __name__ == "__main__":
    headers = ["Name", "Age", "City"]
    data = [["John", 30, "New York"], ["Jane", 25, "London"]]

    # Using default (Pandas) renderer
    table1 = TableDisplay(headers, data)

    # Using DataTables renderer
    table2 = TableDisplay(headers, data, renderer=DataTablesRenderer())
