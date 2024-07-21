"""A module for displaying data in various formats."""

from html import escape


def create_image(console, image_filename):
    """Create an image from the console output."""
    font_size = 15
    from PIL import Image, ImageDraw, ImageFont

    text = console.export_text()  # Get the console output as text.

    # Create an image from the text
    font_size = 15
    font = ImageFont.load_default()  # Use the default font to avoid file path issues.
    # text_width, text_height = ImageDraw.Draw(
    #    Image.new("RGB", (100, 100))
    # ).multiline_textsize(text, font=font)
    text_width, text_height = get_multiline_textsize(text, font)
    image = Image.new(
        "RGB", (text_width + 20, text_height + 20), color=(255, 255, 255)
    )  # Add some padding
    d = ImageDraw.Draw(image)

    # Draw text to image
    d.multiline_text((10, 10), text, font=font, fill=(0, 0, 0))
    # Save the image
    image.save(image_filename)


def display_table(console, table, filename):
    # from rich.console import Console
    # from rich.table import Table
    """Display the table using the rich library and save it to a file if a filename is provided."""
    if filename is not None:
        with open(filename, "w") as f:
            with console.capture() as capture:
                console.print(table)
            f.write(capture.get())
        create_image(console, filename + ".png")
    else:
        console.print(table)


def gen_html_sandwich(html_inner, interactive=False):
    """Wrap the inner HTML content in a header and footer to make a complete HTML document."""
    return html_inner
    if interactive:
        html_header = """
            <html>
            <head>
            <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"></script>
            <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.css" />
            <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.js"></script>
            <style>
                table {
                    font-family: Arial, sans-serif;
                    border-collapse: collapse;
                    width: 100%;
                }
                
                td, th {
                    border: 1px solid #dddddd;
                    text-align: left;
                    padding: 8px;
                }
                
                tr:nth-child(even) {
                    background-color: #dddddd;
                }
            </style>
            <script>
            $(document).ready( function () {
                $('#myTable').DataTable();
            } )
            </script>
            </head>
            <body>
        """
    else:
        html_header = """
            <html>
            <head>
            <style>
                table {
                    font-family: Arial, sans-serif;
                    border-collapse: collapse;
                    width: 100%;
                }
                
                td, th {
                    border: 1px solid #dddddd;
                    text-align: left;
                    padding: 8px;
                }
                
                tr:nth-child(even) {
                    background-color: #dddddd;
                }
            </style>
            </head>
            <body>
        """

    html_footer = """
        </body>
        </html>
    """
    return html_header + html_inner + html_footer


def view_html(html):
    """Display HTML content in a web browser."""
    import tempfile
    import webbrowser

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as f:
        url = "file://" + f.name
        # Write the HTML content to the file
        f.write(html)

    # Open the URL in the web browser
    webbrowser.open(url)


def human_readable_labeler_creator():
    """Create a function that maps thread ids to human-readable labels.

    It is structured as a closure, so that the mapping is persistent.
    I.e., when the returned function is called, it will use the same
    dictionary to map thread ids to human-readable labels if it's seen that ID
    before; otherwise, it will add a new entry to the dictionary.
    This will persist across calls to the function.
    """
    d = {}

    def func(thread_id):
        if thread_id in d:
            return d[thread_id]
        else:
            d[thread_id] = len(d)
            return d[thread_id]

    return func


def get_multiline_textsize(text, font):
    """Get the size of the text when it is drawn on an image."""
    lines = text.split("\n")

    # Initialize width and height
    max_width = 0
    total_height = 0

    for line in lines:
        # Get the size of the text for the line
        box = font.getbbox(line)
        width, height = box[2], box[3]

        # Update max_width if width of the current line is greater than max_width
        max_width = max(max_width, width)

        # Add height to total_height
        total_height += height

    return max_width, total_height


def print_results_long(results, max_rows=None):
    from rich.console import Console
    from rich.table import Table

    console = Console(record=True)
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Result index", style="dim")
    table.add_column("Key", style="dim")
    table.add_column("Value", style="dim")
    list_of_dicts = results.to_dicts()
    num_rows = 0
    for i, results_dict in enumerate(list_of_dicts):
        for key, value in results_dict.items():
            table.add_row(str(i), key, str(value))
            num_rows += 1
        if max_rows is not None and num_rows >= max_rows:
            break
    console.print(table)


