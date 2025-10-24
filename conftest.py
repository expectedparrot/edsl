import os
import pytest


def pytest_configure(config):
    """
    Set environment variable when pytest is running, particularly for doctests.
    """
    # Set a general pytest flag
    os.environ["EDSL_RUNNING_IN_PYTEST"] = "True"

    # Check if doctests are being run
    if config.option.doctestmodules:
        os.environ["EDSL_RUNNING_DOCTESTS"] = "True"


def pytest_unconfigure(config):
    """
    Clean up environment variables after pytest finishes.
    """
    os.environ.pop("EDSL_RUNNING_IN_PYTEST", None)
    os.environ.pop("EDSL_RUNNING_DOCTESTS", None)
