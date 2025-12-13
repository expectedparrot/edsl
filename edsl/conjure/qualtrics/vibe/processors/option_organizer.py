"""
Option organization processor for sorting and cleaning question options.
"""

import re
from typing import Dict, Any, Optional, List, Union, Tuple
from edsl.questions import Question
from .base_processor import BaseProcessor, ProcessingResult


class OptionOrganizationProcessor(BaseProcessor):
    """Processor that organizes and sorts question options."""

    async def process(self, question: Question, context: Optional[Dict[str, Any]] = None) -> ProcessingResult:
        """
        Process question options for better organization.

        Args:
            question: Question to process
            context: Optional context data

        Returns:
            ProcessingResult with organized options
        """
        if not hasattr(question, 'question_options') or not question.question_options:
            return ProcessingResult(
                question=question,
                changed=False,
                changes=[],
                confidence=1.0,
                reasoning="No options to organize"
            )

        original_options = list(question.question_options)
        organized_options = self._organize_options(original_options, question.question_text)

        if organized_options != original_options:
            self.log(f"Reordered options from {len(original_options)} items")

            # Create new question with organized options
            question_dict = question.to_dict()
            question_dict['question_options'] = organized_options

            # Preserve option_labels mapping if it exists
            if hasattr(question, 'option_labels') and question.option_labels:
                question_dict['option_labels'] = question.option_labels

            # Create question from dict using the appropriate class
            question_class = type(question)
            improved_question = question_class.from_dict(question_dict)

            return ProcessingResult(
                question=improved_question,
                changed=True,
                changes=[{
                    'type': 'options_reordered',
                    'original': original_options,
                    'new': organized_options,
                    'count': len(organized_options)
                }],
                confidence=0.9,
                reasoning=f"Reordered {len(organized_options)} options for better logical sequence"
            )

        return ProcessingResult(
            question=question,
            changed=False,
            changes=[],
            confidence=1.0,
            reasoning="Options already in good order"
        )

    def _organize_options(self, options: List[Union[str, int, float]], question_text: str) -> List[Union[str, int, float]]:
        """
        Organize options in a logical order.

        Args:
            options: List of option values
            question_text: Question text for context

        Returns:
            List of options in better order
        """
        # Handle numeric ranges (like employee counts, age ranges, etc.)
        if self._looks_like_numeric_ranges(options):
            return self._sort_numeric_ranges(options)

        # Handle frequency/agreement scales
        if self._looks_like_frequency_scale(options):
            return self._sort_frequency_scale(options)

        # Handle likert scales
        if self._looks_like_likert_scale(options):
            return self._sort_likert_scale(options)

        # Handle time periods
        if self._looks_like_time_periods(options):
            return self._sort_time_periods(options)

        # Handle yes/no/unsure patterns
        if self._looks_like_yes_no_pattern(options):
            return self._sort_yes_no_pattern(options)

        # If we can't determine a pattern, return original order
        return options

    def _looks_like_numeric_ranges(self, options: List[Union[str, int, float]]) -> bool:
        """Check if options look like numeric ranges (e.g., '1-5', '10-20', '1 employee')."""
        range_count = 0
        for opt in options:
            if isinstance(opt, str):
                # Look for patterns like "1-5", "10-20", "1 employee", "2-9 employees"
                if re.search(r'\d+[-–]\d+|\d+\s*(employee|person|year|dollar)', opt, re.IGNORECASE):
                    range_count += 1
                # Also count single numbers with units
                elif re.search(r'^\d+\s*(employee|person|year|dollar)', opt, re.IGNORECASE):
                    range_count += 1

        # Consider it numeric ranges if 50%+ options match the pattern
        return range_count / len(options) >= 0.5

    def _sort_numeric_ranges(self, options: List[Union[str, int, float]]) -> List[Union[str, int, float]]:
        """Sort numeric range options."""
        def extract_range_start(option: Union[str, int, float]) -> float:
            """Extract the starting number from a range option."""
            if isinstance(option, (int, float)):
                return float(option)

            option_str = str(option).strip()

            # Handle special cases first
            if re.search(r'(don\'t know|unknown|other|none)', option_str, re.IGNORECASE):
                return float('inf')  # Put these at the end

            if re.search(r'(more than|over|\+)', option_str, re.IGNORECASE):
                # Extract number after "more than" or "over"
                match = re.search(r'(\d+(?:,\d+)*)', option_str)
                if match:
                    return float(match.group(1).replace(',', '')) + 0.1  # Slightly higher than the number
                return float('inf')

            # Look for range patterns like "1-5", "10-20", "1,000-3,000"
            range_match = re.search(r'(\d+(?:,\d+)*)[-–](\d+(?:,\d+)*)', option_str)
            if range_match:
                start = float(range_match.group(1).replace(',', ''))
                return start

            # Look for single numbers like "1 employee", "50 years"
            single_match = re.search(r'(\d+(?:,\d+)*)', option_str)
            if single_match:
                return float(single_match.group(1).replace(',', ''))

            # If no number found, put at beginning
            return -1.0

        # Sort by extracted range start, preserving relative order for equal values
        return sorted(options, key=lambda x: (extract_range_start(x), options.index(x)))

    def _looks_like_frequency_scale(self, options: List[Union[str, int, float]]) -> bool:
        """Check if options look like frequency scales."""
        frequency_patterns = [
            'never', 'rarely', 'sometimes', 'often', 'always',
            'daily', 'weekly', 'monthly', 'yearly',
            'very often', 'very rarely'
        ]

        matches = 0
        for opt in options:
            if isinstance(opt, str):
                opt_lower = opt.lower()
                if any(pattern in opt_lower for pattern in frequency_patterns):
                    matches += 1

        return matches / len(options) >= 0.4

    def _sort_frequency_scale(self, options: List[Union[str, int, float]]) -> List[Union[str, int, float]]:
        """Sort frequency scale options."""
        frequency_order = [
            'never', 'rarely', 'very rarely', 'seldom', 'infrequently',
            'sometimes', 'occasionally', 'moderately',
            'often', 'frequently', 'very often', 'usually',
            'always', 'constantly',
            'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        ]

        def frequency_score(option: Union[str, int, float]) -> int:
            if isinstance(option, str):
                opt_lower = option.lower()
                for i, freq in enumerate(frequency_order):
                    if freq in opt_lower:
                        return i
            return 999  # Unknown items go to end

        return sorted(options, key=frequency_score)

    def _looks_like_likert_scale(self, options: List[Union[str, int, float]]) -> bool:
        """Check if options look like Likert scale."""
        likert_patterns = [
            'strongly disagree', 'disagree', 'neutral', 'agree', 'strongly agree',
            'very satisfied', 'satisfied', 'dissatisfied', 'very dissatisfied',
            'excellent', 'good', 'fair', 'poor'
        ]

        matches = 0
        for opt in options:
            if isinstance(opt, str):
                opt_lower = opt.lower()
                if any(pattern in opt_lower for pattern in likert_patterns):
                    matches += 1

        return matches / len(options) >= 0.4

    def _sort_likert_scale(self, options: List[Union[str, int, float]]) -> List[Union[str, int, float]]:
        """Sort Likert scale options."""
        # Negative to positive order
        likert_order = [
            'strongly disagree', 'disagree', 'somewhat disagree',
            'neutral', 'neither', 'undecided',
            'somewhat agree', 'agree', 'strongly agree',
            'very dissatisfied', 'dissatisfied', 'satisfied', 'very satisfied',
            'poor', 'fair', 'good', 'excellent'
        ]

        def likert_score(option: Union[str, int, float]) -> int:
            if isinstance(option, str):
                opt_lower = option.lower()
                for i, likert in enumerate(likert_order):
                    if likert in opt_lower:
                        return i
            return 999

        return sorted(options, key=likert_score)

    def _looks_like_time_periods(self, options: List[Union[str, int, float]]) -> bool:
        """Check if options look like time periods."""
        time_patterns = [
            'hour', 'day', 'week', 'month', 'year',
            'morning', 'afternoon', 'evening', 'night',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
        ]

        matches = 0
        for opt in options:
            if isinstance(opt, str):
                opt_lower = opt.lower()
                if any(pattern in opt_lower for pattern in time_patterns):
                    matches += 1

        return matches / len(options) >= 0.4

    def _sort_time_periods(self, options: List[Union[str, int, float]]) -> List[Union[str, int, float]]:
        """Sort time period options."""
        # This is simplified - could be more sophisticated
        time_order = [
            'hour', 'day', 'week', 'month', 'year',
            'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
            'morning', 'afternoon', 'evening', 'night'
        ]

        def time_score(option: Union[str, int, float]) -> int:
            if isinstance(option, str):
                opt_lower = option.lower()
                for i, time_period in enumerate(time_order):
                    if time_period in opt_lower:
                        return i
            return 999

        return sorted(options, key=time_score)

    def _looks_like_yes_no_pattern(self, options: List[Union[str, int, float]]) -> bool:
        """Check if options follow yes/no/other pattern."""
        yes_no_patterns = ['yes', 'no', 'maybe', 'unsure', "don't know", 'other']

        matches = 0
        for opt in options:
            if isinstance(opt, str):
                opt_lower = opt.lower().strip()
                if any(pattern in opt_lower for pattern in yes_no_patterns):
                    matches += 1

        return matches / len(options) >= 0.6

    def _sort_yes_no_pattern(self, options: List[Union[str, int, float]]) -> List[Union[str, int, float]]:
        """Sort yes/no pattern options."""
        yes_no_order = ['yes', 'no', 'maybe', 'unsure', "don't know", "i don't know", 'other']

        def yes_no_score(option: Union[str, int, float]) -> int:
            if isinstance(option, str):
                opt_lower = option.lower().strip()
                for i, pattern in enumerate(yes_no_order):
                    if pattern == opt_lower or pattern in opt_lower:
                        return i
            return 999

        return sorted(options, key=yes_no_score)