def print_dict_with_rich(d, key_name="Key", value_name="Value", filename=None):
    """Print a dictionary as a table using the rich library.

    Example:
    >>> print_dict_with_rich({"a": 1, "b": 2, "c": 3})
    ┏━━━━━┳━━━━━━━┓
    ┃ Key ┃ Value ┃
    ┡━━━━━╇━━━━━━━┩
    │ a   │ 1     │
    │ b   │ 2     │
    │ c   │ 3     │
    └─────┴───────┘
    """
    from rich.console import Console
    from rich.table import Table

    console = Console(record=True)
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(key_name, style="dim")
    table.add_column(value_name, style="dim")
    for key, value in d.items():
        table.add_row(key, str(value))
    console.print(table)
    # display_table(console, table, filename)


def print_dict_as_html_table(
    d,
    show=False,
    key_name="Key",
    value_name="Value",
    filename=None,
):
    """Print a dictionary as an HTML table.

    :param d: The dictionary to print.
    :param show: Whether to display the HTML table in the browser.
    :param key_name: The name of the key column.
    :param value_name: The name of the value column.
    :param filename: The name of the file to save the HTML table to.
    """
    # Start the HTML table
    html_table = f'<table border="1">\n<tr><th>{escape(key_name)}</th><th>{escape(value_name)}</th></tr>\n'

    # Add rows to the HTML table
    for key, value in d.items():
        html_table += (
            f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>\n"
        )

    # Close the HTML table
    html_table += "</table>"

    # Print the HTML table to console
    # print(html_table)

    # Write to file if a filename is provided
    if filename:
        with open(filename, "w") as file:
            file.write(html_table)
    else:
        if show:
            view_html(gen_html_sandwich(html_table))
        else:
            return html_table


def print_scenario_list(data):
    from rich.console import Console
    from rich.table import Table

    new_data = []
    for obs in data:
        try:
            _ = obs.pop("edsl_version")
            _ = obs.pop("edsl_class_name")
        except KeyError as e:
            # print(e)
            pass
        new_data.append(obs)

    columns = list(new_data[0].keys())
    console = Console(record=True)

    # Create a table object
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    for column in columns:
        table.add_column(column, style="dim")

    for obs in new_data:
        row = [str(obs[key]) for key in columns]
        table.add_row(*row)

    console.print(table)


def print_list_of_dicts_with_rich(data, filename=None, split_at_dot=True):
    raise Exception(
        "print_list_of_dicts_with_rich is now called print_dataset_with_rich"
    )


def print_dataset_with_rich(data, filename=None, split_at_dot=True):
    """Initialize console object."""
    """
    The list seems superfluous.
    This prints a list of dictionaries as a table using the rich library.

    >>> data = [{"a": [1, 2, 3], "b": [4, 5, 6]}]
    >>> print_list_of_dicts_with_rich(data)
    ┏━━━┳━━━┓
    ┃ a ┃ b ┃
    ┡━━━╇━━━┩
    │ 1 │ 4 │
    ├───┼───┤
    │ 2 │ 5 │
    ├───┼───┤
    │ 3 │ 6 │
    └───┴───┘
    """
    from rich.console import Console
    from rich.table import Table

    console = Console(record=True)

    # Create a table object
    table = Table(show_header=True, header_style="bold magenta", show_lines=True)

    # Adding columns to the table
    for d in data:
        for key in d.keys():
            if split_at_dot:
                value = key.replace(".", "\n.")
            else:
                value = key
            table.add_column(value, style="dim")

    # Adding rows to the table
    num_rows = len(next(iter(data[0].values())))
    for i in range(num_rows):
        row = [str(d[key][i]) for d in data for key in d.keys()]
        table.add_row(*row)

    console.print(table)
    # display_table(console, table, filename)


