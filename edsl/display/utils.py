"""
Utility functions for display-related operations.

This module provides helper functions that build on the core display functionality
to perform common display-related tasks used throughout the edsl package.
"""

from .core import HTML, display, is_notebook_environment


def file_notice(file_name, link_text="Download file"):
    """
    Display a notice about a file being created, with a download link in notebook environments.

    Args:
        file_name (str): The path to the file
        link_text (str): The text to display for the download link

    Returns:
        None
    """
    if is_notebook_environment():
        html_content = f'<p>File created: {file_name}</p><a href="{file_name}" download>{link_text}</a>'
        display(HTML(html_content))
    else:
        print(f"File created: {file_name}")


def smart_truncate(text, max_length, ellipsis="..."):
    """
    Truncate a string at whitespace boundaries to avoid breaking URLs or important strings.
    URLs are never truncated as they need to remain functional.

    Args:
        text (str): The text to truncate
        max_length (int): Maximum length of the truncated string (including ellipsis)
        ellipsis (str): The ellipsis string to append when truncating

    Returns:
        str: The truncated string, or original string if it's a URL
    """
    if len(text) <= max_length:
        return text

    # Check if this looks like a URL - if so, don't truncate it
    # URLs should remain functional
    if text.startswith(("http://", "https://", "ftp://", "ftps://")) or "://" in text:
        return text

    # If the text needs to be truncated
    target_length = max_length - len(ellipsis)

    # If target length is too small, just do simple truncation
    if target_length < 10:
        return text[:target_length] + ellipsis

    # Try to find a good breaking point (whitespace)
    # Look for the last whitespace character within a reasonable range
    # We'll search backwards up to 20% of the target length to find whitespace
    search_start = max(target_length - int(target_length * 0.2), target_length // 2)

    for i in range(target_length - 1, search_start - 1, -1):
        if text[i].isspace():
            return text[:i] + ellipsis

    # If no good break point found, fall back to simple truncation
    return text[:target_length] + ellipsis


def display_html(html_content, width=None, height=None, as_iframe=False):
    """
    Display HTML content, optionally within an iframe.

    Args:
        html_content (str): The HTML content to display
        width (int, optional): Width of the iframe (if as_iframe=True)
        height (int, optional): Height of the iframe (if as_iframe=True)
        as_iframe (bool): Whether to display the content in an iframe

    Returns:
        None
    """
    from html import escape

    if as_iframe:
        width = width or 600
        height = height or 200
        escaped_output = escape(html_content)
        iframe_html = f'<iframe srcdoc="{escaped_output}" style="width: {width}px; height: {height}px;"></iframe>'
        display(HTML(iframe_html))
    else:
        display(HTML(html_content))
