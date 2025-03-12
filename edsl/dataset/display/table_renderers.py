from abc import ABC, abstractmethod
from .table_data_class import TableData

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
            f"<th>{header}</th>" for header in self.table_data.headers
        )
        body_rows = ""
        for row in self.table_data.data:
            body_rows += "<tr>"
            body_rows += "".join(f"<td>{cell}</td>" for cell in row)
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
                df = pd.DataFrame(self.table_data.data, columns=self.table_data.headers)

            styled_df = df.style.set_properties(
                **{"text-align": "left"}
            ).background_gradient()

            return f"""
            <div style="max-height: 500px; overflow-y: auto;">
                {styled_df.to_html()}
            </div>
            """

    @classmethod
    def get_css(cls) -> str:
        return ""  # Pandas styling handles its own CSS
