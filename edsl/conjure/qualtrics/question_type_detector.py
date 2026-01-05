"""Question type detection for Qualtrics data."""

from typing import List, Callable

from .data_classes import QualtricsQuestionMetadata, Column, DataType


class QualtricsQuestionTypeDetector:
    """Detect question types from Qualtrics data patterns.

    Handles:
    - Analyzing response values
    - Identifying text/MC/checkbox/linear scale types
    - Distinguishing metadata from question columns
    """

    # Phrases that indicate checkbox questions
    CHECKBOX_PHRASES = [
        "select all that apply",
        "check all that apply",
        "mark all that apply",
    ]

    # Phrases that indicate linear scale questions
    SCALE_PHRASES = [
        "scale of",
        "rate from",
        "rating scale",
        "slider",
    ]

    def __init__(
        self,
        columns: List[Column],
        is_metadata_func: Callable[[QualtricsQuestionMetadata], bool],
        verbose: bool = False,
    ):
        """
        Initialize the question type detector.

        Args:
            columns: List of data columns
            is_metadata_func: Function to check if a column is metadata
            verbose: Print detailed processing information
        """
        self.columns = columns
        self.is_metadata_func = is_metadata_func
        self.verbose = verbose

    def detect(self, question_group: List[QualtricsQuestionMetadata]) -> DataType:
        """Detect the question type for a group of related columns.

        Args:
            question_group: List of metadata for columns belonging to the same question

        Returns:
            The detected DataType
        """
        if len(question_group) == 0:
            return DataType.UNKNOWN

        # Check if all are metadata columns
        if all(self.is_metadata_func(meta) for meta in question_group):
            return DataType.METADATA

        # Single column questions
        if len(question_group) == 1:
            return self._detect_single_column(question_group[0])

        # Multi-column questions
        return self._detect_multi_column(question_group)

    def _detect_single_column(self, meta: QualtricsQuestionMetadata) -> DataType:
        """Detect type for a single-column question.

        Args:
            meta: The column metadata

        Returns:
            The detected DataType
        """
        question_text = meta.question_text.lower()

        # Look for checkbox indicators
        if any(phrase in question_text for phrase in self.CHECKBOX_PHRASES):
            return DataType.QUESTION_CHECKBOX

        # Look for scale indicators
        if any(phrase in question_text for phrase in self.SCALE_PHRASES):
            return DataType.QUESTION_LINEAR_SCALE

        # Check response patterns
        col_values = self.columns[meta.column_index].values
        unique_values = list(set([v for v in col_values if v and str(v).strip()]))

        # Linear scale detection: all numeric, small range
        try:
            numeric_values = [float(v) for v in unique_values]
            if len(numeric_values) == len(unique_values) and len(numeric_values) <= 11:
                return DataType.QUESTION_LINEAR_SCALE
        except (ValueError, TypeError):
            pass

        # Multiple choice vs free text based on unique values
        if len(unique_values) <= 20:
            return DataType.QUESTION_MULTIPLE_CHOICE
        else:
            return DataType.QUESTION_TEXT

    def _detect_multi_column(
        self, question_group: List[QualtricsQuestionMetadata]
    ) -> DataType:
        """Detect type for a multi-column question.

        Args:
            question_group: List of metadata for columns belonging to the same question

        Returns:
            The detected DataType
        """
        # Check for binary responses (typical of checkboxes)
        all_binary = True
        for meta in question_group:
            col_values = self.columns[meta.column_index].values
            unique_values = set(
                [str(v).lower() for v in col_values if v and str(v).strip()]
            )
            if not unique_values.issubset(
                {"1", "0", "true", "false", "yes", "no", "checked", ""}
            ):
                all_binary = False
                break

        if all_binary:
            return DataType.QUESTION_CHECKBOX
        else:
            return DataType.QUESTION_MULTIPLE_CHOICE
