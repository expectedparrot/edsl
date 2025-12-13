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
                from edsl.questions import QuestionLinearScale, QuestionYesNo, QuestionLikertFive, QuestionFreeText

                type_classes = {
                    'linear_scale': QuestionLinearScale,
                    'yes_no': QuestionYesNo,
                    'likert_five': QuestionLikertFive,
                    'free_text': QuestionFreeText
                }

                if suggested_type in type_classes:
                    question_class = type_classes[suggested_type]
                    improved_question = question_class.from_dict(question_dict)
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