"""
Display utility functions providing IPython display abstractions.

Moved from the former edsl.display module into utilities to reduce module count.
"""

try:
    from IPython.display import display as ipython_display
    from IPython.display import HTML as IPythonHTML

    _IPYTHON_AVAILABLE = True
except ImportError:
    _IPYTHON_AVAILABLE = False


def is_notebook_environment():
    """Check if code is running in a Jupyter notebook or similar interactive environment."""
    try:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True
        elif shell == "Shell":
            import sys
            if "google.colab" in sys.modules:
                return True
            return False
        elif shell == "TerminalInteractiveShell":
            return False
        else:
            return False
    except (NameError, ImportError):
        return False


class HTML:
    """Wrapper for IPython's HTML display class with fallback for non-notebook environments."""

    def __init__(self, data=None, metadata=None, **kwargs):
        self.data = data
        self.metadata = metadata
        self.kwargs = kwargs

        if _IPYTHON_AVAILABLE and is_notebook_environment():
            self._ipython_html = IPythonHTML(data, metadata, **kwargs)
        else:
            self._ipython_html = None

    def __repr__(self):
        return f"{self.data}"

    def _repr_html_(self):
        if self._ipython_html:
            return self._ipython_html._repr_html_()
        return self.data


def display(obj, *args, **kwargs):
    """Display an object in the frontend, with fallback for non-notebook environments."""
    if _IPYTHON_AVAILABLE and is_notebook_environment():
        ipython_display(obj, *args, **kwargs)
    else:
        if hasattr(obj, "_repr_html_"):
            print("HTML representation available, but not in notebook environment.")
        print(repr(obj))
        for arg in args:
            print(repr(arg))


def file_notice(file_name, link_text="Download file"):
    """Display a notice about a file being created, with a download link in notebook environments."""
    if is_notebook_environment():
        html_content = f'<p>File created: {file_name}</p><a href="{file_name}" download>{link_text}</a>'
        display(HTML(html_content))
    else:
        print(f"File created: {file_name}")


def smart_truncate(text, max_length, ellipsis="..."):
    """Truncate a string at whitespace boundaries. URLs are never truncated."""
    if len(text) <= max_length:
        return text

    if text.startswith(("http://", "https://", "ftp://", "ftps://")) or "://" in text:
        return text

    target_length = max_length - len(ellipsis)

    if target_length < 10:
        return text[:target_length] + ellipsis

    search_start = max(target_length - int(target_length * 0.2), target_length // 2)

    for i in range(target_length - 1, search_start - 1, -1):
        if text[i].isspace():
            return text[:i] + ellipsis

    return text[:target_length] + ellipsis


def display_html(html_content, width=None, height=None, as_iframe=False):
    """Display HTML content, optionally within an iframe."""
    from html import escape

    if as_iframe:
        width = width or 600
        height = height or 200
        escaped_output = escape(html_content)
        iframe_html = f'<iframe srcdoc="{escaped_output}" style="width: {width}px; height: {height}px;"></iframe>'
        display(HTML(iframe_html))
    else:
        display(HTML(html_content))
