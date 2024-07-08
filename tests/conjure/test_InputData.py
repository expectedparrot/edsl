import pytest
import doctest
from edsl.conjure import InputData

def test_doctests():
    # Use doctest to run the tests
    doctest.testmod(InputData, verbose=True)

if __name__ == "__main__":
    pytest.main()