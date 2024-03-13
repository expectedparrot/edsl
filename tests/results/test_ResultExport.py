import pytest

from edsl.results import Results
r = Results.example()

def test_print():
    r.print(format = "rich")
    r.print(format = "html")
    r.print(format = "markdown")

def test_bad_name():
    with pytest.raises(ValueError):
        r.print(format = "bad")

