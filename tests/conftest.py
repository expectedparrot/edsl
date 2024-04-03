import pytest


@pytest.fixture(scope="function", autouse=True)
async def clear_after_test():
    """
    This fixture does some things after each test (function) runs.
    """
    # Before the test runs, do nothing
    yield
    # After the test completes, do the following

    # e.g., you could clear your database
