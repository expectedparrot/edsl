from tabulate import tabulate
from pathlib import Path

from edsl.results.CSSParameterizer import CSSParameterizer


class TableDisplay:
    max_height = 400
    min_height = 100

    def __init__(self, headers, data, tablefmt=None, raw_data_set=None):
        self.headers = headers
        self.data = data
        self.tablefmt = tablefmt
        self.raw_data_set = raw_data_set

        if hasattr(raw_data_set, "print_parameters"):
            if raw_data_set.print_parameters:
                self.printing_parameters = raw_data_set.print_parameters
            else:
                self.printing_parameters = {}
        else:
            self.printing_parameters = {}

    @classmethod
    def get_css(cls):
        """Load CSS content from the file next to this module"""
        css_path = Path(__file__).parent / "table_display.css"
        return css_path.read_text()

    @classmethod
    def from_dictionary(cls, dictionary, tablefmt=None):
        headers = list(dictionary.keys())
        data = [list(dictionary.values())]
        return TableDisplay(headers, data, tablefmt)

    @classmethod
    def from_dictionary_wide(cls, dictionary, tablefmt=None):
        # headers = list(dictionary.keys())
        # data = [list(dictionary.values())]
        headers = ["key", "value"]
        data = [[k, v] for k, v in dictionary.items()]
        return TableDisplay(headers, data, tablefmt)

    @classmethod
    def from_dataset(cls, dataset, tablefmt=None):
        headers, data = dataset._tabular()
        return TableDisplay(dataset.headers, dataset.data, tablefmt, dataset)

    def to_csv(self, filename: str):
        return self.raw_data_set.to_csv(filename)

    def write(self, filename: str):
        if self.tablefmt is None:
            table = tabulate(self.data, headers=self.headers, tablefmt="simple")
        else:
            table = tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)

        with open(filename, "w") as file:
            print("Writing table to", filename)
            file.write(table)

    def to_pandas(self):
        return self.raw_data_set.to_pandas()

    def to_list(self):
        return self.raw_data_set.to_list()

    def __repr__(self):

        from tabulate import tabulate

        from rich.table import Table
        from rich.console import Console

        table = Table(show_lines=True)
        for header in self.headers:
            table.add_column(str(header))

        for index in range(len(self.data)):
            table.add_row(*[str(e) for e in self.data[index]])

        console = Console(record=True)
        with console.capture() as capture:
            console.print(table)
        return capture.get()

        if self.tablefmt is None:
            return tabulate(self.data, headers=self.headers, tablefmt="simple")
        else:
            return tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)

    def print(self, format="rich"):
        if format == "rich":
            from rich.table import Table
            from rich.console import Console

            console = Console()

            table = Table(show_lines=True)

            for header in self.headers:
                table.add_column(str(header))

            for index in range(len(self.data)):
                table.add_row(*[str(e) for e in self.data[index]])

            console.print(table)

    def long(self):
        new_header = ["row", "key", "value"]
        new_data = []
        for index, row in enumerate(self.data):
            new_data.extend([[index, k, v] for k, v in zip(self.headers, row)])
        return TableDisplay(new_header, new_data)

    def _interactive_html(self):
        if self.tablefmt is not None:
            return (
                "<pre>"
                + tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)
                + "</pre>"
            )

        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <link href="https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-bs5/1.13.6/dataTables.bootstrap5.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-buttons-bs5/2.4.1/buttons.bootstrap5.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-responsive-bs5/2.4.1/responsive.bootstrap5.min.css" rel="stylesheet">
            <style>
                .container {{ 
                    padding: 20px;
                    max-width: 100%;
                }}
                .dataTables_wrapper {{ 
                    width: 100%;
                    overflow-x: auto;
                }}
                .dt-buttons {{
                    margin-bottom: 15px;
                }}
                {css}
            </style>
        </head>
        <body>
            <div class="container">
                <table id="interactive-table" class="table table-striped" style="width:100%">
                    <thead>
                        <tr>
                            {header_cells}
                        </tr>
                    </thead>
                    <tbody>
                        {body_rows}
                    </tbody>
                </table>
            </div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.0/jquery.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net/1.13.6/jquery.dataTables.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-bs5/1.13.6/dataTables.bootstrap5.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-buttons/2.4.1/js/dataTables.buttons.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-buttons-bs5/2.4.1/js/buttons.bootstrap5.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-buttons/2.4.1/js/buttons.colVis.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-responsive/2.4.1/js/dataTables.responsive.min.js"></script>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/datatables.net-responsive-bs5/2.4.1/js/responsive.bootstrap5.min.js"></script>
            <script>
                $(document).ready(function() {{
                    $('#interactive-table').DataTable({{
                        pageLength: 10,
                        lengthMenu: [[5, 10, 25, -1], [5, 10, 25, "All"]],
                        order: [[0, 'asc']],
                        scrollX: true,
                        responsive: {{
                            details: {{
                                type: 'column',
                                target: 'tr'
                            }}
                        }},
                        dom: 'Bfrtip',
                        buttons: [
                            {{
                                extend: 'colvis',
                                text: 'Show/Hide Columns',
                                className: 'btn btn-secondary'
                            }}
                        ],
                        columnDefs: [
                            {{
                                // Make all columns toggleable
                                targets: '_all',
                                className: 'dt-head-nowrap'
                            }}
                        ]
                    }});
                }});
            </script>
        </body>
        </html>
        """

        # Generate header cells
        header_cells = "".join(f"<th>{header}</th>" for header in self.headers)

        # Generate body rows
        body_rows = ""
        for row in self.data:
            body_rows += "<tr>"
            body_rows += "".join(f"<td>{cell}</td>" for cell in row)
            body_rows += "</tr>"

        # Get parameters and apply CSS
        parameters = {}
        parameters.update(self.printing_parameters)
        rendered_css = CSSParameterizer(self.get_css()).apply_parameters(parameters)

        # Format the template
        return html_template.format(
            css=rendered_css, header_cells=header_cells, body_rows=body_rows
        )

    def _repr_html_(self):
        # return self._interactive_html()
        if self.tablefmt is not None:
            return (
                "<pre>"
                + tabulate(self.data, headers=self.headers, tablefmt=self.tablefmt)
                + "</pre>"
            )

        num_rows = len(self.data)
        height = min(
            num_rows * 30 + 50, self.max_height
        )  # Added extra space for header

        if height < self.min_height:
            height = self.min_height

        html_template = """
        <style>
            {css}
        </style>
        <div class="table-container">
            <div class="scroll-table-wrapper">
                {table}
            </div>
        </div>
        """

        html_content = tabulate(self.data, headers=self.headers, tablefmt="html")
        html_content = html_content.replace("<table>", '<table class="scroll-table">')

        height_string = f"{height}px"
        parameters = {"containerHeight": height_string, "headerColor": "blue"}
        parameters.update(self.printing_parameters)
        rendered_css = CSSParameterizer(self.get_css()).apply_parameters(parameters)

        return html_template.format(table=html_content, css=rendered_css)

    @classmethod
    def example(
        cls,
        headers=None,
        data=None,
        filename: str = "table_example.html",
        auto_open: bool = True,
    ):
        """
        Creates a standalone HTML file with an example table in an iframe and optionally opens it in a new tab.

        Args:
            cls: The class itself
            headers (list): List of column headers. If None, uses example headers
            data (list): List of data rows. If None, uses example data
            filename (str): The name of the HTML file to create. Defaults to "table_example.html"
            auto_open (bool): Whether to automatically open the file in the default web browser. Defaults to True

        Returns:
            str: The path to the created HTML file
        """
        import os
        import webbrowser

        # Use example data if none provided
        if headers is None:
            headers = ["Name", "Age", "City", "Occupation"]
        if data is None:
            data = [
                [
                    "John Doe",
                    30,
                    "New York",
                    """cls: The class itself
        headers (list): List of column headers. If None, uses example headers
        data (list): List of data rows. If None, uses example data
        filename (str): The name of the HTML file to create. Defaults to "table_example.html"
        auto_open (bool): Whether to automatically open the file in the default web browser. Defaults to True
        """,
                ],
                ["Jane Smith", 28, "San Francisco", "Designer"],
                ["Bob Johnson", 35, "Chicago", "Manager"],
                ["Alice Brown", 25, "Boston", "Developer"],
                ["Charlie Wilson", 40, "Seattle", "Architect"],
            ]

        # Create instance with the data
        instance = cls(headers=headers, data=data)

        # Get the table HTML content
        table_html = instance._repr_html_()

        # Calculate the appropriate iframe height
        num_rows = len(data)
        iframe_height = min(num_rows * 140 + 50, cls.max_height)
        print(f"Table height: {iframe_height}px")

        # Create the full HTML document
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Table Display Example</title>
            <style>
                body {{
                    margin: 0;
                    padding: 20px;
                    font-family: Arial, sans-serif;
                }}
                iframe {{
                    width: 100%;
                    height: {iframe_height}px;
                    border: none;
                    overflow: hidden;
                }}
            </style>
        </head>
        <body>
            <iframe srcdoc='{table_html}'></iframe>
        </body>
        </html>
        """

        # Write the HTML file
        abs_path = os.path.abspath(filename)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Open in browser if requested
        if auto_open:
            webbrowser.open("file://" + abs_path, new=2)

        return abs_path


if __name__ == "__main__":
    TableDisplay.example()
