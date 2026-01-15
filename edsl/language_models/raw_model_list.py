"""
RawModelList - A simple list of Models without event-sourcing.

This is used for testing scenarios where Models have custom behavior
(like func=, throw_exception, scripted_responses) that cannot be serialized.

For production use, prefer ModelList which has git-like versioning support.
"""

from __future__ import annotations
from typing import Optional, List, TYPE_CHECKING
from collections import UserList

if TYPE_CHECKING:
    from ..language_models import LanguageModel


class RawModelList(UserList):
    """
    A simple list of Model objects without event-sourcing.

    Used for tests that need Model features that can't be serialized:
    - Custom func= parameter
    - throw_exception / exception_probability
    - from_scripted_responses()

    For production code, use ModelList instead.
    """

    def __init__(self, data: Optional[List["LanguageModel"]] = None):
        super().__init__(data or [])
