"""
Question type correction processor.
"""

from typing import Dict, Any, Optional, List
from edsl.questions import Question
from .base_processor import BaseProcessor, ProcessingResult


class TypeCorrectionProcessor(BaseProcessor):
    """Processor that corrects question types based on content analysis."""

    async def process(self, question: Question, context: Optional[Dict[str, Any]] = None) -> ProcessingResult:
        """
        Process question for type correction.

        Args:
            question: Question to process
            context: Optional context data (response data, etc.)

        Returns:
            ProcessingResult with corrected question type if needed
        """
        original_type = question.question_type
        suggested_type = self._analyze_question_type(question, context)

        if suggested_type and suggested_type != original_type:
            self.log(f"Type correction: {original_type} → {suggested_type}")

            # Create new question with correct type
            question_dict = question.to_dict()
            question_dict['question_type'] = suggested_type

            try:
                # For type changes, we need to import and use the new question type
                from edsl.questions import QuestionLinearScale, QuestionYesNo, QuestionLikertFive, QuestionFreeText, QuestionNumerical

                type_classes = {
                    'linear_scale': QuestionLinearScale,
                    'yes_no': QuestionYesNo,
                    'likert_five': QuestionLikertFive,
                    'free_text': QuestionFreeText,
                    'numerical': QuestionNumerical
                }

                if suggested_type in type_classes:
                    question_class = type_classes[suggested_type]
                    # Clean up question dict to remove incompatible parameters for the new type
                    clean_question_dict = self._clean_question_dict_for_type(question_dict, suggested_type)
                    improved_question = question_class.from_dict(clean_question_dict)
                else:
                    # Fallback to original type
                    question_class = type(question)
                    improved_question = question_class.from_dict(question_dict)
                return ProcessingResult(
                    question=improved_question,
                    changed=True,
                    changes=[{
                        'type': 'question_type_corrected',
                        'original': original_type,
                        'new': suggested_type
                    }],
                    confidence=0.8,
                    reasoning=f"Corrected question type from {original_type} to {suggested_type} based on content analysis"
                )
            except Exception as e:
                self.log(f"Failed to create question with type {suggested_type}: {e}")

        return ProcessingResult(
            question=question,
            changed=False,
            changes=[],
            confidence=1.0,
            reasoning="Question type is appropriate"
        )

    def _analyze_question_type(self, question: Question, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Analyze question to suggest correct type.

        Args:
            question: Question to analyze
            context: Optional response data

        Returns:
            Suggested question type or None if current type is appropriate
        """
        if not hasattr(question, 'question_options') or not question.question_options:
            return None

        options = question.question_options
        question_text = getattr(question, 'question_text', '').lower()

        # Check for numeric rating scales that should be QuestionLinearScale
        if self._is_numeric_scale(options):
            # Check if it's currently multiple_choice but should be linear_scale
            if question.question_type == 'multiple_choice':
                return 'linear_scale'

        # Check for yes/no questions
        if self._is_yes_no_question(options):
            if question.question_type in ['multiple_choice', 'linear_scale']:
                return 'yes_no'

        # Check for Likert scales
        if self._is_likert_scale(options, question_text):
            if question.question_type == 'multiple_choice':
                return 'likert_five'  # Assuming 5-point scale

        # Check for numerical questions (percentages, monetary amounts, etc.)
        if self._is_numerical_question(question_text, options):
            return 'numerical'

        # Check for free text that was misclassified
        if self._is_free_text_question(question_text, options):
            return 'free_text'

        return None

    def _is_numeric_scale(self, options: List) -> bool:
        """Check if options represent a numeric scale (1-5, 1-10, etc.)."""
        if len(options) < 3:
            return False

        # Check if all options are consecutive integers
        try:
            numeric_options = [int(opt) for opt in options]
            numeric_options.sort()

            # Check if consecutive integers
            if len(numeric_options) >= 3:
                for i in range(1, len(numeric_options)):
                    if numeric_options[i] != numeric_options[i-1] + 1:
                        return False
                return True
        except:
            pass

        return False

    def _is_yes_no_question(self, options: List) -> bool:
        """Check if this is a yes/no question."""
        if len(options) != 2:
            return False

        option_strings = [str(opt).lower().strip() for opt in options]
        yes_no_patterns = [
            ['yes', 'no'],
            ['true', 'false'],
            ['correct', 'incorrect']
        ]

        for pattern in yes_no_patterns:
            if sorted(option_strings) == sorted(pattern):
                return True

        return False

    def _is_likert_scale(self, options: List, question_text: str) -> bool:
        """Check if this is a Likert scale question."""
        if len(options) not in [3, 4, 5, 7]:
            return False

        likert_indicators = [
            'agree', 'disagree', 'strongly', 'somewhat',
            'satisfied', 'dissatisfied', 'likely', 'unlikely'
        ]

        # Check question text for Likert indicators
        text_has_likert = any(indicator in question_text for indicator in likert_indicators)

        # Check options for Likert patterns
        options_str = ' '.join([str(opt).lower() for opt in options])
        options_have_likert = any(indicator in options_str for indicator in likert_indicators)

        return text_has_likert or options_have_likert

    def _is_free_text_question(self, question_text: str, options: List) -> bool:
        """Check if this should be a free text question."""
        free_text_indicators = [
            'explain', 'describe', 'comment', 'please specify',
            'other (please specify)', 'in your own words'
        ]

        return any(indicator in question_text for indicator in free_text_indicators)

    def _is_numerical_question(self, question_text: str, options: List) -> bool:
        """Check if this should be a numerical question."""
        # Check for numerical question indicators in the text
        numerical_indicators = [
            'percentage', 'percent', '%', 'amount', 'dollars', '$',
            'how much', 'how many', 'number of', 'quantity', 'age',
            'income', 'salary', 'price', 'cost', 'value', 'weight',
            'height', 'distance', 'time', 'years', 'months', 'days'
        ]

        text_has_numerical = any(indicator in question_text.lower() for indicator in numerical_indicators)

        # Check if most/all options are numeric
        if not options:
            return text_has_numerical

        numeric_options_count = 0
        for option in options:
            try:
                # Try to convert to float to see if it's numeric
                float(str(option).strip())
                numeric_options_count += 1
            except (ValueError, TypeError):
                pass

        # If more than 75% of options are numeric and we have numerical text indicators
        options_are_mostly_numeric = (numeric_options_count / len(options)) > 0.75

        return text_has_numerical and options_are_mostly_numeric

    def _clean_question_dict_for_type(self, question_dict: Dict[str, Any], target_type: str) -> Dict[str, Any]:
        """
        Clean question dictionary to remove parameters incompatible with target type.

        Args:
            question_dict: Original question dictionary
            target_type: Target question type

        Returns:
            Cleaned dictionary with only compatible parameters
        """
        # Start with a copy of the original dict
        clean_dict = question_dict.copy()

        # Define parameter compatibility for each question type
        valid_params = {
            'free_text': {'question_name', 'question_text', 'answering_instructions', 'question_presentation'},
            'yes_no': {'question_name', 'question_text', 'answering_instructions', 'question_presentation'},
            'linear_scale': {'question_name', 'question_text', 'question_options', 'answering_instructions', 'question_presentation'},
            'likert_five': {'question_name', 'question_text', 'answering_instructions', 'question_presentation'},
            'numerical': {'question_name', 'question_text', 'min_value', 'max_value', 'answering_instructions', 'question_presentation'},
        }

        # Get valid parameters for the target type
        if target_type in valid_params:
            valid_for_type = valid_params[target_type]

            # Remove any parameters that are not valid for this type
            keys_to_remove = []
            for key in clean_dict:
                if key not in valid_for_type and key != 'question_type':  # Always keep question_type
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del clean_dict[key]

        # Special handling for numerical questions - infer min/max from options if available
        if target_type == 'numerical' and 'question_options' in question_dict:
            options = question_dict['question_options']
            numeric_values = []

            for option in options:
                try:
                    numeric_values.append(float(str(option).strip()))
                except (ValueError, TypeError):
                    pass

            if numeric_values:
                clean_dict['min_value'] = min(numeric_values)
                clean_dict['max_value'] = max(numeric_values)

        return clean_dict