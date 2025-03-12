"""A module for displaying data in various formats.

This module provides utility functions for formatting and displaying data,
primarily used by the Results module for printing results.
"""

# Only print_results_long is actively used in the codebase (in results.py)
# The rest of the functions are kept for reference but are not imported in __init__.py


def print_results_long(results, max_rows=None):
    """
    Format results data as a rich console table with columns for index, key, and value.
    
    Args:
        results: The Results object to display
        max_rows: Optional maximum number of rows to display
    """
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


# The rest of these functions are not actively used by the codebase
# They are kept but commented out for potential future reference

"""
def create_image(console, image_filename):
    font_size = 15
    from PIL import Image, ImageDraw, ImageFont

    text = console.export_text()

    font_size = 15
    font = ImageFont.load_default()
    text_width, text_height = get_multiline_textsize(text, font)
    image = Image.new(
        "RGB", (text_width + 20, text_height + 20), color=(255, 255, 255)
    )
    d = ImageDraw.Draw(image)
    d.multiline_text((10, 10), text, font=font, fill=(0, 0, 0))
    image.save(image_filename)


def display_table(console, table, filename):
    if filename is not None:
        with open(filename, "w") as f:
            with console.capture() as capture:
                console.print(table)
            f.write(capture.get())
        create_image(console, filename + ".png")
    else:
        console.print(table)


def gen_html_sandwich(html_inner, interactive=False):
    return html_inner


def view_html(html):
    import tempfile
    import webbrowser

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as f:
        url = "file://" + f.name
        f.write(html)
    webbrowser.open(url)


def get_multiline_textsize(text, font):
    lines = text.split("\n")
    max_width = 0
    total_height = 0

    for line in lines:
        box = font.getbbox(line)
        width, height = box[2], box[3]
        max_width = max(max_width, width)
        total_height += height

    return max_width, total_height


def print_dict_with_rich(d, key_name="Key", value_name="Value", filename=None):
    from rich.console import Console
    from rich.table import Table

    console = Console(record=True)
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column(key_name, style="dim")
    table.add_column(value_name, style="dim")
    for key, value in d.items():
        table.add_row(key, str(value))
    console.print(table)


def print_table_with_rich(data, filename=None):
    from rich.console import Console
    from rich.table import Table

    console = Console(record=True)
    table = Table(show_header=True, header_style="bold magenta", row_styles=["", "dim"])

    if not data:
        console.print("No data provided!")
        return

    for key in data[0].keys():
        table.add_column(key, style="dim")

    for row in data:
        table.add_row(*[str(value) for value in row.values()])

    console.print(table)
"""


if __name__ == "__main__":
    import doctest

    doctest.testmod()