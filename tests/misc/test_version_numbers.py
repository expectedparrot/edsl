# a test that checks the version numbers in pyproject.toml is the same as in
# import edsl
# edsl.__version__


import sys
import pytest

@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires Python 3.11+")
def test_version_numbers():
    import tomllib
    import edsl

    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    assert edsl.__version__ == pyproject["tool"]["poetry"]["version"]
