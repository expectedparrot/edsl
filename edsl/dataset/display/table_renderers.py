from abc import ABC, abstractmethod
from pathlib import Path
import html
import re
from .table_data_class import TableData


def escape_and_colorize_html(text: str, colorize: bool = True) -> str:
    """Escape HTML special characters, convert URLs to hyperlinks, and optionally colorize tag-like patterns.

    Args:
        text: The text to escape and colorize
        colorize: If True, add color styling to patterns that look like HTML tags

    Returns:
        HTML-safe string with URLs as hyperlinks and optional color styling for tags
    """
    # First, escape all HTML special characters
    escaped = html.escape(str(text))

    # Convert URLs to hyperlinks before colorizing
    # Pattern to match http://, https://, ftp://, and ftps:// URLs
    url_pattern = r'(https?://[^\s<>"]+|ftp://[^\s<>"]+)'

    def make_hyperlink(match):
        url = match.group(1)
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'

    # Replace URLs with hyperlinks
    with_links = re.sub(url_pattern, make_hyperlink, escaped)

    if not colorize:
        return with_links

    # Pattern to match escaped tag-like structures: &lt;...&gt;
    # This matches opening tags, closing tags, and self-closing tags
    tag_pattern = r"&lt;(/?)([^&\s]+)([^&]*)&gt;"

    def colorize_tag(match):
        slash = match.group(1)  # Captures "/" for closing tags or empty string
        tag_name = match.group(2)  # Tag name
        rest = match.group(3)  # Any attributes or content after tag name

        # Different colors for opening vs closing tags
        if slash:
            # Closing tags in a reddish color
            color = "#d73a49"  # GitHub-style red
        else:
            # Opening tags in a bluish color
            color = "#005cc5"  # GitHub-style blue

        return f'<span style="color: {color}; font-weight: 500;">&lt;{slash}{tag_name}{rest}&gt;</span>'

    # Replace all tag-like patterns with colored versions
    colorized = re.sub(tag_pattern, colorize_tag, with_links)

    return colorized


class DataTablesRendererABC(ABC):
    def __init__(self, table_data: TableData):
        self.table_data = table_data

    @abstractmethod
    def render_html(self) -> str:
        pass