def create_latex_table_from_data(data, filename=None, split_at_dot=True):
    """
    This function takes a list of dictionaries and returns a LaTeX table as a string.
    The table can either be printed or written to a file.

    >>> data = [{"a": [1, 2, 3], "b": [4, 5, 6]}]
    >>> print(create_latex_table_from_data(data))
    \\begin{tabular}{|c|c|}
    \\hline
    a & b \\\\
    \\hline
    1 & 4 \\\\
    2 & 5 \\\\
    3 & 6 \\\\
    \\hline
    \\end{tabular}
    """

    def escape_latex(s):
        replacements = [
            ("_", r"\_"),
            ("&", r"\&"),
            ("%", r"\%"),
            ("$", r"\$"),
            ("#", r"\#"),
            ("{", r"\{"),
            ("}", r"\}"),
            ("~", r"\textasciitilde{}"),
            ("^", r"\textasciicircum{}"),
            ("\\", r"\textbackslash{}"),
        ]

        for old, new in replacements:
            s = s.replace(old, new)
        return s

    # Start the LaTeX table
    latex_table = ["\\begin{tabular}{|" + "c|" * len(data[0]) + "}"]
    latex_table.append("\\hline")

    # Add the header row
    headers = []
    for key in data[0].keys():
        if split_at_dot:
            value = key.replace(".", "\n.")
        else:
            value = key
        headers.append(escape_latex(value))
    latex_table.append(" & ".join(headers) + " \\\\")
    latex_table.append("\\hline")

    # Determine the number of rows
    num_rows = len(next(iter(data[0].values())))

    # Debugging: Print the keys of the dictionaries
    # print("Keys in data[0]:", list(data[0].keys()))

    # Add the data rows
    for i in range(num_rows):
        row = []
        for key in data[0].keys():
            for d in data:
                try:
                    row.append(escape_latex(str(d[key][i])))
                except KeyError as e:
                    print(
                        f"KeyError: {e} - Key '{key}' not found in data dictionary. The keys are {list(d.keys())}"
                    )
                    raise
        latex_table.append(" & ".join(row) + " \\\\")

    latex_table.append("\\hline")
    latex_table.append("\\end{tabular}")

    # Join all parts into a single string
    latex_table_str = "\n".join(latex_table)

    # Write to file if filename is provided
    if filename:
        with open(filename, "w") as f:
            f.write(latex_table_str)
            print(f"Table written to {filename}")

    return latex_table_str


def print_list_of_dicts_as_html_table(data, interactive=True):
    """Print a list of dictionaries as an HTML table.

    :param data: The list of dictionaries to print.
    :param filename: The name of the file to save the HTML table to.
    :param interactive: Whether to make the table interactive using DataTables.
    """
    style = """
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        table, th, td {
            border: 1px solid black;
        }
        th, td {
            padding: 10px;
            text-align: left;
        }
    </style>
    """
    html_table = style + '<table id="myTable" class="display">\n'
    html_table += "  <thead>\n"
    # Add the header row
    headers = [key for d in data for key in d.keys()]
    html_table += "  <tr>\n"
    for header in headers:
        html_table += f"    <th>{header}</th>\n"
    html_table += "  </tr>\n"
    html_table += "  </thead>\n</tbody>\n"

    # Determine the number of rows
    num_rows = max(len(values) for d in data for values in d.values())

    # Add the data rows
    for i in range(num_rows):
        html_table += "  <tr>\n"
        for d in data:
            for key in d.keys():
                value = d[key][i] if i < len(d[key]) else ""
                html_table += f"    <td>{value}</td>\n"
        html_table += "  </tr>\n"

    # Close the table
    html_table += "</tbody>\n"
    html_table += "</table>"
    return gen_html_sandwich(html_table, interactive=interactive)


