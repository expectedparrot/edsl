"""Matrix question detection and reconstruction for Qualtrics CSV imports."""

import re
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
from dataclasses import dataclass

from edsl.questions import QuestionMatrix, QuestionMatrixEntry
from .data_classes import QualtricsQuestionMetadata, Column


@dataclass
class MatrixGroup:
    """Represents a detected matrix question group."""
    base_question_id: str  # e.g., "Q20"
    columns: List[Column]  # All columns belonging to this matrix
    row_labels: List[str]  # Row labels extracted from question text
    column_labels: List[str]  # Column labels extracted from question text
    question_text: str  # Base question text (common part)


class MatrixDetector:
    """Detects and reconstructs matrix questions from Qualtrics CSV format."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def detect_matrix_groups(self, columns: List[Column]) -> Tuple[List[MatrixGroup], List[Column]]:
        """
        Detect matrix question groups from column metadata.

        Args:
            columns: List of all columns from CSV

        Returns:
            Tuple of (matrix_groups, remaining_non_matrix_columns)
        """
        matrix_candidates = defaultdict(list)
        non_matrix_columns = []

        if self.verbose:
            print(f"\n🔍 MATRIX DETECTION: Analyzing {len(columns)} columns for matrix patterns")
            print("="*60)

        # Group columns by potential matrix base ID
        for column in columns:
            metadata = column.question_metadata
            if not metadata:
                non_matrix_columns.append(column)
                continue

            # Check for matrix pattern: Q##_# or Q##_##
            base_id = self._extract_matrix_base_id(metadata.short_label)
            if base_id:
                matrix_candidates[base_id].append(column)
                if self.verbose:
                    print(f"  📊 {metadata.short_label} → Matrix group '{base_id}'")
            else:
                non_matrix_columns.append(column)
                if self.verbose:
                    print(f"  📄 {metadata.short_label} → Individual question")

        if self.verbose:
            print(f"\n📋 GROUPING RESULTS:")
            print(f"  Matrix candidates: {len(matrix_candidates)} groups")
            print(f"  Individual questions: {len(non_matrix_columns)} columns")

            for base_id, group_columns in matrix_candidates.items():
                column_names = [col.question_metadata.short_label for col in group_columns]
                print(f"    {base_id}: {column_names} ({len(group_columns)} columns)")
            print()

        # Build individual matrix groups first
        individual_matrices = []

        if self.verbose:
            print(f"🔨 MATRIX RECONSTRUCTION: Building matrices from candidates")
            print("-"*60)

        for base_id, group_columns in matrix_candidates.items():
            if len(group_columns) > 1:
                if self.verbose:
                    print(f"  🔧 Reconstructing '{base_id}' from {len(group_columns)} columns...")

                # This is a real matrix - reconstruct it
                matrix_group = self._reconstruct_matrix_group(base_id, group_columns)
                if matrix_group:
                    individual_matrices.append(matrix_group)
                    if self.verbose:
                        print(f"    ✅ Created matrix: {base_id}")
                        print(f"       Rows: {matrix_group.row_labels}")
                        print(f"       Columns: {matrix_group.column_labels}")
                        print(f"       Text: {matrix_group.question_text[:80]}...")
                else:
                    # Failed to reconstruct - treat as individual questions
                    non_matrix_columns.extend(group_columns)
                    if self.verbose:
                        print(f"    ❌ Failed to reconstruct '{base_id}' - treating as individual questions")
            else:
                # Single column - not a matrix
                non_matrix_columns.extend(group_columns)
                if self.verbose:
                    print(f"  📄 '{base_id}' has only 1 column - treating as individual question")

        # Now detect cross-matrix combinations (e.g., Q20+Q21)
        if self.verbose:
            print(f"\n🔗 MATRIX COMBINATION: Looking for combinable matrices")
            print("-"*60)
            print(f"  Individual matrices found: {len(individual_matrices)}")
            for matrix in individual_matrices:
                print(f"    {matrix.base_question_id}: {len(matrix.columns)} columns, {len(matrix.row_labels)} rows")

        combined_matrices = self._detect_combinable_matrices(individual_matrices)

        # Add any matrices that weren't combined to the final list
        final_matrices = combined_matrices.copy()
        for matrix in individual_matrices:
            if not any(matrix.base_question_id in combined.base_question_id for combined in combined_matrices):
                final_matrices.append(matrix)

        if self.verbose:
            print(f"\n📊 FINAL MATRIX SUMMARY:")
            print("="*60)
            print(f"  Final matrices: {len(final_matrices)}")
            print(f"  Individual questions: {len(non_matrix_columns)}")

            for i, matrix in enumerate(final_matrices, 1):
                print(f"  {i}. {matrix.base_question_id}:")
                print(f"     Type: {'Combined' if '_' in matrix.base_question_id else 'Individual'}")
                print(f"     Rows: {matrix.row_labels}")
                print(f"     Columns: {matrix.column_labels}")
                print(f"     Question: {matrix.question_text[:60]}...")
            print()

        return final_matrices, non_matrix_columns

    def _detect_combinable_matrices(self, matrices: List[MatrixGroup]) -> List[MatrixGroup]:
        """
        Detect matrices that should be combined into a single multi-row matrix.

        Examples:
        - Q20 (3 months) + Q21 (5 years) = Time period matrix
        - Q17 (trust) + Q18 (satisfaction) = Evaluation matrix
        """
        if len(matrices) < 2:
            return []

        combined_matrices = []
        used_matrices = set()

        for i, matrix1 in enumerate(matrices):
            if matrix1.base_question_id in used_matrices:
                continue

            # Look for matrices that can be combined with this one
            combinable_group = [matrix1]

            if self.verbose:
                print(f"  🔍 Checking combinations for '{matrix1.base_question_id}':")

            for j, matrix2 in enumerate(matrices):
                if j <= i or matrix2.base_question_id in used_matrices:
                    continue

                if self.verbose:
                    print(f"    Comparing with '{matrix2.base_question_id}'...")

                if self._can_combine_matrices(matrix1, matrix2):
                    combinable_group.append(matrix2)
                    if self.verbose:
                        print(f"      ✅ Compatible - can combine")
                else:
                    if self.verbose:
                        print(f"      ❌ Not compatible")

            # If we found matrices to combine, create a combined matrix
            if len(combinable_group) > 1:
                if self.verbose:
                    question_ids = [m.base_question_id for m in combinable_group]
                    print(f"  🔗 Creating combination: {' + '.join(question_ids)}")

                combined_matrix = self._combine_matrices(combinable_group)
                if combined_matrix:
                    combined_matrices.append(combined_matrix)
                    for matrix in combinable_group:
                        used_matrices.add(matrix.base_question_id)

                    if self.verbose:
                        print(f"    ✅ Combined into: {combined_matrix.base_question_id}")
                        print(f"       New rows: {combined_matrix.row_labels}")
            elif self.verbose:
                print(f"  📄 '{matrix1.base_question_id}' will remain individual")

        return combined_matrices

    def _can_combine_matrices(self, matrix1: MatrixGroup, matrix2: MatrixGroup) -> bool:
        """Check if two matrices can be combined into one."""
        # The key insight: if they have identical column structures, they should be combined
        # This handles Q20+Q21 (same 3 AI categories) and Q17+Q18 (same 3 freelancer types)

        if len(matrix1.column_labels) != len(matrix2.column_labels):
            if self.verbose:
                print(f"        Different column counts: {len(matrix1.column_labels)} vs {len(matrix2.column_labels)}")
            return False

        # Normalize column labels for comparison (handle case differences and whitespace)
        cols1 = [label.lower().strip() for label in matrix1.column_labels]
        cols2 = [label.lower().strip() for label in matrix2.column_labels]

        # If column structures are identical, they should be combined
        compatible = cols1 == cols2

        if self.verbose:
            if compatible:
                print(f"        Column structures match:")
                for i, (c1, c2) in enumerate(zip(matrix1.column_labels, matrix2.column_labels)):
                    print(f"          {i+1}. '{c1}' ≈ '{c2}'")
            else:
                print(f"        Column structures differ:")
                for i, (c1, c2) in enumerate(zip(matrix1.column_labels, matrix2.column_labels)):
                    match_status = "✓" if c1.lower().strip() == c2.lower().strip() else "✗"
                    print(f"          {i+1}. {match_status} '{c1}' vs '{c2}'")

        return compatible

    def _combine_matrices(self, matrices: List[MatrixGroup]) -> Optional[MatrixGroup]:
        """Combine multiple single-row matrices into one multi-row matrix."""
        if not matrices:
            return None

        # Sort matrices by question number for consistent ordering
        def extract_number(question_id: str) -> int:
            match = re.search(r'Q(\d+)', question_id)
            return int(match.group(1)) if match else 0

        sorted_matrices = sorted(matrices, key=lambda m: extract_number(m.base_question_id))

        # Create combined matrix
        first_matrix = sorted_matrices[0]
        question_ids = [m.base_question_id for m in sorted_matrices]

        # Create combined question name (e.g., "Q20_Q21" or "Q20-21")
        if len(question_ids) == 2:
            combined_name = f"{question_ids[0]}_{question_ids[1]}"
        else:
            combined_name = "_".join(question_ids)

        # Combine all row labels from individual matrices
        combined_row_labels = []
        all_columns = []

        for matrix in sorted_matrices:
            combined_row_labels.extend(matrix.row_labels)
            all_columns.extend(matrix.columns)

        # Use the first matrix's column labels (they should be identical)
        column_labels = first_matrix.column_labels

        # Create a combined question text
        combined_text = self._create_combined_question_text(sorted_matrices)

        return MatrixGroup(
            base_question_id=combined_name,
            columns=all_columns,
            row_labels=combined_row_labels,
            column_labels=column_labels,
            question_text=combined_text
        )

    def _create_combined_question_text(self, matrices: List[MatrixGroup]) -> str:
        """Create a combined question text from multiple matrices."""
        if not matrices:
            return ""

        # Use the first matrix's question text as the base, but remove time-specific details
        # since the time periods will be captured in the row labels
        base_text = matrices[0].question_text

        # Clean up common patterns that make the text specific to one time period
        base_text = re.sub(r'And looking ahead to the next \d+ months?,', '', base_text, flags=re.IGNORECASE)
        base_text = re.sub(r'And lastly, looking ahead to the next \d+ years?,', '', base_text, flags=re.IGNORECASE)
        base_text = re.sub(r'Overall,', '', base_text, flags=re.IGNORECASE)
        base_text = re.sub(r'And how', 'How', base_text, flags=re.IGNORECASE)

        # Clean up extra whitespace
        base_text = re.sub(r'\s+', ' ', base_text).strip()

        return base_text

    def _extract_matrix_base_id(self, question_id: str) -> Optional[str]:
        """Extract base question ID from matrix column ID."""
        # Patterns to match: Q20_1, Q20_2, Q21_1, Q17_1, etc.
        pattern = r'^(Q\d+)_\d+$'
        match = re.match(pattern, question_id)
        return match.group(1) if match else None

    def _reconstruct_matrix_group(self, base_id: str, columns: List[Column]) -> Optional[MatrixGroup]:
        """Reconstruct a matrix group from its component columns."""
        if not columns:
            return None

        # Sort columns by their suffix number
        sorted_columns = sorted(columns, key=lambda c: self._get_column_suffix(c.question_metadata.short_label))

        # Extract common question text and row/column labels
        question_text = self._extract_common_question_text(sorted_columns)
        row_labels = self._extract_row_labels(sorted_columns)
        column_labels = self._extract_column_labels(sorted_columns)

        if not question_text:
            return None

        return MatrixGroup(
            base_question_id=base_id,
            columns=sorted_columns,
            row_labels=row_labels,
            column_labels=column_labels,
            question_text=question_text
        )

    def _get_column_suffix(self, question_id: str) -> int:
        """Extract the numeric suffix from a matrix column ID."""
        match = re.search(r'_(\d+)$', question_id)
        return int(match.group(1)) if match else 0

    def _extract_common_question_text(self, columns: List[Column]) -> str:
        """Extract the common part of question text from matrix columns."""
        if not columns:
            return ""

        # Get all question texts
        texts = [col.question_metadata.question_text for col in columns if col.question_metadata]
        if not texts:
            return ""

        # For matrix questions, the text often contains the column-specific part at the end
        # We'll take the first text and remove the column-specific suffix
        base_text = texts[0]

        # Common patterns to remove from the end:
        # " - Only humans without generative AI "
        # " - Humans with the help of generative AI "
        # " - Only by generative AI"
        suffixes_to_remove = [
            r'\s*-\s*Only humans without generative AI\s*$',
            r'\s*-\s*Humans with the help of generative AI\s*$',
            r'\s*-\s*Only by generative AI\s*$',
            r'\s*-\s*[^-]+\s*$'  # Generic "- something" at the end
        ]

        for pattern in suffixes_to_remove:
            base_text = re.sub(pattern, '', base_text, flags=re.IGNORECASE)

        return base_text.strip()

    def _extract_row_labels(self, columns: List[Column]) -> List[str]:
        """Extract row labels from matrix question texts."""
        # For matrix columns like Q20_1, Q20_2, Q20_3, there's only ONE row per matrix
        # The row label should be extracted from the unique base question text

        if not columns:
            return []

        # Get the first column's text to extract the row label
        first_column = columns[0]
        if not first_column.question_metadata:
            return ['Row 1']

        text = first_column.question_metadata.question_text.lower()

        # Detect time period patterns for our specific case
        if 'next 3 months' in text:
            return ['Next 3 months']
        elif 'next 5 years' in text or 'lastly' in text:
            return ['Next 5 years']
        elif 'overall' in text and 'trust' in text:
            return ['Trust level']
        elif 'satisfied' in text:
            return ['Satisfaction level']
        else:
            # Extract a meaningful row label from the question text
            # Remove common prefixes and suffixes
            clean_text = first_column.question_metadata.question_text.strip()
            clean_text = re.sub(r'\s*-\s*[^-]+\s*$', '', clean_text)  # Remove "- column suffix"

            # Take first few words as row label
            words = clean_text.split()[:4]  # First 4 words
            if words:
                return [' '.join(words).rstrip(':,.')]
            else:
                return ['Row 1']

    def _extract_column_labels(self, columns: List[Column]) -> List[str]:
        """Extract column labels from matrix question texts."""
        column_labels = []

        for column in columns:
            if not column.question_metadata:
                continue

            text = column.question_metadata.question_text
            if self.verbose:
                print(f"  Extracting label from: {repr(text[:100])}")

            # Extract the part after the last " - "
            match = re.search(r'\s*-\s*([^-]+)\s*$', text)
            if match:
                label = match.group(1).strip()
                # Clean up common artifacts like trailing spaces and encoding issues
                label = re.sub(r'\s+$', '', label)  # Remove trailing whitespace
                # Keep "Only" prefix as it's part of the meaning

                if self.verbose:
                    print(f"    Extracted label: {repr(label)}")
                column_labels.append(label)
            else:
                # This should never happen! Log the failure and try alternative parsing
                if self.verbose:
                    print(f"    ❌ Failed to extract label with regex from: {repr(text)}")

                # Try alternative patterns for edge cases
                # Look for text after colon and dash pattern
                alt_match = re.search(r':\s*-\s*(.+)$', text)
                if alt_match:
                    label = alt_match.group(1).strip()
                    if self.verbose:
                        print(f"    ✅ Alternative extraction: {repr(label)}")
                    column_labels.append(label)
                else:
                    # Only use generic fallback as absolute last resort and warn about it
                    suffix = self._get_column_suffix(column.question_metadata.short_label)
                    fallback_label = f'Option {suffix}'
                    print(f"❌ WARNING: Using generic label '{fallback_label}' for column {column.question_metadata.short_label}")
                    print(f"    Question text was: {repr(text[:200])}")
                    column_labels.append(fallback_label)

        return column_labels

    def create_matrix_question(self, matrix_group: MatrixGroup):
        """Create a QuestionMatrix or QuestionMatrixEntry object from a detected matrix group."""
        # Clean up the question text (remove encoding artifacts)
        cleaned_text = self._clean_question_text(matrix_group.question_text)

        # For single-concept matrices (like Q17 trust ratings), we don't need multiple rows
        # The scenarios themselves become the question_items
        if len(matrix_group.row_labels) == 1 and len(matrix_group.column_labels) >= 2:
            if self.verbose:
                print(f"    Detected single-concept matrix - using scenarios as items directly")
        elif len(matrix_group.row_labels) < 2:
            raise ValueError(f"Matrix {matrix_group.base_question_id} has only {len(matrix_group.row_labels)} row(s). Matrix questions require at least 2 rows. Consider treating as individual questions instead.")

        # Decide between QuestionMatrix (choice-based) vs QuestionMatrixEntry (rating-based)
        if self._should_use_matrix_entry(matrix_group):
            return self._create_matrix_entry(matrix_group, cleaned_text)
        else:
            return self._create_standard_matrix(matrix_group, cleaned_text)

    def _should_use_matrix_entry(self, matrix_group: MatrixGroup) -> bool:
        """
        Determine if this should be a QuestionMatrixEntry (rating) vs QuestionMatrix (choice).

        This analyzes the actual response data to detect if users provided numeric ratings
        rather than categorical choices.
        """
        # Analyze response data from the first few columns to detect scale patterns
        numeric_responses = []
        total_responses = 0

        for column in matrix_group.columns[:3]:  # Check first 3 columns
            if not hasattr(column, 'values'):
                continue

            for value in column.values:
                if value is not None and str(value).strip():
                    total_responses += 1
                    try:
                        # Try to parse as number
                        num_val = float(str(value).strip())
                        numeric_responses.append(num_val)
                    except:
                        # Check if it's a labeled endpoint like "Not at all - 1" or "Very Much - 7"
                        val_str = str(value).strip()
                        if ' - ' in val_str:
                            try:
                                # Extract number from "label - number" format
                                number_part = val_str.split(' - ')[-1]
                                num_val = float(number_part)
                                numeric_responses.append(num_val)
                            except:
                                pass

        if total_responses == 0:
            # Fallback to keyword analysis if no response data
            return self._keyword_based_matrix_entry_detection(matrix_group)

        # If 70%+ of responses are numeric, it's likely a rating scale
        numeric_ratio = len(numeric_responses) / total_responses

        if self.verbose:
            print(f"    Response analysis: {len(numeric_responses)}/{total_responses} ({numeric_ratio:.1%}) are numeric")
            if numeric_responses:
                min_val, max_val = min(numeric_responses), max(numeric_responses)
                print(f"    Detected scale range: {min_val} to {max_val}")

        return numeric_ratio >= 0.7  # 70% threshold for rating scales

    def _keyword_based_matrix_entry_detection(self, matrix_group: MatrixGroup) -> bool:
        """Fallback keyword-based detection when no response data is available."""
        # Check for rating/evaluation keywords in row labels
        rating_keywords = ['trust', 'satisfaction', 'level', 'rate', 'score', 'evaluation']
        text_lower = matrix_group.question_text.lower()

        # Look for rating-related terms in question text or row labels
        for keyword in rating_keywords:
            if keyword in text_lower:
                return True
            for row_label in matrix_group.row_labels:
                if keyword in row_label.lower():
                    return True

        # Check if column labels look like scenarios to rate rather than choices
        # Long descriptive column labels suggest rating scenarios
        avg_column_length = sum(len(col) for col in matrix_group.column_labels) / len(matrix_group.column_labels)
        if avg_column_length > 30:  # Long descriptive columns suggest rating scenarios
            return True

        # Check for specific patterns that suggest rating
        for col in matrix_group.column_labels:
            col_lower = col.lower()
            # Look for scenario descriptions
            if any(phrase in col_lower for phrase in ['freelancer who', 'person who', 'scenario where']):
                return True

        # Default to standard matrix for choice-based questions
        return False

    def _detect_scale_range(self, matrix_group: MatrixGroup) -> tuple[int, int]:
        """
        Detect the min and max values of the rating scale from response data.

        Returns:
            Tuple of (min_value, max_value)
        """
        numeric_values = []

        # Analyze all columns to find the full range
        for column in matrix_group.columns:
            if not hasattr(column, 'values'):
                continue

            for value in column.values:
                if value is not None and str(value).strip():
                    try:
                        # Try to parse as number
                        num_val = float(str(value).strip())
                        if num_val.is_integer():
                            numeric_values.append(int(num_val))
                        else:
                            numeric_values.append(num_val)
                    except:
                        # Check if it's a labeled endpoint like "Not at all - 1" or "Very Much - 7"
                        val_str = str(value).strip()
                        if ' - ' in val_str:
                            try:
                                # Extract number from "label - number" format
                                number_part = val_str.split(' - ')[-1]
                                num_val = float(number_part)
                                if num_val.is_integer():
                                    numeric_values.append(int(num_val))
                                else:
                                    numeric_values.append(num_val)
                            except:
                                pass

        if not numeric_values:
            # Fallback to default 1-7 scale
            return (1, 7)

        min_val = min(numeric_values)
        max_val = max(numeric_values)

        # Handle common scale patterns
        if min_val >= 0 and max_val <= 10 and len(set(numeric_values)) <= 11:
            # Likely a 0-10 or 1-10 scale
            return (int(min_val), int(max_val))
        elif min_val >= 0 and max_val <= 100 and max(numeric_values) > 10:
            # Likely a percentage scale (0-100)
            return (0, 100)
        elif min_val >= 1 and max_val <= 7:
            # Common 1-7 Likert scale
            return (1, 7)
        elif min_val >= 1 and max_val <= 5:
            # Common 1-5 Likert scale
            return (1, 5)
        else:
            # Use actual min/max for unusual scales
            return (int(min_val), int(max_val))

    def _extract_scale_and_labels(self, matrix_group: MatrixGroup) -> tuple[list[int], dict[int, str]]:
        """
        Extract the rating scale numbers and endpoint labels from response data.

        Returns:
            Tuple of (scale_options, option_labels)
            e.g. ([1,2,3,4,5,6,7], {1: "Not at all", 7: "Very much"})
        """
        numeric_values = []
        label_map = {}

        # Analyze response data to find scale values and labels
        for column in matrix_group.columns:
            if not hasattr(column, 'values'):
                continue

            for value in column.values:
                if value is not None and str(value).strip():
                    val_str = str(value).strip()

                    # Check for labeled endpoints like "Not at all- 1" or "Very Much - 7"
                    # Handle both "label- number" and "label - number" formats
                    if ' - ' in val_str or '- ' in val_str:
                        try:
                            # Try "label - number" first (with spaces)
                            if ' - ' in val_str:
                                label_part, number_part = val_str.rsplit(' - ', 1)
                            else:
                                # Try "label- number" (no space before hyphen)
                                label_part, number_part = val_str.rsplit('- ', 1)

                            num_val = int(float(number_part))
                            label_map[num_val] = label_part.strip()
                            numeric_values.append(num_val)
                        except:
                            pass
                    else:
                        # Try to parse as plain number
                        try:
                            num_val = int(float(val_str))
                            numeric_values.append(num_val)
                        except:
                            pass

        if not numeric_values:
            # Fallback to default 1-7 scale
            return ([1, 2, 3, 4, 5, 6, 7], {})

        min_val = min(numeric_values)
        max_val = max(numeric_values)

        # If we have labeled endpoints, ensure we include the full labeled range
        if label_map:
            # Extend range to include all labeled values
            labeled_values = list(label_map.keys())
            min_val = min(min_val, min(labeled_values))
            max_val = max(max_val, max(labeled_values))

        # Create complete scale range
        scale_options = list(range(min_val, max_val + 1))

        if self.verbose and label_map:
            print(f"    Extracted scale labels: {label_map}")

        return (scale_options, label_map)

    def _create_matrix_entry(self, matrix_group: MatrixGroup, cleaned_text: str) -> QuestionMatrix:
        """Create a QuestionMatrix for rating-based matrices with proper EDSL structure."""
        # For EDSL QuestionMatrix, the structure should be:
        # - question_items = the scenarios being rated (what we called column_labels)
        # - question_options = the rating scale numbers [1,2,3,4,5,6,7]
        # - option_labels = scale endpoint labels {1: "Not at all", 7: "Very much"}

        scale_options, option_labels = self._extract_scale_and_labels(matrix_group)

        if self.verbose:
            print(f"    Creating QuestionMatrix with {len(matrix_group.column_labels)} items and scale {scale_options}")

        # For single-concept matrices (like Q17), use scenarios as items directly
        # For multi-concept matrices (like Q17+Q18), we need to handle differently
        if len(matrix_group.row_labels) == 1:
            # Single concept matrix: scenarios are the items to rate
            question_items = matrix_group.column_labels
        else:
            # Multi-concept matrix: row labels are what we're rating, scenarios are rated multiple times
            # This case needs more complex handling - for now, use scenarios as items
            question_items = matrix_group.column_labels

        # Correct EDSL structure: scenarios as items, scale as options
        return QuestionMatrix(
            question_name=matrix_group.base_question_id,
            question_text=cleaned_text,
            question_items=question_items,  # Scenarios being rated
            question_options=scale_options,  # Rating scale numbers
            option_labels=option_labels,  # Scale endpoint labels
        )

    def _create_standard_matrix(self, matrix_group: MatrixGroup, cleaned_text: str) -> QuestionMatrix:
        """Create a standard QuestionMatrix for choice-based matrices."""
        return QuestionMatrix(
            question_name=matrix_group.base_question_id,
            question_text=cleaned_text,
            question_items=matrix_group.row_labels,
            question_options=matrix_group.column_labels
        )

    def _clean_question_text(self, text: str) -> str:
        """Clean up question text by removing encoding artifacts and formatting issues."""
        if not text:
            return text

        # Fix common encoding issues
        cleaned = text.replace('â€¦', '...')  # Fix ellipsis encoding
        cleaned = cleaned.replace('â€™', "'")  # Fix apostrophe encoding
        cleaned = cleaned.replace('â€œ', '"')  # Fix opening quote
        cleaned = cleaned.replace('â€', '"')   # Fix closing quote

        # Remove extra whitespace and newlines
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)  # Collapse multiple newlines
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Collapse multiple spaces

        return cleaned.strip()