class DataTablesRenderer(DataTablesRendererABC):
    """Interactive DataTables renderer implementation"""

    def render_html(self) -> str:
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-bs5/1.13.6/dataTables.bootstrap5.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-buttons-bs5/2.4.1/buttons.bootstrap5.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-responsive-bs5/2.4.1/responsive.bootstrap5.min.css" rel="stylesheet">
            <style>
                {css}
            </style>
        </head>
        <body>
            <div class="container">
                <table id="interactive-table" class="table table-striped" style="width:100%">
                    <thead>
                        <tr>{header_cells}</tr>
                    </thead>
                    <tbody>{body_rows}</tbody>
                </table>
            </div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.0/jquery.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net/1.13.6/jquery.dataTables.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-bs5/1.13.6/dataTables.bootstrap5.min.js"></script>
            <script>
                $(document).ready(function() {{
                    $('#interactive-table').DataTable({{
                        pageLength: 10,
                        lengthMenu: [[5, 10, 25, -1], [5, 10, 25, "All"]],
                        scrollX: true,
                        responsive: true,
                        dom: 'Bfrtip',
                        buttons: [
                            {{
                                extend: 'colvis',
                                text: 'Show/Hide Columns'
                            }}
                        ]
                    }});
                }});
            </script>
        </body>
        </html>
        """

        header_cells = "".join(
            f"<th style='vertical-align: top;'>{escape_and_colorize_html(header)}</th>"
            for header in self.table_data.headers
        )
        body_rows = ""
        for row in self.table_data.data:
            body_rows += "<tr>"
            body_rows += "".join(
                f"<td style='vertical-align: top;'>{escape_and_colorize_html(cell)}</td>"
                for cell in row
            )
            body_rows += "</tr>"

        parameters = self.table_data.parameters or {}
        css = self.get_css()
        if hasattr(self, "css_parameterizer"):
            css = self.css_parameterizer(css).apply_parameters(parameters)

        return html_template.format(
            css=css, header_cells=header_cells, body_rows=body_rows
        )

    @classmethod
    def get_css(cls) -> str:
        """Load CSS content from the file next to this module"""
        css_path = Path(__file__).parent / "table_display.css"
        return css_path.read_text()


class PandasStyleRenderer(DataTablesRendererABC):
    """Pandas-based styled renderer implementation"""

    def render_html(self) -> str:
        import pandas as pd

        from contextlib import redirect_stderr
        import io

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            if self.table_data.raw_data_set is not None and hasattr(
                self.table_data.raw_data_set, "to_pandas"
            ):
                df = self.table_data.raw_data_set.to_pandas()
            else:
                # Handle empty data case
                if not self.table_data.data and not self.table_data.headers:
                    return "<p>Empty table</p>"
                df = pd.DataFrame(self.table_data.data, columns=self.table_data.headers)

            # Escape HTML special characters, colorize tags, and escape dollar signs to prevent MathJax rendering
            df = df.map(
                lambda x: (
                    escape_and_colorize_html(x).replace("$", "\\$")
                    if isinstance(x, str)
                    else x
                )
            )

            styled_df = df.style.set_properties(
                **{
                    "text-align": "left",
                    "vertical-align": "top",  # Top-justify text in cells
                    "white-space": "pre-wrap",  # Allows text wrapping
                    "max-width": "300px",  # Maximum width before wrapping
                    "word-wrap": "break-word",  # Breaks words that exceed max-width
                }
            ).background_gradient()

            return f"""
            <div style="max-height: 500px; overflow-y: auto;">
                {styled_df.to_html()}
            </div>
            """

    @classmethod
    def get_css(cls) -> str:
        return ""  # Pandas styling handles its own CSS


class RichRenderer(DataTablesRendererABC):
    """Rich-based terminal renderer implementation"""

    # ------------------------------------------------------------------
    # HTML fallback (required by the ABC).  The Rich renderer is intended
    # primarily for terminal output, but we still provide a minimal HTML
    # representation so that RichRenderer can be used in any context.
    # ------------------------------------------------------------------
    def render_html(self) -> str:
        """
        This method is required by the ABC but is not the primary function
        for this renderer. The render_terminal method below is what's used.
        """
        # Provide a basic HTML fallback for HTML contexts
        html_output = "<table border='1'><thead><tr>"
        html_output += "".join(
            f"<th style='vertical-align: top;'>{escape_and_colorize_html(header)}</th>"
            for header in self.table_data.headers
        )
        html_output += "</tr></thead><tbody>"

        for row in self.table_data.data:
            html_output += "<tr>"
            html_output += "".join(
                f"<td style='vertical-align: top;'>{escape_and_colorize_html(cell)}</td>"
                for cell in row
            )
            html_output += "</tr>"
        html_output += "</tbody></table>"

        return html_output

    # ------------------------------------------------------------------
    # Rich terminal helpers
    # ------------------------------------------------------------------

    def _build_rich_table(self):
        """Return a :class:`rich.table.Table` instance for *self.table_data*."""
        from rich.table import Table

        # Enable horizontal lines between rows for better readability
        tbl = Table(show_header=True, header_style="bold", show_lines=True)

        # Column headers
        for header in self.table_data.headers:
            tbl.add_column(str(header))

        # Rows
        for row in self.table_data.data:
            str_row = ["" if cell is None else str(cell) for cell in row]
            tbl.add_row(*str_row)

        return tbl

    def render_terminal(self, *, console=None) -> None:
        """Print the table to *console* (defaults to a new Console)."""
        try:
            from rich.console import Console

            if console is None:
                console = Console()

            console.print(self._build_rich_table())

        except ImportError:
            # Fallback if Rich is not installed
            print("Rich package is not installed. Install with 'pip install rich'")
            from tabulate import tabulate

            print(
                tabulate(
                    self.table_data.data,
                    headers=self.table_data.headers,
                    tablefmt="grid",
                )
            )

    # ------------------------------------------------------------------
    # String representation helpers
    # ------------------------------------------------------------------

    def render_str(self, width: int = 120) -> str:
        """Return the Rich-formatted table as a plain string.

        This is primarily useful for non-interactive contexts where the Rich
        colour codes are still desirable (e.g. writing to a log file) or when
        :pymeth:`TableDisplay.__repr__` needs a value to return.

        In Jupyter notebooks, returns a minimal string since _repr_html_ handles display.
        """
        # In Jupyter notebook environments, return minimal string
        # since _repr_html_ will handle the actual display
        # Check specifically for Jupyter notebook (not just IPython terminal)
        try:
            ipy = get_ipython()
            if ipy is not None and "IPKernelApp" in ipy.config:
                # We're in a Jupyter notebook/kernel, not IPython terminal
                rows = len(self.table_data.data)
                cols = len(self.table_data.headers)
                return f"TableDisplay({rows} rows x {cols} columns)"
        except NameError:
            pass

        try:
            from rich.console import Console
            import io
            import sys

            # Detect if we're in a terminal or being piped
            is_terminal = sys.stdout.isatty()

            # Try to detect actual terminal width if we're connected to a terminal
            if is_terminal:
                try:
                    # Use the actual terminal width if available
                    import os

                    terminal_width = os.get_terminal_size().columns
                    # Use terminal width but with a reasonable minimum
                    width = max(terminal_width, 80)
                except (OSError, AttributeError):
                    # Fall back to provided width if terminal size detection fails
                    pass

            buffer = io.StringIO()
            capture_console = Console(
                file=buffer,
                force_terminal=is_terminal,  # Only force terminal mode if actually in terminal
                width=width,
                color_system=(
                    "truecolor" if is_terminal else None
                ),  # No color for non-terminal
                legacy_windows=False,
            )
            capture_console.print(self._build_rich_table())
            return buffer.getvalue()
        except ImportError:
            # Degrade gracefully if Rich isn't available.
            from tabulate import tabulate

            return tabulate(
                self.table_data.data,
                headers=self.table_data.headers,
                tablefmt="grid",
            )
