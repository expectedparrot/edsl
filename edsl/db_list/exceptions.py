"""
Exception classes for the SQLList module.
"""

from ..base.base_exception import BaseException


class SQLListError(BaseException):
    """Base exception for SQLList-related errors."""
    doc_page = "utilities"


class SQLListIndexError(SQLListError):
    """Raised when an invalid index is used with SQLList."""
    pass


class SQLListValueError(SQLListError):
    """Raised when an operation receives an invalid value in SQLList."""
    pass