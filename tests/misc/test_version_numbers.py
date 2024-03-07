# a test that checks the version numbers in pyproject.toml is the same as in
# import edsl
# edsl.__version__


def test_version_numbers():
    import edsl
    from toml import load

    with open("pyproject.toml", "r") as f:
        pyproject = load(f)
    assert edsl.__version__ == pyproject["tool"]["poetry"]["version"]
