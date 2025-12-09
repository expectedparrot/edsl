"""Data classes for Qualtrics CSV processing."""

from dataclasses import dataclass
from typing import List, Any, Optional
from enum import Enum


class DataType(Enum):
    """Data types detected in Qualtrics CSV columns."""

    METADATA = "metadata"  # StartDate, EndDate, ResponseId, etc.
    QUESTION_TEXT = "question_text"  # Free text responses
    QUESTION_MULTIPLE_CHOICE = "question_multiple_choice"  # Single selection
    QUESTION_CHECKBOX = "question_checkbox"  # Multiple selections
    QUESTION_LINEAR_SCALE = "question_linear_scale"  # Numeric scales
    QUESTION_MULTIPLE_CHOICE_WITH_OTHER = "question_multiple_choice_with_other"
    UNKNOWN = "unknown"


@dataclass
class Column:
    """A column of values from CSV."""

    name: str
    _values: list

    def __iter__(self):
        return iter(self._values)

    def __getitem__(self, index):
        return self._values[index]

    def __len__(self):
        return len(self._values)

    @property
    def values(self) -> list:
        return self._values


@dataclass
class PrependData:
    """Metadata fields (ResponseId, dates, custom fields)."""

    column_index: int
    column_name: str
    values: List[Any]


@dataclass
class GroupData:
    """Groups of columns representing a single question."""

    data_type: DataType | None
    start_index: int | None
    end_index: int | None


@dataclass
class QuestionMapping:
    """Maps question names to their column indices."""

    question_name: str
    column_indices: List[int]
    is_checkbox: bool
    is_multiple_choice_with_other: bool = False


@dataclass
class QualtricsQuestionMetadata:
    """Metadata extracted from Qualtrics headers."""

    short_label: str  # Q1, Q2_1, etc. (row 1)
    question_text: str  # Human readable question text (row 2)
    import_id: str  # QID1, QID2_1, etc. (row 3)
    question_name: str  # Canonicalized name for grouping
    subpart: Optional[str]  # For multi-part questions (e.g., "_1", "_TEXT")
    column_index: int  # Original column position
