"""
Base class for vibe processing steps.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from edsl.questions import Question


@dataclass
class ProcessingResult:
    """Result of a processing step."""
    question: Question
    changed: bool
    changes: List[Dict[str, Any]]
    confidence: float
    reasoning: str


class BaseProcessor(ABC):
    """Base class for processing steps."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    @abstractmethod
    async def process(self, question: Question, context: Optional[Dict[str, Any]] = None) -> ProcessingResult:
        """
        Process a question and return the result.

        Args:
            question: Question to process
            context: Optional context data (response data, etc.)

        Returns:
            ProcessingResult with the improved question and metadata
        """
        pass

    def log(self, message: str):
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"  {self.__class__.__name__}: {message}")