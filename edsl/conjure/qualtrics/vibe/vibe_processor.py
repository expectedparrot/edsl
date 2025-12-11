"""
Main vibe processor for AI-powered question cleanup and enhancement.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from edsl import Survey
from edsl.questions import Question
from .question_analyzer import QuestionAnalyzer


@dataclass
class VibeChange:
    """Records a change made by the vibe processor."""
    question_name: str
    change_type: str  # 'text', 'options', 'type'
    original_value: Any
    new_value: Any
    reasoning: str
    confidence: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'question_name': self.question_name,
            'change_type': self.change_type,
            'original_value': self.original_value,
            'new_value': self.new_value,
            'reasoning': self.reasoning,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class VibeConfig:
    """Configuration for vibe processing."""

    enabled: bool = True
    system_prompt: str = """You are analyzing questions converted from Qualtrics CSV exports to identify and fix TECHNICAL conversion errors and misclassifications ONLY.

CRITICAL RULES:
- Do NOT change grammar, spelling, capitalization, or language style
- Do NOT make questions more "professional" or "formal"
- Do NOT fix typos or informal language - these are intentional survey design choices
- ONLY fix technical artifacts from the Qualtrics→CSV→EDSL conversion process
- Preserve the original author's wording, tone, and style completely

TECHNICAL CONVERSION ISSUES TO FIX:
1. HTML tags, entities, or artifacts (e.g., <p>, <b>, &nbsp;, &lt;, &gt;, etc.)
2. Encoding problems (corrupted characters, broken UTF-8, etc.)
3. Question type misclassification due to conversion errors
4. Corrupted or missing option lists from CSV export issues
5. Structural problems from matrix question flattening

VALID EDSL QUESTION TYPES:
=========================
Core Types:
- QuestionFreeText: Free-form text responses
- QuestionMultipleChoice: Select exactly one option from a list (requires question_options)
- QuestionCheckBox: Select multiple options from a list (requires question_options)
- QuestionNumerical: Numeric responses (optional min_value, max_value)
- QuestionMatrix: Grid-based questions with rows/columns
- QuestionRank: Rank items by preference (requires question_options)
- QuestionInterview: Interview-style dialogue

Derived Types:
- QuestionLinearScale: Linear scale with integer options and optional labels (requires question_options as list[int], optional option_labels as dict[int, str])
- QuestionLikertFive: 5-point agree/disagree scale
- QuestionYesNo: Simple yes/no questions
- QuestionTopK: Select top K items from options
- QuestionMultipleChoiceWithOther: Multiple choice with custom "Other" option

QUESTION TYPE SELECTION GUIDELINES:
===================================
- Use QuestionFreeText for open-ended text questions
- Use QuestionMultipleChoice for single-selection from fixed options
- Use QuestionCheckBox for multi-selection from fixed options
- Use QuestionLikertFive for agree/disagree statements
- Use QuestionLinearScale for numeric scales (1-5, 1-10, etc.) with question_options=[1,2,3,4,5] and optional option_labels={1: "Low", 5: "High"}
- Use QuestionYesNo for binary yes/no questions
- Use QuestionNumerical for pure numeric input

