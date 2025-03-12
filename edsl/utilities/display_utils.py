"""Utility functions for display and formatting."""

from html import escape


class Markdown:
    """Wrapper class for Markdown text display in Jupyter."""

    def __init__(self, text: str):
        self.text = text

    def __str__(self):
        return self.text
    
    def _repr_markdown_(self):
        return self.text


def dict_to_html(d):
    """Convert a dictionary to an HTML table."""
    # Start the HTML table
    html_table = f'<table border="1">\n<tr><th>{escape("Key")}</th><th>{escape("Value")}</th></tr>\n'

    # Add rows to the HTML table
    for key, value in d.items():
        html_table += (
            f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>\n"
        )

    # Close the HTML table
    html_table += "</table>"
    return html_table