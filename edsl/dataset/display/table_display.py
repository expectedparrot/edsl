from typing import (
    Protocol,
    Optional,
    TYPE_CHECKING,
    Sequence,
    Union,
    Literal,
)

if TYPE_CHECKING:
    from ..dataset import Dataset

from .table_data_class import TableData

from .table_renderers import DataTablesRenderer, PandasStyleRenderer, RichRenderer

Row = Sequence[Union[str, int, float, bool, None]]
TableFormat = Literal[
    "grid", "simple", "pipe", "orgtbl", "rst", "mediawiki", "html", "latex", "rich"
]


class TableRenderer(Protocol):
    """Table renderer protocol"""

    def render_html(self, table_data: TableData) -> str:
        pass


# Modified TableDisplay class
class TableDisplay:
    def __init__(
        self,
        headers: Sequence[str],
        data: Sequence[Row],
        tablefmt: Optional[TableFormat] = None,
        raw_data_set: "Dataset" = None,
        renderer_class: Optional[TableRenderer] = None,
    ):
        assert len(headers) == len(data[0])  # Check if headers and data are consistent

        self.headers = headers
        self.data = data
        self.tablefmt = tablefmt
        self.raw_data_set = raw_data_set

        self.renderer_class = renderer_class or PandasStyleRenderer

        # Handle printing parameters from raw_data_set
        if hasattr(raw_data_set, "print_parameters"):
            self.printing_parameters = (
                raw_data_set.print_parameters if raw_data_set.print_parameters else {}
            )
        else:
            self.printing_parameters = {}

    def _repr_html_(self) -> str:
        table_data = TableData(
            headers=self.headers,
            data=self.data,
            parameters=self.printing_parameters,
            raw_data_set=self.raw_data_set,
        )
        return self.renderer_class(table_data).render_html()

    def __repr__(self):
        # If rich format is requested, use RichRenderer
        if self.tablefmt == "rich":
            table_data = TableData(
                headers=self.headers,
                data=self.data,
                parameters=self.printing_parameters,
                raw_data_set=self.raw_data_set,
            )
            RichRenderer(table_data).render_terminal()
            return ""  # Return empty string since the table is already printed
        else:
            # Fall back to tabulate for other formats
            from tabulate import tabulate
            return tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)

    @classmethod
    def from_dictionary(
        cls,
        dictionary: dict,
        tablefmt: Optional[TableFormat] = None,
        renderer: Optional[TableRenderer] = None,
    ) -> "TableDisplay":
        headers = list(dictionary.keys())
        data = [list(dictionary.values())]
        return cls(headers, data, tablefmt, renderer_class=renderer)

    @classmethod
    def from_dictionary_wide(
        cls,
        dictionary: dict,
        tablefmt: Optional[TableFormat] = None,
        renderer: Optional[TableRenderer] = None,
    ) -> "TableDisplay":
        headers = ["key", "value"]
        data = [[k, v] for k, v in dictionary.items()]
        return cls(headers, data, tablefmt, renderer_class=renderer)

    @classmethod
    def from_dataset(
        cls,
        dataset: "Dataset",
        tablefmt: Optional[TableFormat] = None,
        renderer: Optional[TableRenderer] = None,
    ) -> "TableDisplay":
        headers, data = dataset._tabular()
        return cls(headers, data, tablefmt, dataset, renderer_class=renderer)

    def long(self) -> "TableDisplay":
        """Convert to long format"""
        new_header = ["row", "key", "value"]
        new_data = []
        for index, row in enumerate(self.data):
            new_data.extend([[index, k, v] for k, v in zip(self.headers, row)])
        return TableDisplay(
            new_header, new_data, self.tablefmt, renderer_class=self.renderer_class
        )


# Example usage:
if __name__ == "__main__":
    headers = ["Name", "Age", "City"]
    data = [["John", 30, "New York"], ["Jane", 25, "London"]]

    # Using default (Pandas) renderer
    table1 = TableDisplay(headers, data)

    # Using DataTables renderer
    table2 = TableDisplay(headers, data, renderer=DataTablesRenderer())
