"""Response extraction for Qualtrics data."""

from typing import List, Dict, Any, Callable, Optional

from edsl.surveys import Survey

from .data_classes import QualtricsQuestionMetadata, Column, QuestionMapping


class QualtricsResponseExtractor:
    """Extract response records from Qualtrics data.

    Handles:
    - Building question-to-column mappings
    - Handling checkbox/matrix responses
    - Creating response dictionaries per respondent
    """

    def __init__(
        self,
        columns: List[Column],
        metadata_columns: List[QualtricsQuestionMetadata],
        survey: Survey,
        is_metadata_func: Callable[[QualtricsQuestionMetadata], bool],
        resolve_piping_func: Callable[[Dict[str, Any]], None],
        verbose: bool = False,
    ):
        """
        Initialize the response extractor.

        Args:
            columns: List of data columns
            metadata_columns: List of column metadata
            survey: The built EDSL Survey
            is_metadata_func: Function to check if a column is metadata
            resolve_piping_func: Function to resolve piping in a record
            verbose: Print detailed processing information
        """
        self.columns = columns
        self.metadata_columns = metadata_columns
        self.survey = survey
        self.is_metadata_func = is_metadata_func
        self.resolve_piping_func = resolve_piping_func
        self.verbose = verbose

        self._question_mappings: List[QuestionMapping] = []

    def build_mappings(self) -> List[QuestionMapping]:
        """Build mappings from question names to column indices.

        Returns:
            List of QuestionMapping objects
        """
        if self.verbose:
            print("Building question mappings...")

        from collections import defaultdict

        mappings = defaultdict(list)

        for meta in self.metadata_columns:
            if not self.is_metadata_func(meta):
                mappings[meta.question_name].append(meta.column_index)

        self._question_mappings = []
        for question_name, indices in mappings.items():
            # Check if this question is a matrix question in the survey
            is_matrix = False
            if self.survey:
                for question in self.survey.questions:
                    if (
                        question.question_name == question_name
                        and question.question_type in ["matrix", "matrix_entry"]
                    ):
                        is_matrix = True
                        break

            # Determine if it's a checkbox question (only if not matrix)
            is_checkbox = len(indices) > 1 and not is_matrix

            self._question_mappings.append(
                QuestionMapping(
                    question_name=question_name,
                    column_indices=indices,
                    is_checkbox=is_checkbox,
                    is_matrix=is_matrix,
                )
            )

        return self._question_mappings

    def extract_records(self) -> List[Dict[str, Any]]:
        """Extract response records for each respondent.

        Returns:
            List of response dictionaries, one per respondent
        """
        if self.verbose:
            print("Building response records...")

        if not self._question_mappings:
            self.build_mappings()

        response_records = []

        if not self.columns:
            return response_records

        num_respondents = len(self.columns[0].values)

        for respondent_idx in range(num_respondents):
            record = self._extract_single_record(respondent_idx)

            # Resolve piping in responses
            self.resolve_piping_func(record)

            response_records.append(record)

        if self.verbose:
            print(f"Built {len(response_records)} response records")

        return response_records

    def _extract_single_record(self, respondent_idx: int) -> Dict[str, Any]:
        """Extract a single respondent's record.

        Args:
            respondent_idx: Index of the respondent

        Returns:
            Dictionary of question_name -> answer
        """
        record = {}

        for mapping in self._question_mappings:
            question_name = mapping.question_name

            if mapping.is_matrix:
                record[question_name] = self._extract_matrix_response(
                    mapping, respondent_idx
                )
            elif mapping.is_checkbox:
                record[question_name] = self._extract_checkbox_response(
                    mapping, respondent_idx
                )
            else:
                record[question_name] = self._extract_single_response(
                    mapping, respondent_idx
                )

        return record

    def _extract_matrix_response(
        self, mapping: QuestionMapping, respondent_idx: int
    ) -> Dict[str, Any]:
        """Extract a matrix question response.

        Args:
            mapping: The question mapping
            respondent_idx: Index of the respondent

        Returns:
            Dictionary of item_name -> value
        """
        matrix_answer = {}

        # Find the matrix question in the survey to get question_items
        matrix_question = None
        for question in self.survey.questions:
            if question.question_name == mapping.question_name:
                matrix_question = question
                break

        if matrix_question and hasattr(matrix_question, "question_items"):
            for i, col_idx in enumerate(mapping.column_indices):
                if i < len(matrix_question.question_items) and col_idx < len(
                    self.columns
                ):
                    item_name = matrix_question.question_items[i]
                    value = self.columns[col_idx].values[respondent_idx]
                    if value is not None:
                        try:
                            if (
                                str(value)
                                .strip()
                                .replace(".", "")
                                .replace("-", "")
                                .isdigit()
                            ):
                                value = int(float(str(value).strip()))
                            else:
                                value = str(value).strip()
                        except:
                            value = str(value) if value else None
                        matrix_answer[item_name] = value
        else:
            # Fallback: create a list of values
            for col_idx in mapping.column_indices:
                if col_idx < len(self.columns):
                    value = self.columns[col_idx].values[respondent_idx]
                    matrix_answer[str(col_idx)] = str(value) if value else None

        return matrix_answer

    def _extract_checkbox_response(
        self, mapping: QuestionMapping, respondent_idx: int
    ) -> List[str]:
        """Extract a checkbox question response.

        Args:
            mapping: The question mapping
            respondent_idx: Index of the respondent

        Returns:
            List of selected option names
        """
        selected = []
        for col_idx in mapping.column_indices:
            if col_idx < len(self.columns):
                value = self.columns[col_idx].values[respondent_idx]
                if value and str(value).strip() not in ["", "0", "false", "no"]:
                    meta = self.metadata_columns[col_idx]
                    option_name = meta.subpart or meta.short_label
                    selected.append(option_name)
        return selected

    def _extract_single_response(
        self, mapping: QuestionMapping, respondent_idx: int
    ) -> Optional[str]:
        """Extract a single-value question response.

        Args:
            mapping: The question mapping
            respondent_idx: Index of the respondent

        Returns:
            The response value or None
        """
        if mapping.column_indices:
            col_idx = mapping.column_indices[0]
            if col_idx < len(self.columns):
                value = self.columns[col_idx].values[respondent_idx]
                return str(value) if value else None
        return None

    @property
    def question_mappings(self) -> List[QuestionMapping]:
        """Get the question mappings."""
        return self._question_mappings
