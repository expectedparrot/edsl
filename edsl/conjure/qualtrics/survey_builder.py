"""Survey builder for Qualtrics data."""

import re
from collections import defaultdict
from typing import List, Callable

from edsl.surveys import Survey
from edsl.questions import (
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionCheckBox,
    QuestionLinearScale,
)

from .data_classes import QualtricsQuestionMetadata, Column, DataType
from .question_type_detector import QualtricsQuestionTypeDetector
from .matrix_detector import MatrixDetector


class QualtricsSurveyBuilder:
    """Build EDSL Survey from Qualtrics metadata and data.

    Handles:
    - Grouping columns by question
    - Creating appropriate question objects
    - Integrating with MatrixDetector
    - Resolving piping in question text
    """

    def __init__(
        self,
        columns: List[Column],
        metadata_columns: List[QualtricsQuestionMetadata],
        is_metadata_func: Callable[[QualtricsQuestionMetadata], bool],
        resolve_piping_func: Callable[[str], str],
        create_semantic_names: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize the survey builder.

        Args:
            columns: List of data columns
            metadata_columns: List of column metadata
            is_metadata_func: Function to check if a column is metadata
            resolve_piping_func: Function to resolve piping in text
            create_semantic_names: Use semantic names vs index-based names
            verbose: Print detailed processing information
        """
        self.columns = columns
        self.metadata_columns = metadata_columns
        self.is_metadata_func = is_metadata_func
        self.resolve_piping_func = resolve_piping_func
        self.create_semantic_names = create_semantic_names
        self.verbose = verbose

        self.matrix_detector = MatrixDetector(verbose=verbose)
        self.type_detector = QualtricsQuestionTypeDetector(
            columns, is_metadata_func, verbose
        )

    def build(self) -> Survey:
        """Build EDSL Survey from the metadata and data.

        Returns:
            An EDSL Survey object
        """
        if self.verbose:
            print("Building EDSL Survey with matrix detection...")

        # Prepare columns with metadata for matrix detection
        columns_with_metadata = self._prepare_columns_for_matrix_detection()

        # Detect matrix question groups
        matrix_groups, remaining_columns = self.matrix_detector.detect_matrix_groups(
            columns_with_metadata
        )

        # Create all questions with their original position
        all_questions_with_position = []

        # Create matrix questions
        self._add_matrix_questions(
            matrix_groups, remaining_columns, all_questions_with_position
        )

        # Create individual questions from remaining columns
        self._add_individual_questions(remaining_columns, all_questions_with_position)

        # Sort by original column position
        all_questions_with_position.sort(key=lambda x: x[0])
        questions = [question for position, question in all_questions_with_position]

        survey = Survey(questions=questions)

        if self.verbose:
            matrix_count = len(matrix_groups)
            individual_count = len(questions) - matrix_count
            print(
                f"Created survey with {len(questions)} questions "
                f"({matrix_count} matrices, {individual_count} individual)"
            )

        return survey

    def _prepare_columns_for_matrix_detection(self) -> List[Column]:
        """Prepare Column objects with metadata for matrix detection."""
        columns_with_metadata = []
        for meta in self.metadata_columns:
            if not self.is_metadata_func(meta):
                temp_column = self.columns[meta.column_index]
                temp_column.question_metadata = meta
                columns_with_metadata.append(temp_column)
        return columns_with_metadata

    def _add_matrix_questions(
        self,
        matrix_groups,
        remaining_columns: List[Column],
        all_questions_with_position: List,
    ) -> None:
        """Create QuestionMatrix objects for detected matrices."""
        for matrix_group in matrix_groups:
            try:
                matrix_question = self.matrix_detector.create_matrix_question(
                    matrix_group
                )
                matrix_question.question_text = self.resolve_piping_func(
                    matrix_question.question_text
                )

                first_column_index = min(
                    col.question_metadata.column_index for col in matrix_group.columns
                )
                all_questions_with_position.append(
                    (first_column_index, matrix_question)
                )

                if self.verbose:
                    print(
                        f"Created matrix question: {matrix_question.question_name} "
                        f"({len(matrix_group.row_labels)}x{len(matrix_group.column_labels)})"
                    )
                    print(f"  Items (rows): {matrix_group.row_labels}")
                    print(f"  Options (columns): {matrix_group.column_labels}")

            except Exception as e:
                if self.verbose:
                    print(
                        f"Warning: Could not create matrix question "
                        f"{matrix_group.base_question_id}: {e}"
                    )
                # Fallback: treat matrix columns as individual questions
                remaining_columns.extend(matrix_group.columns)

    def _add_individual_questions(
        self,
        remaining_columns: List[Column],
        all_questions_with_position: List,
    ) -> None:
        """Build individual questions from remaining columns."""
        # Group columns by question_name
        question_groups = defaultdict(list)
        for col in remaining_columns:
            if hasattr(col, "question_metadata") and col.question_metadata:
                question_groups[col.question_metadata.question_name].append(
                    col.question_metadata
                )

        for question_name, group in question_groups.items():
            group.sort(key=lambda x: x.column_index)
            first_column_index = group[0].column_index

            question_type = self.type_detector.detect(group)
            question_text = group[0].question_text
            question_text = self.resolve_piping_func(question_text)

            if self.create_semantic_names:
                clean_text = re.sub(r"[^\w\s]", "", question_text)
                semantic_name = "_".join(clean_text.lower().split()[:5])
                if semantic_name:
                    question_name = semantic_name

            question = self._create_question(
                question_name, question_text, question_type, group
            )
            if question:
                all_questions_with_position.append((first_column_index, question))

    def _create_question(
        self,
        question_name: str,
        question_text: str,
        question_type: DataType,
        group: List[QualtricsQuestionMetadata],
    ):
        """Create an EDSL question object based on the detected type."""
        try:
            if question_type == DataType.QUESTION_TEXT:
                return QuestionFreeText(
                    question_name=question_name, question_text=question_text
                )

            elif question_type == DataType.QUESTION_MULTIPLE_CHOICE:
                options = set()
                for meta in group:
                    col_values = self.columns[meta.column_index].values
                    for value in col_values:
                        if value and str(value).strip():
                            options.add(str(value).strip())

                if options:
                    options_list = sorted(list(options))
                    # Handle single-option case (likely consent/agreement questions)
                    if len(options_list) == 1:
                        # Convert to Yes/No question for consent-type questions
                        single_option = options_list[0].lower()
                        if any(
                            keyword in single_option
                            for keyword in [
                                "agree",
                                "consent",
                                "understand",
                                "participant",
                                "participate",
                            ]
                        ):
                            return QuestionMultipleChoice(
                                question_name=question_name,
                                question_text=question_text,
                                question_options=["Yes", "No"],
                            )
                        else:
                            # For other single-option cases, convert to free text
                            return QuestionFreeText(
                                question_name=question_name,
                                question_text=question_text,
                            )
                    else:
                        return QuestionMultipleChoice(
                            question_name=question_name,
                            question_text=question_text,
                            question_options=options_list,
                        )

            elif question_type == DataType.QUESTION_CHECKBOX:
                if len(group) > 1:
                    options = []
                    for meta in group:
                        if meta.subpart:
                            options.append(meta.subpart)
                        else:
                            options.append(meta.short_label)

                    if options:
                        return QuestionCheckBox(
                            question_name=question_name,
                            question_text=question_text,
                            question_options=options,
                        )

            elif question_type == DataType.QUESTION_LINEAR_SCALE:
                all_values = []
                for meta in group:
                    col_values = self.columns[meta.column_index].values
                    for value in col_values:
                        if value and str(value).strip():
                            try:
                                all_values.append(int(float(value)))
                            except (ValueError, TypeError):
                                pass

                if all_values:
                    min_val = min(all_values)
                    max_val = max(all_values)
                    return QuestionLinearScale(
                        question_name=question_name,
                        question_text=question_text,
                        question_options=list(range(min_val, max_val + 1)),
                    )

            return None

        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not create question {question_name}: {e}")
            # Fallback to free text
            return QuestionFreeText(
                question_name=question_name,
                question_text=question_text or f"Question {question_name}",
            )
