def is_notebook() -> bool:
    """Check if the code is running in a Jupyter notebook, Google Colab, or marimo."""
    import sys

    # Check for marimo first (doesn't use IPython)
    if "marimo" in sys.modules:
        return True

    try:
        from IPython import get_ipython

        ipy = get_ipython()
        if ipy is None:
            return False

        shell = ipy.__class__.__name__
        if shell == "ZMQInteractiveShell":
            # Jupyter console can use ZMQInteractiveShell but behaves like a terminal.
            # If stdout is a TTY, avoid notebook-only HTML displays.
            stdout = getattr(sys, "stdout", None)
            if stdout is not None and hasattr(stdout, "isatty") and stdout.isatty():
                return False
            return True  # Jupyter notebook or qtconsole
        elif shell == "Shell":  # Google Colab's shell class
            if "google.colab" in sys.modules:
                return True  # Running in Google Colab
            return False
        elif shell == "TerminalInteractiveShell":
            return False  # Terminal running IPython
        else:
            return False  # Other type
    except (ImportError, NameError):
        return False  # Probably standard Python interpreter
