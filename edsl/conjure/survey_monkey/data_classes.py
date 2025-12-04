"""Data classes and enums for Survey Monkey CSV parsing."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Any


class Column:
    """A column of values from a CSV file."""

    def __init__(self, name: str, values: list):
        self.name = name
        self._values = values

    def __repr__(self):
        return repr(self._values)

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __getitem__(self, index):
        return self._values[index]

    def __add__(self, other):
        new_data = []
        for a, b in zip(self._values, other._values):
            if isinstance(a, list) and isinstance(b, list):
                new_data.append(a + b)
            elif isinstance(a, list) and isinstance(b, str):
                if b == "":
                    new_data.append(a)
                else:
                    new_data.append(a + [b])
            elif isinstance(a, str) and isinstance(b, list):
                if a == "":
                    new_data.append(b)
                else:
                    new_data.append([a] + b)
            elif isinstance(a, str) and isinstance(b, str):
                if b == "":
                    new_data.append(a)
                elif a == "":
                    new_data.append(b)
                else:
                    new_data.append([a, b])
            else:
                raise ValueError(f"Cannot add {type(a)} and {type(b)}")
        return Column(self.name + other.name, new_data)

    def first_n_rows(self, n: int = 5):
        return "\n".join([f"{i}: {row}" for i, row in enumerate(self._values[:n])])


class DataType(Enum):
    """Type of data in a column group."""
    PREPEND = "prepend"
    SURVEY_RESPONSE = "survey_response"


class ColumnType(Enum):
    """Classification of individual columns."""
    PREPEND = auto()
    QUESTION_START = auto()
    QUESTION_CONTINUATION = auto()
    QUESTION_VIEWED = auto()


@dataclass
class PrependData:
    """Metadata fields prepended to survey responses (e.g., Respondent ID, dates)."""
    column_index: int
    column_name: str
    values: List[Any]


@dataclass
class GroupData:
    """A group of columns representing a single question or prepend field."""
    data_type: DataType | None
    start_index: int | None
    end_index: int | None
    _first_lines: List[str] = None
    _second_lines: List[str] = None

    def __len__(self):
        return self.end_index - self.start_index + 1

    def __getitem__(self, index):
        return self.data[index]

    def first_lines(self):
        if self._first_lines is None:
            raise ValueError("first_lines not set on GroupData")
        return [self._first_lines[i] for i in range(self.start_index, self.end_index + 1)]

    def second_lines(self):
        if self._second_lines is None:
            raise ValueError("second_lines not set on GroupData")
        return [self._second_lines[i] for i in range(self.start_index, self.end_index + 1)]


@dataclass
class MonadicQuestion:
    """A question where the text varies per row with parameterized values."""
    question_template: str
    slots: List[Any]  # List of SlotInfo objects with their values
    responses: List[str]
    column_index: int


@dataclass
class QuestionMapping:
    """Maps a question name to its column indices and type."""
    question_name: str
    column_indices: List[int]
    is_checkbox: bool
    is_multiple_choice_with_other: bool = False


# Standard Survey Monkey header fields
SURVEY_MONKEY_HEADERS = [
    "Respondent ID",
    "Collector ID",
    "Start Date",
    "End Date",
    "Email Address",
    "First Name",
    "Last Name",
]