def print_list_of_dicts_as_markdown_table(data, filename=None):
    """Print a list of dictionaries as a Markdown table.

    :param data: The list of dictionaries to print.
    :param filename: The name of the file to save the Markdown table to.
    """
    if not data:
        print("No data provided")
        return

    # Gather all unique headers
    # headers = list({key for d in data for key in d.keys()})
    headers = []
    for column in data:
        headers.append(list(column.keys())[0])

    markdown_table = "| " + " | ".join(headers) + " |\n"
    markdown_table += "|-" + "-|-".join(["" for _ in headers]) + "-|\n"

    num_rows = len(next(iter(data[0].values())))
    for i in range(num_rows):
        row = [str(d[key][i]) for d in data for key in d.keys()]
        # table.add_row(*row)
        markdown_table += "| " + " | ".join(row) + " |\n"

    # Output or save to file
    if filename:
        with open(filename, "w") as f:
            f.write(markdown_table)
    else:
        print(markdown_table)


def print_public_methods_with_doc(obj):
    """Print the public methods of an object along with their docstrings."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    public_methods_with_docstrings = [
        (method, getattr(obj, method).__doc__)
        for method in dir(obj)
        if callable(getattr(obj, method))
        and not method.startswith("_")
        and method != "methods"
    ]

    for method, doc in public_methods_with_docstrings:
        if doc:
            console.print(f"[bold]{method}:[/bold]", style="green")
            console.print(f"\t{doc.strip()}", style="yellow")


def print_tally_with_rich(data, filename=None):
    """Print a tally of values in a list using the rich library.

    Example:
    >>> data = {'a':12, 'b':14, 'c':9}
    >>> print_tally_with_rich(data)
    ┏━━━━━━━┳━━━━━━━┓
    ┃ Value ┃ Count ┃
    ┡━━━━━━━╇━━━━━━━┩
    │ a     │ 12    │
    │ b     │ 14    │
    │ c     │ 9     │
    └───────┴───────┘
    """
    # Initialize a console object
    from rich.console import Console
    from rich.table import Table
    from IPython.display import display

    console = Console(record=True)

    # Create a new table
    table = Table(show_header=True, header_style="bold magenta", row_styles=["", "dim"])

    # Add columns to the table
    table.add_column("Value", style="dim")
    table.add_column("Count", style="dim")

    # Add rows to the table
    for key, value in data.items():
        table.add_row(key, str(value))

    from IPython.display import display

    display_table(console, table, filename)


def print_table_with_rich(data, filename=None):
    """Print a list of dictionaries as a table using the rich library.

    Example:
    >>> data = [{"a": 1, "b": 2, "c": 3}]
    >>> print_table_with_rich(data)
    ┏━━━┳━━━┳━━━┓
    ┃ a ┃ b ┃ c ┃
    ┡━━━╇━━━╇━━━┩
    │ 1 │ 2 │ 3 │
    └───┴───┴───┘
    >>> data = [{"a": 1, "b": 2, "c": 3},{"a": 2, "b": 9, "c": 8}]
    >>> print_table_with_rich(data)
    ┏━━━┳━━━┳━━━┓
    ┃ a ┃ b ┃ c ┃
    ┡━━━╇━━━╇━━━┩
    │ 1 │ 2 │ 3 │
    │ 2 │ 9 │ 8 │
    └───┴───┴───┘
    """
    from rich.console import Console
    from rich.table import Table

    # Initialize a console object - expects a list of dictionaries
    console = Console(record=True)

    # Create a new table
    table = Table(show_header=True, header_style="bold magenta", row_styles=["", "dim"])

    # Check if data is empty; if it is, exit
    if not data:
        console.print("No data provided!")
        return

    # Add columns based on keys in the first dictionary
    for key in data[0].keys():
        table.add_column(key, style="dim")

    # Add rows to the table
    for row in data:
        table.add_row(*[str(value) for value in row.values()])

    display_table(console, table, filename)


if __name__ == "__main__":
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3})
    import doctest

    doctest.testmod()
    # print_list_of_dicts_with_rich([{"a": [1, 2, 3], "b": [4, 5, 6]}])
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html")
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, show=True)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=True)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=False)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=True)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=False)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=True)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=False)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=True)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=False)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=True)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=False)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=True)
    # print_dict_as_html_table({"a": 1, "b": 2, "c": 3}, filename="test.html", show=False)
    # print_dict_as_html_table({"a": 1, "b": 2, "c
