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
        # Generate a unique ID for this table instance to avoid conflicts
        import uuid

        table_id = f"interactive-table-{uuid.uuid4().hex[:8]}"

        html_template = """
        <div>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-bs5/1.13.6/dataTables.bootstrap5.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-buttons-bs5/2.4.1/buttons.bootstrap5.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-responsive-bs5/2.4.1/responsive.bootstrap5.min.css" rel="stylesheet">
            <style>
                {css}
            </style>
            <div class="container" style="max-width: 100%; margin: 20px 0;">
                <table id="{table_id}" class="table table-striped" style="width:100%">
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
                (function() {{
                    // Wait for dependencies to load
                    function initTable() {{
                        if (typeof jQuery === 'undefined' || typeof jQuery.fn.DataTable === 'undefined') {{
                            setTimeout(initTable, 100);
                            return;
                        }}

                        // Check if table already initialized
                        if (jQuery.fn.DataTable.isDataTable('#{table_id}')) {{
                            jQuery('#{table_id}').DataTable().destroy();
                        }}

                        jQuery('#{table_id}').DataTable({{
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
                    }}

                    // Initialize immediately if DOM is ready, otherwise wait
                    if (document.readyState === 'loading') {{
                        document.addEventListener('DOMContentLoaded', initTable);
                    }} else {{
                        initTable();
                    }}
                }})();
            </script>
        </div>
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
            css=css, header_cells=header_cells, body_rows=body_rows, table_id=table_id
        )

    @classmethod
    def get_css(cls) -> str:
        """Load CSS content from the file next to this module"""
        css_path = Path(__file__).parent / "table_display.css"
        return css_path.read_text()


class PandasStyleRenderer(DataTablesRendererABC):
    """Pandas-based styled renderer implementation"""

    def render_html(self) -> str:
        # Handle empty data case
        if not self.table_data.data and not self.table_data.headers:
            return "<p>Empty table</p>"

        # Build HTML table manually for better compatibility
        html_parts = []

        # Add styles
        html_parts.append(
            """
        <style>
            .edsl-table {
                border-collapse: collapse;
                width: 100%;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                font-size: 12px;
            }
            .edsl-table th {
                background-color: rgba(127, 127, 127, 0.1);
                font-weight: 600;
                padding: 12px 8px;
                text-align: left;
                vertical-align: top;
                border: 1px solid rgba(127, 127, 127, 0.3);
                border-bottom: 2px solid rgba(127, 127, 127, 0.5);
                position: sticky;
                top: 0;
                z-index: 10;
                white-space: nowrap;
                min-width: fit-content;
            }
            .edsl-table td {
                padding: 8px;
                text-align: left;
                vertical-align: top;
                white-space: pre-wrap;
                max-width: 300px;
                word-wrap: break-word;
                border: 1px solid rgba(127, 127, 127, 0.3);
            }
            .edsl-table tbody tr:nth-child(odd) {
                background-color: rgba(127, 127, 127, 0.05);
            }
            .edsl-table tbody tr:hover {
                background-color: rgba(59, 130, 246, 0.15);
            }
        </style>
        """
        )

        # Start table
        html_parts.append(
            '<div style="max-height: 500px; overflow: auto; width: 100%;"><table class="edsl-table">'
        )

        # Add header
        html_parts.append("<thead><tr>")
        for header in self.table_data.headers:
            escaped_header = escape_and_colorize_html(header)
            html_parts.append(f"<th>{escaped_header}</th>")
        html_parts.append("</tr></thead>")

        # Add body
        html_parts.append("<tbody>")
        for row in self.table_data.data:
            html_parts.append("<tr>")
            for cell in row:
                escaped_cell = escape_and_colorize_html(cell).replace("$", "\\$")
                html_parts.append(f"<td>{escaped_cell}</td>")
            html_parts.append("</tr>")
        html_parts.append("</tbody>")

        # Close table
        html_parts.append("</table></div>")

        return "".join(html_parts)

    @classmethod
    def get_css(cls) -> str:
        return ""  # Pandas styling handles its own CSS


class TabulatorRenderer(DataTablesRendererABC):
    """Tabulator-based interactive table renderer implementation"""

    def render_html(self) -> str:
        # Generate a unique ID for this table instance
        import uuid
        import json

        unique_id = uuid.uuid4().hex[:8]
        table_id = f"tabulator-table-{unique_id}"
        js_id = f"tabulator_table_{unique_id}"  # JavaScript-safe ID (no hyphens)

        # Handle empty data
        if not self.table_data.data or not self.table_data.headers:
            return "<p>Empty table</p>"

        # Convert data to format Tabulator expects
        columns = [
            {"title": str(header), "field": f"col_{i}"}
            for i, header in enumerate(self.table_data.headers)
        ]

        # Build data rows as dictionaries
        data_rows = []
        for row in self.table_data.data:
            row_dict = {
                f"col_{i}": str(cell) if cell is not None else ""
                for i, cell in enumerate(row)
            }
            data_rows.append(row_dict)

        html_template = """
        <div>
            <link href="https://unpkg.com/tabulator-tables@6.2.1/dist/css/tabulator_bootstrap5.min.css" rel="stylesheet">
            <style>
                .layout-toggle-{table_id} {{
                    display: flex;
                    justify-content: flex-end;
                    align-items: center;
                    gap: 20px;
                    margin-bottom: 5px;
                    font-size: 11px;
                    color: #666;
                }}
                .toggle-switch-{table_id} {{
                    position: relative;
                    display: inline-flex;
                    align-items: center;
                    gap: 8px;
                }}
                .toggle-switch-{table_id} input {{
                    opacity: 0;
                    width: 0;
                    height: 0;
                }}
                .toggle-slider-{table_id} {{
                    position: relative;
                    display: inline-block;
                    width: 36px;
                    height: 20px;
                    background-color: #ccc;
                    border-radius: 20px;
                    cursor: pointer;
                    transition: background-color 0.3s;
                }}
                .toggle-slider-{table_id}:before {{
                    content: "";
                    position: absolute;
                    height: 14px;
                    width: 14px;
                    left: 3px;
                    bottom: 3px;
                    background-color: white;
                    border-radius: 50%;
                    transition: transform 0.3s;
                }}
                .toggle-switch-{table_id} input:checked + .toggle-slider-{table_id} {{
                    background-color: #007bff;
                }}
                .toggle-switch-{table_id} input:checked + .toggle-slider-{table_id}:before {{
                    transform: translateX(16px);
                }}
                .expandable-cell-{table_id} {{
                    cursor: pointer;
                    user-select: none;
                }}
                .expandable-cell-{table_id}:hover {{
                    background-color: rgba(0, 123, 255, 0.1);
                }}
            </style>
            <div class="layout-toggle-{table_id}">
                <label class="toggle-switch-{table_id}">
                    <span style="order: -1;">Collapse</span>
                    <input type="checkbox" id="toggle-layout-{table_id}" checked onchange="window.setLayout_{js_id}(this.checked)">
                    <span class="toggle-slider-{table_id}"></span>
                    <span>Scroll</span>
                </label>
                <label class="toggle-switch-{table_id}">
                    <span style="order: -1;">Truncate</span>
                    <input type="checkbox" id="toggle-text-{table_id}" onchange="window.setTextMode_{js_id}(this.checked)">
                    <span class="toggle-slider-{table_id}"></span>
                    <span>Wrap</span>
                </label>
            </div>
            <div id="{table_id}"></div>
            <script src="https://unpkg.com/tabulator-tables@6.2.1/dist/js/tabulator.min.js"></script>
            <script>
                (function() {{
                    let table_{js_id};
                    let isScrollMode_{js_id} = true;
                    let isWrapMode_{js_id} = false;
                    const baseColumns_{js_id} = {columns_json};
                    const originalData_{js_id} = {data_json};

                    // Store expanded state for each cell (row_index, col_index)
                    const expandedCells_{js_id} = new Set();

                    function createColumns(wrapMode) {{
                        if (wrapMode) {{
                            // Wrap mode: use variableHeight for all columns
                            return baseColumns_{js_id}.map(col => ({{
                                ...col,
                                variableHeight: true,
                                formatter: "textarea"
                            }}));
                        }} else {{
                            // Truncate mode: custom formatter with click-to-expand
                            return baseColumns_{js_id}.map((col, colIndex) => ({{
                                ...col,
                                formatter: function(cell) {{
                                    const value = cell.getValue();
                                    if (!value) return '';

                                    const rowIndex = cell.getRow().getPosition();
                                    const cellKey = rowIndex + '_' + colIndex;
                                    const isExpanded = expandedCells_{js_id}.has(cellKey);
                                    const maxLength = 100;

                                    if (value.length <= maxLength) {{
                                        return value;
                                    }}

                                    if (isExpanded) {{
                                        return '<div class="expandable-cell-{table_id}" data-cell="' + cellKey + '">' + value + '</div>';
                                    }} else {{
                                        return '<div class="expandable-cell-{table_id}" data-cell="' + cellKey + '">' +
                                               value.substring(0, maxLength) + '...</div>';
                                    }}
                                }},
                                cellClick: function(e, cell) {{
                                    if (!e.target.classList.contains('expandable-cell-{table_id}')) return;

                                    const cellKey = e.target.getAttribute('data-cell');
                                    if (expandedCells_{js_id}.has(cellKey)) {{
                                        expandedCells_{js_id}.delete(cellKey);
                                    }} else {{
                                        expandedCells_{js_id}.add(cellKey);
                                    }}

                                    // Redraw the specific row
                                    cell.getRow().reformat();
                                }}
                            }}));
                        }}
                    }}

                    function createTable(scrollMode, wrapMode) {{
                        if (table_{js_id}) {{
                            table_{js_id}.destroy();
                        }}

                        try {{
                            table_{js_id} = new Tabulator("#{table_id}", {{
                                data: originalData_{js_id},
                                columns: createColumns(wrapMode),
                                layout: "fitDataFill",
                                pagination: true,
                                paginationSize: 10,
                                paginationSizeSelector: [5, 10, 25, 50, 100],
                                movableColumns: true,
                                resizableColumns: true,
                                responsiveLayout: scrollMode ? false : "collapse",
                                height: "500px",
                            }});
                        }} catch(e) {{
                            console.error("Tabulator initialization error:", e);
                            document.getElementById("{table_id}").innerHTML = "<p style='color: red;'>Error initializing table: " + e.message + "</p>";
                        }}
                    }}

                    function initTable() {{
                        if (typeof Tabulator === 'undefined') {{
                            setTimeout(initTable, 100);
                            return;
                        }}
                        createTable(isScrollMode_{js_id}, isWrapMode_{js_id});
                    }}

                    window.setLayout_{js_id} = function(isScrollMode) {{
                        isScrollMode_{js_id} = isScrollMode;
                        createTable(isScrollMode, isWrapMode_{js_id});
                    }}

                    window.setTextMode_{js_id} = function(isWrapMode) {{
                        isWrapMode_{js_id} = isWrapMode;
                        // Clear expanded state when switching modes
                        expandedCells_{js_id}.clear();
                        createTable(isScrollMode_{js_id}, isWrapMode);
                    }}

                    if (document.readyState === 'loading') {{
                        document.addEventListener('DOMContentLoaded', initTable);
                    }} else {{
                        initTable();
                    }}
                }})();
            </script>
        </div>
        """

        return html_template.format(
            table_id=table_id,
            js_id=js_id,
            data_json=json.dumps(data_rows),
            columns_json=json.dumps(columns),
        )

    @classmethod
    def get_css(cls) -> str:
        return ""  # Tabulator handles its own CSS


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
