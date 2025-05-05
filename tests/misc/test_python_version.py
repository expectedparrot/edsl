"""Test Python version compatibility."""
import sys


def test_python_version():
    """Test that the current Python version is supported."""
    version = sys.version_info
    major, minor = version.major, version.minor
    
    # EDSL supports Python 3.9 to 3.13
    assert major == 3
    assert 9 <= minor <= 13, f"Python version 3.{minor} is not supported"
    
    print(f"Running on Python {major}.{minor}")