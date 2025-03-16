"""
Core display functionality that abstracts IPython.display.

This module provides wrapper classes and functions that abstract the IPython.display
functionality to enable potential future replacement with alternative implementations.
"""

try:
    from IPython.display import display as ipython_display
    from IPython.display import HTML as IPythonHTML
    from IPython.display import FileLink as IPythonFileLink
    from IPython.display import IFrame as IPythonIFrame
    _IPYTHON_AVAILABLE = True
except ImportError:
    _IPYTHON_AVAILABLE = False


def is_notebook_environment():
    """
    Check if code is running in a Jupyter notebook or similar interactive environment.
    
    Returns:
        bool: True if running in a notebook environment, False otherwise
    """
    try:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "Shell":  # Google Colab's shell class
            import sys
            if "google.colab" in sys.modules:
                return True  # Running in Google Colab
            return False
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type
    except (NameError, ImportError):
        return False  # Probably standard Python interpreter


class HTML:
    """
    Wrapper for IPython's HTML display class.
    
    This class provides the same functionality as IPython.display.HTML but can be
    extended or replaced with alternative implementations.
    """
    def __init__(self, data=None, metadata=None, **kwargs):
        self.data = data
        self.metadata = metadata
        self.kwargs = kwargs
        
        if _IPYTHON_AVAILABLE and is_notebook_environment():
            self._ipython_html = IPythonHTML(data, metadata, **kwargs)
        else:
            self._ipython_html = None

    def __repr__(self):
        """Return a string representation of the HTML object."""
        return f"{self.data}"

    def _repr_html_(self):
        """Return HTML representation of the object."""
        if self._ipython_html:
            return self._ipython_html._repr_html_()
        return self.data


class FileLink:
    """
    Wrapper for IPython's FileLink display class.
    
    This class provides the same functionality as IPython.display.FileLink but can be
    extended or replaced with alternative implementations.
    """
    def __init__(self, path, url_prefix='', result_html_prefix='', result_html_suffix='', **kwargs):
        self.path = path
        self.url_prefix = url_prefix
        self.result_html_prefix = result_html_prefix 
        self.result_html_suffix = result_html_suffix
        self.kwargs = kwargs
        
        if _IPYTHON_AVAILABLE and is_notebook_environment():
            self._ipython_filelink = IPythonFileLink(
                path, 
                url_prefix, 
                result_html_prefix, 
                result_html_suffix,
                **kwargs
            )
        else:
            self._ipython_filelink = None

    def _repr_html_(self):
        """Return HTML representation of the file link."""
        if self._ipython_filelink:
            return self._ipython_filelink._repr_html_()
        return f'<a href="{self.url_prefix}{self.path}" target="_blank">{self.path}</a>'


class IFrame:
    """
    Wrapper for IPython's IFrame display class.
    
    This class provides the same functionality as IPython.display.IFrame but can be
    extended or replaced with alternative implementations.
    """
    def __init__(self, src, width, height, **kwargs):
        self.src = src
        self.width = width
        self.height = height
        self.kwargs = kwargs
        
        if _IPYTHON_AVAILABLE and is_notebook_environment():
            self._ipython_iframe = IPythonIFrame(src, width, height, **kwargs)
        else:
            self._ipython_iframe = None

    def _repr_html_(self):
        """Return HTML representation of the iframe."""
        if self._ipython_iframe:
            return self._ipython_iframe._repr_html_()
        return f'<iframe src="{self.src}" width="{self.width}" height="{self.height}"></iframe>'


def display(obj, *args, **kwargs):
    """
    Display an object in the frontend.
    
    Wrapper around IPython.display.display that can be extended or replaced with
    alternative implementations.
    
    Args:
        obj: The object to display
        *args: Additional objects to display
        **kwargs: Additional keyword arguments for display
    """
    if _IPYTHON_AVAILABLE and is_notebook_environment():
        ipython_display(obj, *args, **kwargs)
    else:
        # Fallback behavior when not in notebook environment
        if hasattr(obj, '_repr_html_'):
            print("HTML representation available, but not in notebook environment.")
        print(repr(obj))
        for arg in args:
            print(repr(arg))