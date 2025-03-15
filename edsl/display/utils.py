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