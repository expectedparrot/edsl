def is_notebook() -> bool:
    """Check if the code is running in a Jupyter notebook, Google Colab, or marimo."""
    import sys

    # Check for marimo first (doesn't use IPython)
    if "marimo" in sys.modules:
        return True

    try:
        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            return True  # Jupyter notebook or qtconsole
        elif shell == "Shell":  # Google Colab's shell class
            if "google.colab" in sys.modules:
                return True  # Running in Google Colab
            return False
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type
    except NameError:
        return False  # Probably standard Python interpreter
