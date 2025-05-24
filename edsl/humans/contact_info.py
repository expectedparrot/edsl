from __future__ import annotations

"""Lightweight container for participant contact information.

The :class:`ContactInfo` dataclass is responsible for holding the four standard
contact-related attributes we track for a participant and offers utility
helpers to *peel* them out of a free-form ``**kwargs`` mapping so that caller
code (e.g. :class:`~edsl.humans.human.Human`) can stay tidy.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ContactInfo:
    """Dataclass holding a participant's contact information.

    Attributes
    ----------
    email, phone, prolific_id, ep_username : Optional[str]
        Standard contact channels we support.  All fields are optional; at
        least one must be non-``None`` for a *valid* Human.
    """

    email: Optional[str] = None
    phone: Optional[str] = None
    prolific_id: Optional[str] = None
    ep_username: Optional[str] = None

    # ------------------------------------------------------------------
    # Class helpers
    # ------------------------------------------------------------------
    _FIELDS = ("email", "phone", "prolific_id", "ep_username")

    @classmethod
    def from_kwargs(cls, kwargs: Dict[str, Any]) -> "ContactInfo":
        """Pop and return all contact-related keys from *kwargs*.

        This mutates the supplied mapping (it *pops* recognised keys) and returns
        a populated :class:`ContactInfo` instance.
        """
        extracted: Dict[str, Any] = {field: kwargs.pop(field, None) for field in cls._FIELDS}
        return cls(**extracted)

    # ------------------------------------------------------------------
    # Instance helpers
    # ------------------------------------------------------------------
    def as_dict(self) -> Dict[str, Optional[str]]:
        """Return a shallow dict representation (handy for JSON serialisation)."""
        return {field: getattr(self, field) for field in self._FIELDS}

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def is_valid_email(email: str) -> bool:
        """Basic regex-based email validation.

        Examples
        --------
        >>> ContactInfo.is_valid_email("test@example.com")
        True
        >>> ContactInfo.is_valid_email("invalid-email")
        False
        """
        import re  # local import avoids cost when unused

        email_pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return bool(re.match(email_pattern, email)) 