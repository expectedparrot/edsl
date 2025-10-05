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
        tablefmt: Optional[TableFormat] = "rich",
        raw_data_set: "Dataset" = None,
        renderer_class: Optional[TableRenderer] = None,
    ):
        if data:
            assert len(headers) == len(
                data[0]
            )  # Check if headers and data are consistent

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
        """
        HTML representation for Jupyter/Colab notebooks.

        The primary path uses the configured `renderer_class` to build an HTML
        string.  Unfortunately, in shared or long-running notebook runtimes it
        is not uncommon for binary dependencies (NumPy, Pandas, etc.) to get
        into an incompatible state, raising import-time errors that would
        otherwise bubble up to the notebook and obscure the actual table
        output.  To make the developer experience smoother we catch *any*
        exception, log/annotate it, and fall back to a plain-text rendering via
        `tabulate`, wrapped in a <pre> block so at least a readable table is
        shown.
        """
        try:
            table_data = TableData(
                headers=self.headers,
                data=self.data,
                parameters=self.printing_parameters,
                raw_data_set=self.raw_data_set,
            )
            return self.renderer_class(table_data).render_html()
        except Exception as exc:  # pragma: no cover
            # --- graceful degradation -------------------------------------------------
            import traceback

            full_traceback = traceback.format_exc()

            try:
                from tabulate import tabulate

                plain = tabulate(
                    self.data,
                    headers=self.headers,
                    tablefmt=self.tablefmt or "simple",
                )
            except Exception:
                # Even `tabulate` failed – resort to the default __repr__.
                plain = (
                    super().__repr__()
                    if hasattr(super(), "__repr__")
                    else str(self.data)
                )

            # Escape HTML-sensitive chars so the browser renders plain text.
            import html

            safe_plain = html.escape(plain)
            return f"<pre>{safe_plain}\n\n[TableDisplay fallback – original error: {exc}]\n\nFull traceback:\n{html.escape(full_traceback)}</pre>"

    def __repr__(self):
        # If rich format is requested, use RichRenderer
        if self.tablefmt == "rich":
            table_data = TableData(
                headers=self.headers,
                data=self.data,
                parameters=self.printing_parameters,
                raw_data_set=self.raw_data_set,
            )

            renderer = RichRenderer(table_data)

            # Simply return the Rich-formatted string; a REPL or caller can
            # decide what to do with it (e.g. the interactive prompt shows the
            # repr automatically, while an explicit `print()` will emit it
            # once).  Avoid calling render_terminal() here to prevent double
            # printing when the caller also prints the returned value.

            return renderer.render_str()
        else:
            # Fall back to tabulate for other formats
            from tabulate import tabulate

            return tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)

    def to_string(self) -> str:
        """Return a string rendering of the table using the current format/renderer.

        This mirrors the logic used by __repr__: when tablefmt is 'rich' it uses the
        Rich renderer's string output; otherwise it renders via `tabulate` using the
        configured `tablefmt`.
        """
        return self.__repr__()

    def to_markdown(self) -> str:
        """Return the table as a Markdown string.

        Uses the 'pipe' table format (GitHub-flavored Markdown compatible).
        Falls back to a minimal manual renderer if 'tabulate' is unavailable.
        """
        try:
            from tabulate import tabulate

            return tabulate(self.data, headers=self.headers, tablefmt="pipe")
        except Exception:
            # Minimal fallback: construct a simple pipe table without alignment
            headers_line = "| " + " | ".join([str(h) for h in self.headers]) + " |"
            separator = "| " + " | ".join(["---" for _ in self.headers]) + " |"
            rows = [
                "| "
                + " | ".join([
                    "" if v is None else str(v)  # ensure printable
                    for v in row
                ])
                + " |"
                for row in self.data
            ]
            return "\n".join([headers_line, separator, *rows])

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

    def flip(self) -> "TableDisplay":
        """Flip the table by transposing columns and rows"""
        # Create new headers from the first column of data (or indices if no suitable column)
        new_headers = [str(i) for i in range(len(self.data))]

        # Transpose the data: each original column becomes a row
        new_data = []
        for i, header in enumerate(self.headers):
            new_row = [header] + [row[i] for row in self.data]
            new_data.append(new_row)

        # The new headers include the original column names as the first column
        new_headers = ["column"] + new_headers

        return TableDisplay(
            new_headers, new_data, self.tablefmt, renderer_class=self.renderer_class
        )


# Example usage:
if __name__ == "__main__":
    headers = ["Name", "Age", "City"]
    data = [["John", 30, "New York"], ["Jane", 25, "London"]]

    # Using default (Pandas) renderer
    table1 = TableDisplay(headers, data)

    # Using DataTables renderer
    table2 = TableDisplay(headers, data, renderer=DataTablesRenderer())
