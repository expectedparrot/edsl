from dataclasses import dataclass
from typing import Any, List


@dataclass
class TableData:
    """Simple data class to hold table information"""

    headers: List[str]
    data: List[List[Any]]
    parameters: dict = None
    raw_data_set: Any = None