COMMON CONVERSION ERRORS TO DETECT:
====================================
- Likert questions incorrectly classified as QuestionMultipleChoice
- Scale questions with numeric ranges classified as QuestionMultipleChoice
- Yes/No questions classified as QuestionMultipleChoice
- Questions missing their option lists due to CSV parsing errors
- HTML artifacts in question text or options
- Incomplete option lists (e.g., scale showing only [3, 5] instead of [1,2,3,4,5])"""

    max_concurrent: int = 5
    timeout_seconds: int = 30
    model: Optional[str] = None  # Use default model if None
    temperature: float = 0.1  # Low temperature for consistent results

    # Custom analyzers can be added
    custom_analyzers: List[Callable] = None

    # Logging configuration
    enable_logging: bool = True
    log_changes: bool = True  # Log individual changes with diffs
    verbose_logging: bool = False  # Include full analysis details


class VibeProcessor:
    """Processes survey questions using AI agents for cleanup and enhancement."""

    def __init__(self, config: Optional[VibeConfig] = None):
        """
        Initialize the vibe processor.

        Args:
            config: Configuration for vibe processing
        """
        self.config = config or VibeConfig()
        self.analyzer = QuestionAnalyzer(self.config)
        self.changes: List[VibeChange] = []  # Track all changes made

    async def process_survey(self, survey: Survey) -> Survey:
        """
        Process all questions in a survey using vibe analysis.

        Args:
            survey: Survey to process

        Returns:
            Enhanced survey with improved questions
        """
        if not self.config.enabled:
            return survey

        if not survey.questions:
            return survey

        # Process questions in batches to respect concurrency limits
        improved_questions = []

        # Split questions into batches
        batch_size = self.config.max_concurrent
        question_batches = [
            survey.questions[i:i + batch_size]
            for i in range(0, len(survey.questions), batch_size)
        ]

        total_questions = len(survey.questions)
        processed_count = 0

        if self.config.enable_logging:
            print(f"🔍 Analyzing {total_questions} questions for conversion issues...")
            print(f"📊 Processing in batches of {self.config.max_concurrent}")

        for batch_idx, batch in enumerate(question_batches, 1):
            if self.config.enable_logging:
                batch_start = processed_count + 1
                batch_end = min(processed_count + len(batch), total_questions)
                print(f"\n📦 Batch {batch_idx}/{len(question_batches)}: Processing questions {batch_start}-{batch_end}...")

            # Process batch concurrently
            batch_results = await asyncio.gather(
                *[self._process_question(q) for q in batch],
                return_exceptions=True
            )

            # Handle results and exceptions
            for original_question, result in zip(batch, batch_results):
                processed_count += 1

                if isinstance(result, Exception):
                    if self.config.enable_logging:
                        print(f"❌ {original_question.question_name}: Analysis failed - {str(result)[:50]}{'...' if len(str(result)) > 50 else ''}")
                    improved_questions.append(original_question)  # Keep original
                else:
                    if self.config.enable_logging:
                        # Check if any changes were made
                        changes_made = any(
                            change.question_name == original_question.question_name
                            for change in self.changes[-10:]  # Check recent changes
                        )
                        if changes_made:
                            print(f"✨ {original_question.question_name}: Fixed conversion issues")
                        else:
                            print(f"✅ {original_question.question_name}: No issues found")
                    improved_questions.append(result)

        # Final progress summary
        if self.config.enable_logging:
            print(f"\n🎯 Analysis complete: {processed_count}/{total_questions} questions processed")

        return Survey(questions=improved_questions)

    async def _process_question(self, question: Question) -> Question:
        """
        Process a single question using AI analysis.

        Args:
            question: Question to process

        Returns:
            Improved question
        """
        try:
            # Use the analyzer to get suggestions
            analysis = await self.analyzer.analyze_question(question)

            # Apply improvements based on analysis
            improved_question = self._apply_improvements(question, analysis)

            return improved_question

        except Exception as e:
            print(f"Error processing question {question.question_name}: {e}")
            return question  # Return original on error

    def _apply_improvements(self, question: Question, analysis: Dict[str, Any]) -> Question:
        """
        Apply improvements to a question based on analysis results.

        Args:
            question: Original question
            analysis: Analysis results from AI agent

        Returns:
            Improved question
        """
        # Create a copy of the question with improvements
        question_dict = question.to_dict()
        changes_made = []

        # Apply text improvements
        if analysis.get('improved_text') and analysis['improved_text'] != question.question_text:
            original_text = question.question_text
            new_text = analysis['improved_text']
            question_dict['question_text'] = new_text

            # Log the change
            change = VibeChange(
                question_name=question.question_name,
                change_type='text',
                original_value=original_text,
                new_value=new_text,
                reasoning=analysis.get('reasoning', 'Text improvement'),
                confidence=analysis.get('confidence', 0.5)
            )
            changes_made.append(change)

            if self.config.enable_logging:
                print(f"    🔧 Text: Removed conversion artifacts")
                if self.config.verbose_logging:
                    print(f"      Before: {original_text[:80]}{'...' if len(original_text) > 80 else ''}")
                    print(f"      After:  {new_text[:80]}{'...' if len(new_text) > 80 else ''}")
                    print(f"      Reason: {analysis.get('reasoning', 'Text improvement')[:100]}{'...' if len(analysis.get('reasoning', '')) > 100 else ''}")

        # Apply option improvements for multiple choice questions
        if (analysis.get('improved_options') and
            hasattr(question, 'question_options') and
            analysis['improved_options'] != question.question_options):

            original_options = question.question_options
            new_options = analysis['improved_options']
            question_dict['question_options'] = new_options

            # Log the change
            change = VibeChange(
                question_name=question.question_name,
                change_type='options',
                original_value=original_options,
                new_value=new_options,
                reasoning=analysis.get('reasoning', 'Option improvement'),
                confidence=analysis.get('confidence', 0.5)
            )
            changes_made.append(change)

            if self.config.enable_logging:
                print(f"    ⚙️ Options: Fixed corrupted choice list")
                if self.config.verbose_logging:
                    print(f"      Before: {str(original_options)[:60]}{'...' if len(str(original_options)) > 60 else ''}")
                    print(f"      After:  {str(new_options)[:60]}{'...' if len(str(new_options)) > 60 else ''}")
                    print(f"      Reason: {analysis.get('reasoning', 'Option improvement')[:100]}{'...' if len(analysis.get('reasoning', '')) > 100 else ''}")

        # Handle question type changes (if suggested and valid)
        converted_question = None
        if analysis.get('suggested_type') and analysis['suggested_type'] != question.__class__.__name__:
            # Try to convert the question type
            converted_question = self._convert_question_type(question, analysis['suggested_type'], analysis)
            if converted_question:
                # Log the successful conversion
                change = VibeChange(
                    question_name=question.question_name,
                    change_type='type',
                    original_value=question.__class__.__name__,
                    new_value=analysis['suggested_type'],
                    reasoning=analysis.get('reasoning', 'Type conversion'),
                    confidence=analysis.get('confidence', 0.5)
                )
                changes_made.append(change)

                if self.config.enable_logging:
                    print(f"    🔄 Type: {question.__class__.__name__} → {analysis['suggested_type']} (converted)")
                    if self.config.verbose_logging:
                        print(f"      Reason: {analysis.get('reasoning', 'Type optimization')[:100]}{'...' if len(analysis.get('reasoning', '')) > 100 else ''}")
            else:
                # Log the failed conversion
                if self.config.enable_logging:
                    print(f"    💡 Type: {question.__class__.__name__} → {analysis['suggested_type']} (suggested - conversion failed)")
                    if self.config.verbose_logging:
                        print(f"      Reason: {analysis.get('reasoning', 'Type optimization')[:100]}{'...' if len(analysis.get('reasoning', '')) > 100 else ''}")

        # Store changes for tracking
        self.changes.extend(changes_made)

        # Return the converted question if we have one, otherwise recreate with improvements
        if converted_question:
            return converted_question

        # Recreate question with improvements (for text/option changes only)
        if changes_made:
            try:
                # Get the original class type and filter valid parameters
                question_class = question.__class__

                # Remove parameters that aren't valid for question constructors
                clean_dict = {k: v for k, v in question_dict.items()
                             if k not in ['question_type', 'response_validator_class', 'edsl_version', 'edsl_class_name']}

                return question_class(**clean_dict)

            except Exception as e:
                # If recreation fails, return original question
                print(f"Warning: Could not recreate question {question.question_name}: {e}")
                return question
        else:
            # No changes made, return original
            return question

    def _convert_question_type(self, question: Question, target_type: str, analysis: Dict[str, Any]) -> Optional[Question]:
        """
        Convert a question to a different EDSL question type.

        Args:
            question: Original question
            target_type: Target EDSL question type name
            analysis: Analysis results with conversion details

        Returns:
            New question with converted type, or None if conversion failed
        """
        if self.config.enable_logging:
            print(f"    🔄 Converting {question.__class__.__name__} → {target_type}")
            print(f"      Question: {question.question_name}")
            print(f"      Text: {question.question_text[:60]}{'...' if len(question.question_text) > 60 else ''}")

        if target_type == 'QuestionLinearScale':
            result = self._convert_to_linear_scale(question, analysis)
        elif target_type == 'QuestionFreeText':
            result = self._convert_to_free_text(question, analysis)
        elif target_type == 'QuestionYesNo':
            result = self._convert_to_yes_no(question, analysis)
        elif target_type == 'QuestionLikertFive':
            result = self._convert_to_likert_five(question, analysis)
        elif target_type == 'QuestionNumerical':
            result = self._convert_to_numerical(question, analysis)
        elif target_type == 'QuestionMultipleChoiceWithOther':
            result = self._convert_to_multiple_choice_with_other(question, analysis)
        # QuestionBudget is excluded from EDSL available types
        # elif target_type == 'QuestionBudget':
        #     result = self._convert_to_budget(question, analysis)
        elif target_type == 'QuestionCheckBox':
            result = self._convert_to_checkbox(question, analysis)
        else:
            if self.config.enable_logging:
                print(f"      ❌ Unsupported conversion type: {target_type}")
                self._explain_unsupported_conversion(target_type, question)
            return None

        if result:
            if self.config.enable_logging:
                print(f"      ✅ Conversion successful!")
        else:
            if self.config.enable_logging:
                print(f"      ❌ Conversion failed")

        return result

    def _explain_unsupported_conversion(self, target_type: str, question: Question) -> None:
        """Explain why a specific conversion type is not supported and what would be needed."""
        explanations = {
            'QuestionNumerical': {
                'reason': 'No implementation for converting to QuestionNumerical',
                'requirements': 'Would need to create QuestionNumerical with appropriate constraints',
                'current_data': f"Current type: {question.__class__.__name__}, Text: '{question.question_text}'"
            },
            'QuestionBudget': {
                'reason': 'No implementation for converting to QuestionBudget',
                'requirements': 'Would need to extract percentage options and create budget allocation logic',
                'current_data': f"Current options: {getattr(question, 'question_options', 'None')}"
            },
            'QuestionMultipleChoiceWithOther': {
                'reason': 'No implementation for converting to QuestionMultipleChoiceWithOther',
                'requirements': 'Would need to detect "Other" option and separate it from regular choices',
                'current_data': f"Current options: {getattr(question, 'question_options', 'None')}"
            },
            'QuestionCheckBox': {
                'reason': 'No implementation for converting to QuestionCheckBox',
                'requirements': 'Would need to convert multiple choice to multiple selection format',
                'current_data': f"Current options: {getattr(question, 'question_options', 'None')}"
            },
            'QuestionRank': {
                'reason': 'No implementation for converting to QuestionRank',
                'requirements': 'Would need to create ranking logic for the options',
                'current_data': f"Current options: {getattr(question, 'question_options', 'None')}"
            }
        }

        if target_type in explanations:
            info = explanations[target_type]
            print(f"      💭 Why unsupported: {info['reason']}")
            print(f"      🛠️  What's needed: {info['requirements']}")
            print(f"      📋 Current data: {info['current_data']}")
        else:
            print(f"      💭 Why unsupported: No converter implemented for {target_type}")
            print(f"      🛠️  What's needed: Create _{target_type.lower().replace('question', 'convert_to_')} method")
            print(f"      📋 Current data: {question.__class__.__name__} with text '{question.question_text[:50]}{'...' if len(question.question_text) > 50 else ''}'")

    def _convert_to_linear_scale(self, question: Question, analysis: Dict[str, Any]) -> Optional[Question]:
        """Convert to QuestionLinearScale with proper format."""
        if self.config.enable_logging:
            print(f"      🔍 Attempting LinearScale conversion...")
            print(f"      Input options: {getattr(question, 'question_options', 'None')}")

        try:
            from edsl.questions import QuestionLinearScale

            if not hasattr(question, 'question_options') or not question.question_options:
                if self.config.enable_logging:
                    print(f"      ❌ No question_options found")
                return None

            options = question.question_options
            if self.config.enable_logging:
                print(f"      📝 Processing {len(options)} options: {options}")

            # Extract numeric scale and labels
            numeric_options = []
            option_labels = {}

            for i, option in enumerate(options):
                option_str = str(option).strip()
                if self.config.enable_logging:
                    print(f"      Option {i+1}: '{option_str}'")

                # Pattern: "Label - Number"
                if ' - ' in option_str:
                    parts = option_str.split(' - ')
                    if len(parts) == 2:
                        label_part = parts[0].strip()
                        num_part = parts[1].strip()
                        if num_part.isdigit():
                            num_val = int(num_part)
                            numeric_options.append(num_val)
                            option_labels[num_val] = label_part
                            if self.config.enable_logging:
                                print(f"        └─ Found labeled number: {num_val} = '{label_part}'")
                        else:
                            if self.config.enable_logging:
                                print(f"        └─ Non-numeric part: '{num_part}'")
                    else:
                        if self.config.enable_logging:
                            print(f"        └─ Multiple dashes, parts: {parts}")

                # Pattern: Just a number
                elif option_str.isdigit():
                    num_val = int(option_str)
                    numeric_options.append(num_val)
                    if self.config.enable_logging:
                        print(f"        └─ Found number: {num_val}")
                else:
                    if self.config.enable_logging:
                        print(f"        └─ Non-numeric option: '{option_str}'")

            if self.config.enable_logging:
                print(f"      📊 Extracted numeric values: {numeric_options}")
                print(f"      🏷️  Extracted labels: {option_labels}")

            # Check if we have a valid numeric sequence
            if len(numeric_options) >= 2:
                numeric_options.sort()
                min_val, max_val = numeric_options[0], numeric_options[-1]

                # Create complete sequence
                complete_sequence = list(range(min_val, max_val + 1))

                if self.config.enable_logging:
                    print(f"      ✅ Valid scale detected: {min_val}-{max_val}")
                    print(f"      📏 Complete sequence: {complete_sequence}")

                # Create the linear scale question
                kwargs = {
                    'question_name': question.question_name,
                    'question_text': question.question_text,
                    'question_options': complete_sequence
                }

                # Only include option_labels if we have labels for all endpoints (min and max)
                if option_labels and min_val in option_labels and max_val in option_labels:
                    kwargs['option_labels'] = option_labels
                    if self.config.enable_logging:
                        print(f"      🏷️  Using complete endpoint labels: {option_labels}")
                elif option_labels:
                    if self.config.enable_logging:
                        print(f"      ⚠️  Incomplete labels found: {option_labels}")
                        print(f"      ⚠️  QuestionLinearScale requires labels for both endpoints or none")
                        print(f"      ⚠️  Skipping labels to avoid validation error")

                if self.config.enable_logging:
                    print(f"      🔧 Creating QuestionLinearScale with kwargs: {kwargs}")

                return QuestionLinearScale(**kwargs)
            else:
                if self.config.enable_logging:
                    print(f"      ❌ Insufficient numeric values: {len(numeric_options)} < 2")

        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ LinearScale conversion failed: {e}")
                import traceback
                traceback.print_exc()

        return None

    def _convert_to_free_text(self, question: Question, analysis: Dict[str, Any]) -> Optional[Question]:
        """Convert to QuestionFreeText."""
        if self.config.enable_logging:
            print(f"      🔍 Converting to FreeText...")
        try:
            from edsl.questions import QuestionFreeText
            result = QuestionFreeText(
                question_name=question.question_name,
                question_text=question.question_text
            )
            if self.config.enable_logging:
                print(f"      ✅ FreeText conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ FreeText conversion failed: {e}")
            return None

    def _convert_to_yes_no(self, question: Question, analysis: Dict[str, Any]) -> Optional[Question]:
        """Convert to QuestionYesNo."""
        if self.config.enable_logging:
            print(f"      🔍 Converting to YesNo...")
        try:
            from edsl.questions import QuestionYesNo
            result = QuestionYesNo(
                question_name=question.question_name,
                question_text=question.question_text
            )
            if self.config.enable_logging:
                print(f"      ✅ YesNo conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ YesNo conversion failed: {e}")
            return None

    def _convert_to_likert_five(self, question: Question, analysis: Dict[str, Any]) -> Optional[Question]:
        """Convert to QuestionLikertFive."""
        if self.config.enable_logging:
            print(f"      🔍 Converting to LikertFive...")
        try:
            from edsl.questions import QuestionLikertFive
            result = QuestionLikertFive(
                question_name=question.question_name,
                question_text=question.question_text
            )
            if self.config.enable_logging:
                print(f"      ✅ LikertFive conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ LikertFive conversion failed: {e}")
            return None

    def _convert_to_numerical(self, question: Question, analysis: Dict[str, Any]) -> Optional[Question]:
        """Convert to QuestionNumerical."""
        if self.config.enable_logging:
            print(f"      🔍 Converting to Numerical...")
        try:
            from edsl.questions import QuestionNumerical

            # Basic conversion - use question text and name
            kwargs = {
                'question_name': question.question_name,
                'question_text': question.question_text
            }

            # Try to infer constraints from analysis or question text
            min_val, max_val = self._infer_numerical_constraints(question, analysis)
            if min_val is not None:
                kwargs['min_value'] = min_val
            if max_val is not None:
                kwargs['max_value'] = max_val

            if self.config.enable_logging:
                constraints = []
                if min_val is not None:
                    constraints.append(f"min={min_val}")
                if max_val is not None:
                    constraints.append(f"max={max_val}")
                constraint_str = f" with {', '.join(constraints)}" if constraints else ""
                print(f"      📊 Creating numerical question{constraint_str}")

            result = QuestionNumerical(**kwargs)
            if self.config.enable_logging:
                print(f"      ✅ Numerical conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ Numerical conversion failed: {e}")
            return None

    def _infer_numerical_constraints(self, question: Question, analysis: Dict[str, Any]) -> tuple:
        """Infer min/max constraints for numerical questions."""
        min_val, max_val = None, None

        # Look for year constraints
        if 'year' in question.question_text.lower():
            if 'birth' in question.question_text.lower():
                min_val, max_val = 1900, 2024  # Birth year range
            else:
                min_val, max_val = 1900, 2100  # General year range

        # Look for percentage constraints
        elif 'percentage' in question.question_text.lower() or '%' in question.question_text:
            min_val, max_val = 0, 100

        # Look for rating constraints
        elif any(word in question.question_text.lower() for word in ['rate', 'rating', 'scale']):
            if '1 to 10' in question.question_text or '1-10' in question.question_text:
                min_val, max_val = 1, 10
            elif '1 to 5' in question.question_text or '1-5' in question.question_text:
                min_val, max_val = 1, 5

        # Look for count constraints (assignment, contract counts, etc.)
        elif 'count' in question.question_text.lower():
            min_val = 0  # Counts are non-negative

        return min_val, max_val

    def _convert_to_multiple_choice_with_other(self, question: Question, analysis: Dict[str, Any]) -> Optional[Question]:
        """Convert to QuestionMultipleChoiceWithOther."""
        if self.config.enable_logging:
            print(f"      🔍 Converting to MultipleChoiceWithOther...")
        try:
            from edsl.questions import QuestionMultipleChoiceWithOther

            # Get options from current question or analysis
            options = getattr(question, 'question_options', None) or analysis.get('improved_options', [])
            if not options:
                if self.config.enable_logging:
                    print(f"      ❌ No options found for MultipleChoiceWithOther")
                return None

            # Find and separate "Other" options
            other_patterns = ['other', 'specify', 'else', 'different', 'not listed', 'prefer to self-describe']
            regular_options = []
            other_option = None

            for option in options:
                option_lower = option.lower()
                if any(pattern in option_lower for pattern in other_patterns):
                    if other_option is None:  # Take first "other" option found
                        other_option = option
                    # Don't add other options to regular list
                else:
                    regular_options.append(option)

            if not other_option:
                if self.config.enable_logging:
                    print(f"      ❌ No 'Other' option found in: {options}")
                return None

            if self.config.enable_logging:
                print(f"      📋 Regular options: {len(regular_options)}")
                print(f"      🔄 Other option: '{other_option}'")

            result = QuestionMultipleChoiceWithOther(
                question_name=question.question_name,
                question_text=question.question_text,
                question_options=regular_options
            )
            if self.config.enable_logging:
                print(f"      ✅ MultipleChoiceWithOther conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ MultipleChoiceWithOther conversion failed: {e}")
            return None

    def _convert_to_budget(self, question: Question, analysis: Dict[str, Any]) -> Optional[Question]:
        """Convert to QuestionBudget."""
        if self.config.enable_logging:
            print(f"      🔍 Converting to Budget...")
        try:
            from edsl.questions import QuestionBudget

            # Get options that should represent percentages
            options = getattr(question, 'question_options', None) or analysis.get('improved_options', [])
            if not options:
                if self.config.enable_logging:
                    print(f"      ❌ No options found for Budget conversion")
                return None

            # Convert string options to numeric values for validation
            try:
                numeric_options = [float(opt.replace('%', '')) for opt in options if opt.replace('.', '').replace('%', '').isdigit()]
                if self.config.enable_logging:
                    print(f"      📊 Found {len(numeric_options)} numeric values: {numeric_options[:10]}{'...' if len(numeric_options) > 10 else ''}")
            except (ValueError, AttributeError):
                if self.config.enable_logging:
                    print(f"      ❌ Could not parse options as numbers: {options[:5]}{'...' if len(options) > 5 else ''}")
                return None

            # Use the text to infer budget categories from the question
            question_text = question.question_text.lower()

            # Try to extract categories from question text
            if 'freelancer' in question_text and 'ai' in question_text:
                # This appears to be about freelancer vs AI work allocation
                budget_sum_to = 100  # percentage allocation
                question_options = ['Work done by freelancers', 'Work done with AI tools']
            else:
                # Generic budget allocation
                budget_sum_to = 100
                question_options = ['Category A', 'Category B', 'Other']
                if self.config.enable_logging:
                    print(f"      ⚠️  Using generic categories - budget question not fully parsed")

            if self.config.enable_logging:
                print(f"      💰 Budget categories: {question_options}")
                print(f"      📊 Budget must sum to: {budget_sum_to}")

            result = QuestionBudget(
                question_name=question.question_name,
                question_text=question.question_text,
                question_options=question_options,
                budget_sum=budget_sum_to
            )
            if self.config.enable_logging:
                print(f"      ✅ Budget conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ Budget conversion failed: {e}")
            return None

    def _convert_to_checkbox(self, question: Question, analysis: Dict[str, Any]) -> Optional[Question]:
        """Convert to QuestionCheckBox."""
        if self.config.enable_logging:
            print(f"      🔍 Converting to CheckBox...")
        try:
            from edsl.questions import QuestionCheckBox

            # Get options from current question
            options = getattr(question, 'question_options', None) or analysis.get('improved_options', [])
            if not options:
                if self.config.enable_logging:
                    print(f"      ❌ No options found for CheckBox conversion")
                return None

            if self.config.enable_logging:
                print(f"      ☑️  Creating checkbox with {len(options)} options")
                if self.config.verbose_logging:
                    print(f"      📋 Options: {options[:5]}{'...' if len(options) > 5 else ''}")

            result = QuestionCheckBox(
                question_name=question.question_name,
                question_text=question.question_text,
                question_options=options
            )
            if self.config.enable_logging:
                print(f"      ✅ CheckBox conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ CheckBox conversion failed: {e}")
            return None

    def process_survey_sync(self, survey: Survey) -> Survey:
        """
        Synchronous wrapper for survey processing.

        Args:
            survey: Survey to process

        Returns:
            Processed survey
        """
        return asyncio.run(self.process_survey(survey))

    def get_change_log(self) -> List[Dict[str, Any]]:
        """
        Get a list of all changes made during processing.

        Returns:
            List of change dictionaries with full diff information
        """
        return [change.to_dict() for change in self.changes]

    def get_change_summary(self) -> Dict[str, Any]:
        """
        Get a summary of changes made during processing.

        Returns:
            Summary dictionary with counts and statistics
        """
        if not self.changes:
            return {
                'total_changes': 0,
                'changes_by_type': {},
                'questions_modified': 0,
                'average_confidence': 0.0
            }

        changes_by_type = {}
        questions_modified = set()
        total_confidence = 0.0

        for change in self.changes:
            # Count by type
            change_type = change.change_type
            changes_by_type[change_type] = changes_by_type.get(change_type, 0) + 1

            # Track questions modified
            questions_modified.add(change.question_name)

            # Sum confidence scores
            total_confidence += change.confidence

        return {
            'total_changes': len(self.changes),
            'changes_by_type': changes_by_type,
            'questions_modified': len(questions_modified),
            'average_confidence': total_confidence / len(self.changes) if self.changes else 0.0,
            'modified_questions': list(questions_modified)
        }

    def print_change_summary(self) -> None:
        """Print a formatted summary of all changes made."""
        summary = self.get_change_summary()

        print(f"\n{'='*60}")
        print(f"🔍 VIBE PROCESSING SUMMARY")
        print(f"{'='*60}")

        if summary['total_changes'] == 0:
            print(f"✅ No conversion issues found - all questions clean!")
        else:
            print(f"📊 Results:")
            print(f"   • Total fixes applied: {summary['total_changes']}")
            print(f"   • Questions modified: {summary['questions_modified']}")
            print(f"   • Average confidence: {summary['average_confidence']:.1%}")

            if summary['changes_by_type']:
                print(f"\n🔧 Fixes by type:")
                change_icons = {
                    'text': '🔧',
                    'options': '⚙️',
                    'type': '🔄'
                }
                for change_type, count in summary['changes_by_type'].items():
                    icon = change_icons.get(change_type, '•')
                    change_desc = {
                        'text': 'HTML/formatting cleanup',
                        'options': 'Option list repairs',
                        'type': 'Question type conversions'
                    }.get(change_type, change_type)
                    print(f"   {icon} {change_desc}: {count}")

        if self.config.verbose_logging and self.changes:
            print(f"\n📋 Change Details:")
            for i, change in enumerate(self.changes, 1):
                print(f"   {i}. {change.question_name} ({change.change_type})")
                print(f"      {change.reasoning[:80]}{'...' if len(change.reasoning) > 80 else ''}")
                print()

        print(f"{'='*60}")