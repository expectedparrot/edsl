"""
Main vibe processor for AI-powered question cleanup and enhancement.
"""

import asyncio
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from edsl import Survey
from edsl.questions import Question

# QuestionAnalyzer removed - using multi-step processing instead


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
            "question_name": self.question_name,
            "change_type": self.change_type,
            "original_value": self.original_value,
            "new_value": self.new_value,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VibeConfig:
    """Configuration for vibe processing."""

    enabled: bool = True
    system_prompt: str = None  # Will be loaded from file
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

    def __post_init__(self):
        """Load system prompt from file if not provided."""
        if self.system_prompt is None:
            try:
                from .config.prompts.prompt_builder import PromptBuilder

                prompt_builder = PromptBuilder()
                self.system_prompt = prompt_builder.system_prompt
            except Exception:
                # Fallback system prompt if file loading fails
                self.system_prompt = "You are analyzing questions converted from Qualtrics CSV exports to identify and fix technical conversion errors and misclassifications."


class VibeProcessor:
    """Processes survey questions using AI agents for cleanup and enhancement."""

    def __init__(self, config: Optional[VibeConfig] = None):
        """
        Initialize the vibe processor.

        Args:
            config: Configuration for vibe processing
        """
        self.config = config or VibeConfig()
        # analyzer removed - using multi-step processing
        self.changes: List[VibeChange] = []  # Track all changes made

    async def process_survey(
        self, survey: Survey, response_data: Optional[Dict[str, List[str]]] = None
    ) -> Survey:
        """
        Process all questions in a survey using vibe analysis.

        Args:
            survey: Survey to process
            response_data: Optional response data for extracting options

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
            survey.questions[i : i + batch_size]
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
                print(
                    f"\n📦 Batch {batch_idx}/{len(question_batches)}: Processing questions {batch_start}-{batch_end}..."
                )

            # Process batch concurrently
            batch_results = await asyncio.gather(
                *[self._process_question(q, response_data) for q in batch],
                return_exceptions=True,
            )

            # Handle results and exceptions
            for original_question, result in zip(batch, batch_results):
                processed_count += 1

                if isinstance(result, Exception):
                    if self.config.enable_logging:
                        print(
                            f"❌ {original_question.question_name}: Analysis failed - {str(result)[:50]}{'...' if len(str(result)) > 50 else ''}"
                        )
                    improved_questions.append(original_question)  # Keep original
                else:
                    if self.config.enable_logging:
                        # Check if any changes were made
                        changes_made = any(
                            change.question_name == original_question.question_name
                            for change in self.changes[-10:]  # Check recent changes
                        )
                        if changes_made:
                            print(
                                f"✨ {original_question.question_name}: Fixed conversion issues"
                            )
                        else:
                            print(
                                f"✅ {original_question.question_name}: No issues found"
                            )
                    improved_questions.append(result)

        # Final progress summary
        if self.config.enable_logging:
            print(
                f"\n🎯 Analysis complete: {processed_count}/{total_questions} questions processed"
            )

        return Survey(questions=improved_questions)

    async def _process_question(
        self, question: Question, response_data: Optional[Dict[str, List[str]]] = None
    ) -> Question:
        """
        Process a single question using multi-step specialized processors.

        Args:
            question: Question to process
            response_data: Optional response data for extracting options

        Returns:
            Improved question
        """
        if self.config.enable_logging:
            print(f"🔧 LLM analysis {question.question_name}...")

        try:
            # Use LLM-based analysis instead of rule-based multi-step processing
            from .question_analyzer import QuestionAnalyzer

            # Create analyzer with current config
            analyzer = QuestionAnalyzer(self.config)

            # Analyze the question using LLM
            analysis_result = await analyzer.analyze_question(question, response_data)

            # Apply the improvements from LLM analysis
            improved_question = question
            changes_made = []

            # Initialize question_class for use throughout
            question_class = type(question)

            # Check if any improvements were suggested
            has_improvements = (
                analysis_result.get("improved_text")
                or analysis_result.get("improved_options")
                or analysis_result.get("suggested_type")
            )

            if has_improvements:
                # Create improved question by applying the changes
                question_dict = question.to_dict()

                # Apply text improvements
                if analysis_result.get("improved_text"):
                    question_dict["question_text"] = analysis_result["improved_text"]
                    changes_made.append(
                        {
                            "type": "text_improved",
                            "original": question.question_text,
                            "new": analysis_result["improved_text"],
                        }
                    )

                # Apply type improvements first (if any)
                type_change_planned = analysis_result.get("suggested_type")

                # Apply option improvements (but skip if we're changing types that don't use options)
                if analysis_result.get("improved_options") and type_change_planned not in [
                        "QuestionNumerical",
                        "QuestionFreeText",
                        "QuestionYesNo",
                        "QuestionLikertFive",
                    ]:
                    question_dict["question_options"] = analysis_result[
                        "improved_options"
                    ]
                    changes_made.append(
                        {
                            "type": "options_reordered",
                            "original": getattr(question, "question_options", []),
                            "new": analysis_result["improved_options"],
                        }
                    )

                # Apply type improvements
                if analysis_result.get("suggested_type"):
                    suggested_type = analysis_result["suggested_type"]
                    try:
                        # Import question types
                        from edsl.questions import (
                            QuestionNumerical,
                            QuestionLinearScale,
                            QuestionYesNo,
                            QuestionLikertFive,
                            QuestionFreeText,
                        )

                        type_map = {
                            "QuestionNumerical": ("numerical", QuestionNumerical),
                            "QuestionLinearScale": (
                                "linear_scale",
                                QuestionLinearScale,
                            ),
                            "QuestionYesNo": ("yes_no", QuestionYesNo),
                            "QuestionLikertFive": ("likert_five", QuestionLikertFive),
                            "QuestionFreeText": ("free_text", QuestionFreeText),
                        }

                        if suggested_type in type_map:
                            type_name, question_class = type_map[suggested_type]

                            if self.config.enable_logging:
                                print(
                                    f"    🔄 Converting {question.question_name} from {question.__class__.__name__} to {suggested_type}"
                                )

                            # Update the question_type in the dict to use the correct EDSL type name
                            question_dict["question_type"] = type_name

                            # Clean the question dict for the new type BEFORE adding type-specific parameters
                            if self.config.enable_logging:
                                print(
                                    f"    🧹 Cleaning parameters for {suggested_type}"
                                )
                            question_dict = self._clean_question_dict_for_type(
                                question_dict, suggested_type
                            )

                            # For numerical questions, add min/max after cleaning
                            if suggested_type == "QuestionNumerical":
                                if self.config.enable_logging:
                                    print("    📊 Adding numerical parameters")
                                if "percentage" in question.question_text.lower():
                                    question_dict["min_value"] = 0
                                    question_dict["max_value"] = 100
                                    if self.config.enable_logging:
                                        print("    📊 Set percentage range: 0-100")
                                elif (
                                    hasattr(question, "question_options")
                                    and question.question_options
                                ):
                                    # Try to infer from existing options
                                    numeric_values = []
                                    for opt in question.question_options:
                                        try:
                                            numeric_values.append(float(str(opt)))
                                        except:
                                            pass
                                    if numeric_values:
                                        question_dict["min_value"] = min(numeric_values)
                                        question_dict["max_value"] = max(numeric_values)
                                        if self.config.enable_logging:
                                            print(
                                                f"    📊 Inferred range: {question_dict['min_value']}-{question_dict['max_value']}"
                                            )

                            changes_made.append(
                                {
                                    "type": "question_type_corrected",
                                    "original": question.__class__.__name__,
                                    "new": suggested_type,
                                }
                            )

                    except Exception as e:
                        if self.config.enable_logging:
                            print(
                                f"    ⚠️ Could not convert {question.question_name} to {suggested_type}: {e}"
                            )
                        # Keep original type if conversion fails
                        question_class = type(question)
                else:
                    # No type change
                    question_class = type(question)

                # Create the improved question
                if self.config.enable_logging:
                    print(
                        f"    🏗️ Creating question with class: {question_class.__name__}"
                    )
                    print(f"    🏗️ Question dict keys: {list(question_dict.keys())}")
                improved_question = question_class.from_dict(question_dict)

                if self.config.enable_logging and changes_made:
                    print(
                        f"    ✨ {question.question_name}: Made {len(changes_made)} improvements"
                    )

                # Store changes for reporting
                for change in changes_made:
                    vibe_change = VibeChange(
                        question_name=question.question_name,
                        change_type=change["type"],
                        original_value=change["original"],
                        new_value=change["new"],
                        reasoning=analysis_result.get("reasoning", ""),
                        confidence=analysis_result.get("confidence", 0.5),
                    )
                    self.changes.append(vibe_change)
            else:
                if self.config.enable_logging:
                    print(f"    ✅ {question.question_name}: No issues found")

            # Validate the final question configuration
            if self.config.enable_logging:
                print(f"🔍 Validating {improved_question.question_name}...")

            validation_result = await analyzer.validate_question(
                improved_question, response_data
            )

            # Log validation results if any issues found
            if not validation_result.get("is_sensible", True):
                if self.config.enable_logging:
                    print(
                        f"    ⚠️  Validation concerns for {improved_question.question_name}:"
                    )
                    for issue in validation_result.get("issues_found", []):
                        print(f"        - {issue}")
                    for suggestion in validation_result.get("suggestions", []):
                        print(f"        💡 {suggestion}")
            else:
                if self.config.enable_logging:
                    print(
                        f"    ✅ Validation passed for {improved_question.question_name}"
                    )

            return improved_question

        except Exception as e:
            if self.config.enable_logging:
                print(f"    ❌ Error processing question {question.question_name}: {e}")
            return question  # Return original on error

    def _clean_question_dict_for_type(
        self, question_dict: Dict[str, Any], target_type: str
    ) -> Dict[str, Any]:
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
            "QuestionFreeText": {
                "question_name",
                "question_text",
                "answering_instructions",
                "question_presentation",
            },
            "QuestionYesNo": {
                "question_name",
                "question_text",
                "answering_instructions",
                "question_presentation",
            },
            "QuestionLinearScale": {
                "question_name",
                "question_text",
                "question_options",
                "answering_instructions",
                "question_presentation",
            },
            "QuestionLikertFive": {
                "question_name",
                "question_text",
                "answering_instructions",
                "question_presentation",
            },
            "QuestionNumerical": {
                "question_name",
                "question_text",
                "min_value",
                "max_value",
                "answering_instructions",
                "question_presentation",
            },
        }

        # Get valid parameters for the target type
        if target_type in valid_params:
            valid_for_type = valid_params[target_type]

            # Remove any parameters that are not valid for this type
            keys_to_remove = []
            for key in clean_dict:
                if (
                    key not in valid_for_type and key != "question_type"
                ):  # Always keep question_type
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del clean_dict[key]

        return clean_dict

    def _apply_improvements(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Question:
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
        if (
            analysis.get("improved_text")
            and analysis["improved_text"] != question.question_text
        ):
            original_text = question.question_text
            new_text = analysis["improved_text"]
            question_dict["question_text"] = new_text

            # Log the change
            change = VibeChange(
                question_name=question.question_name,
                change_type="text",
                original_value=original_text,
                new_value=new_text,
                reasoning=analysis.get("reasoning", "Text improvement"),
                confidence=analysis.get("confidence", 0.5),
            )
            changes_made.append(change)

            if self.config.enable_logging:
                print("    🔧 Text: Removed conversion artifacts")
                if self.config.verbose_logging:
                    print(
                        f"      Before: {original_text[:80]}{'...' if len(original_text) > 80 else ''}"
                    )
                    print(
                        f"      After:  {new_text[:80]}{'...' if len(new_text) > 80 else ''}"
                    )
                    print(
                        f"      Reason: {analysis.get('reasoning', 'Text improvement')[:100]}{'...' if len(analysis.get('reasoning', '')) > 100 else ''}"
                    )

        # Apply option improvements for multiple choice questions
        if (
            analysis.get("improved_options")
            and hasattr(question, "question_options")
            and analysis["improved_options"] != question.question_options
        ):

            original_options = question.question_options
            new_options = analysis["improved_options"]
            question_dict["question_options"] = new_options

            # Log the change
            change = VibeChange(
                question_name=question.question_name,
                change_type="options",
                original_value=original_options,
                new_value=new_options,
                reasoning=analysis.get("reasoning", "Option improvement"),
                confidence=analysis.get("confidence", 0.5),
            )
            changes_made.append(change)

            if self.config.enable_logging:
                print("    ⚙️ Options: Fixed corrupted choice list")
                if self.config.verbose_logging:
                    print(
                        f"      Before: {str(original_options)[:60]}{'...' if len(str(original_options)) > 60 else ''}"
                    )
                    print(
                        f"      After:  {str(new_options)[:60]}{'...' if len(str(new_options)) > 60 else ''}"
                    )
                    print(
                        f"      Reason: {analysis.get('reasoning', 'Option improvement')[:100]}{'...' if len(analysis.get('reasoning', '')) > 100 else ''}"
                    )

        # Handle question type changes (if suggested and valid)
        converted_question = None
        if (
            analysis.get("suggested_type")
            and analysis["suggested_type"] != question.__class__.__name__
        ):
            # Try to convert the question type
            converted_question = self._convert_question_type(
                question, analysis["suggested_type"], analysis
            )
            if converted_question:
                # Log the successful conversion
                change = VibeChange(
                    question_name=question.question_name,
                    change_type="type",
                    original_value=question.__class__.__name__,
                    new_value=analysis["suggested_type"],
                    reasoning=analysis.get("reasoning", "Type conversion"),
                    confidence=analysis.get("confidence", 0.5),
                )
                changes_made.append(change)

                if self.config.enable_logging:
                    print(
                        f"    🔄 Type: {question.__class__.__name__} → {analysis['suggested_type']} (converted)"
                    )
                    if self.config.verbose_logging:
                        print(
                            f"      Reason: {analysis.get('reasoning', 'Type optimization')[:100]}{'...' if len(analysis.get('reasoning', '')) > 100 else ''}"
                        )
            else:
                # Log the failed conversion
                if self.config.enable_logging:
                    print(
                        f"    💡 Type: {question.__class__.__name__} → {analysis['suggested_type']} (suggested - conversion failed)"
                    )
                    if self.config.verbose_logging:
                        print(
                            f"      Reason: {analysis.get('reasoning', 'Type optimization')[:100]}{'...' if len(analysis.get('reasoning', '')) > 100 else ''}"
                        )

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
                clean_dict = {
                    k: v
                    for k, v in question_dict.items()
                    if k
                    not in [
                        "question_type",
                        "response_validator_class",
                        "edsl_version",
                        "edsl_class_name",
                    ]
                }

                return question_class(**clean_dict)

            except Exception as e:
                # If recreation fails, return original question
                print(
                    f"Warning: Could not recreate question {question.question_name}: {e}"
                )
                return question
        else:
            # No changes made, return original
            return question

    def _convert_question_type(
        self, question: Question, target_type: str, analysis: Dict[str, Any]
    ) -> Optional[Question]:
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
            print(
                f"      Text: {question.question_text[:60]}{'...' if len(question.question_text) > 60 else ''}"
            )

        if target_type == "QuestionLinearScale":
            result = self._convert_to_linear_scale(question, analysis)
        elif target_type == "QuestionFreeText":
            result = self._convert_to_free_text(question, analysis)
        elif target_type == "QuestionYesNo":
            result = self._convert_to_yes_no(question, analysis)
        elif target_type == "QuestionLikertFive":
            result = self._convert_to_likert_five(question, analysis)
        elif target_type == "QuestionNumerical":
            result = self._convert_to_numerical(question, analysis)
        elif target_type == "QuestionMultipleChoiceWithOther":
            result = self._convert_to_multiple_choice_with_other(question, analysis)
        # QuestionBudget is excluded from EDSL available types
        # elif target_type == 'QuestionBudget':
        #     result = self._convert_to_budget(question, analysis)
        elif target_type == "QuestionCheckBox":
            result = self._convert_to_checkbox(question, analysis)
        else:
            if self.config.enable_logging:
                print(f"      ❌ Unsupported conversion type: {target_type}")
                self._explain_unsupported_conversion(target_type, question)
            return None

        if result:
            if self.config.enable_logging:
                print("      ✅ Conversion successful!")
        else:
            if self.config.enable_logging:
                print("      ❌ Conversion failed")

        return result

    def _explain_unsupported_conversion(
        self, target_type: str, question: Question
    ) -> None:
        """Explain why a specific conversion type is not supported and what would be needed."""
        explanations = {
            "QuestionNumerical": {
                "reason": "No implementation for converting to QuestionNumerical",
                "requirements": "Would need to create QuestionNumerical with appropriate constraints",
                "current_data": f"Current type: {question.__class__.__name__}, Text: '{question.question_text}'",
            },
            "QuestionBudget": {
                "reason": "No implementation for converting to QuestionBudget",
                "requirements": "Would need to extract percentage options and create budget allocation logic",
                "current_data": f"Current options: {getattr(question, 'question_options', 'None')}",
            },
            "QuestionMultipleChoiceWithOther": {
                "reason": "No implementation for converting to QuestionMultipleChoiceWithOther",
                "requirements": 'Would need to detect "Other" option and separate it from regular choices',
                "current_data": f"Current options: {getattr(question, 'question_options', 'None')}",
            },
            "QuestionCheckBox": {
                "reason": "No implementation for converting to QuestionCheckBox",
                "requirements": "Would need to convert multiple choice to multiple selection format",
                "current_data": f"Current options: {getattr(question, 'question_options', 'None')}",
            },
            "QuestionRank": {
                "reason": "No implementation for converting to QuestionRank",
                "requirements": "Would need to create ranking logic for the options",
                "current_data": f"Current options: {getattr(question, 'question_options', 'None')}",
            },
        }

        if target_type in explanations:
            info = explanations[target_type]
            print(f"      💭 Why unsupported: {info['reason']}")
            print(f"      🛠️  What's needed: {info['requirements']}")
            print(f"      📋 Current data: {info['current_data']}")
        else:
            print(
                f"      💭 Why unsupported: No converter implemented for {target_type}"
            )
            print(
                f"      🛠️  What's needed: Create _{target_type.lower().replace('question', 'convert_to_')} method"
            )
            print(
                f"      📋 Current data: {question.__class__.__name__} with text '{question.question_text[:50]}{'...' if len(question.question_text) > 50 else ''}'"
            )

    def _convert_to_linear_scale(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Optional[Question]:
        """Convert to QuestionLinearScale with proper format."""
        if self.config.enable_logging:
            print("      🔍 Attempting LinearScale conversion...")
            print(
                f"      Input options: {getattr(question, 'question_options', 'None')}"
            )

        try:
            from edsl.questions import QuestionLinearScale

            if (
                not hasattr(question, "question_options")
                or not question.question_options
            ):
                if self.config.enable_logging:
                    print("      ❌ No question_options found")
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
                if " - " in option_str:
                    parts = option_str.split(" - ")
                    if len(parts) == 2:
                        label_part = parts[0].strip()
                        num_part = parts[1].strip()
                        if num_part.isdigit():
                            num_val = int(num_part)
                            numeric_options.append(num_val)
                            option_labels[num_val] = label_part
                            if self.config.enable_logging:
                                print(
                                    f"        └─ Found labeled number: {num_val} = '{label_part}'"
                                )
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
                    "question_name": question.question_name,
                    "question_text": question.question_text,
                    "question_options": complete_sequence,
                }

                # Only include option_labels if we have labels for all endpoints (min and max)
                if (
                    option_labels
                    and min_val in option_labels
                    and max_val in option_labels
                ):
                    kwargs["option_labels"] = option_labels
                    if self.config.enable_logging:
                        print(
                            f"      🏷️  Using complete endpoint labels: {option_labels}"
                        )
                elif option_labels:
                    if self.config.enable_logging:
                        print(f"      ⚠️  Incomplete labels found: {option_labels}")
                        print(
                            "      ⚠️  QuestionLinearScale requires labels for both endpoints or none"
                        )
                        print("      ⚠️  Skipping labels to avoid validation error")

                if self.config.enable_logging:
                    print(
                        f"      🔧 Creating QuestionLinearScale with kwargs: {kwargs}"
                    )

                return QuestionLinearScale(**kwargs)
            else:
                if self.config.enable_logging:
                    print(
                        f"      ❌ Insufficient numeric values: {len(numeric_options)} < 2"
                    )

        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ LinearScale conversion failed: {e}")
                import traceback

                traceback.print_exc()

        return None

    def _convert_to_free_text(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Optional[Question]:
        """Convert to QuestionFreeText."""
        if self.config.enable_logging:
            print("      🔍 Converting to FreeText...")
        try:
            from edsl.questions import QuestionFreeText

            result = QuestionFreeText(
                question_name=question.question_name,
                question_text=question.question_text,
            )
            if self.config.enable_logging:
                print("      ✅ FreeText conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ FreeText conversion failed: {e}")
            return None

    def _convert_to_yes_no(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Optional[Question]:
        """Convert to QuestionYesNo."""
        if self.config.enable_logging:
            print("      🔍 Converting to YesNo...")
        try:
            from edsl.questions import QuestionYesNo

            result = QuestionYesNo(
                question_name=question.question_name,
                question_text=question.question_text,
            )
            if self.config.enable_logging:
                print("      ✅ YesNo conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ YesNo conversion failed: {e}")
            return None

    def _convert_to_likert_five(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Optional[Question]:
        """Convert to QuestionLikertFive."""
        if self.config.enable_logging:
            print("      🔍 Converting to LikertFive...")
        try:
            from edsl.questions import QuestionLikertFive

            result = QuestionLikertFive(
                question_name=question.question_name,
                question_text=question.question_text,
            )
            if self.config.enable_logging:
                print("      ✅ LikertFive conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ LikertFive conversion failed: {e}")
            return None

    def _convert_to_numerical(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Optional[Question]:
        """Convert to QuestionNumerical."""
        if self.config.enable_logging:
            print("      🔍 Converting to Numerical...")
        try:
            from edsl.questions import QuestionNumerical

            # Basic conversion - use question text and name
            kwargs = {
                "question_name": question.question_name,
                "question_text": question.question_text,
            }

            # Try to infer constraints from analysis or question text
            min_val, max_val = self._infer_numerical_constraints(question, analysis)
            if min_val is not None:
                kwargs["min_value"] = min_val
            if max_val is not None:
                kwargs["max_value"] = max_val

            if self.config.enable_logging:
                constraints = []
                if min_val is not None:
                    constraints.append(f"min={min_val}")
                if max_val is not None:
                    constraints.append(f"max={max_val}")
                constraint_str = (
                    f" with {', '.join(constraints)}" if constraints else ""
                )
                print(f"      📊 Creating numerical question{constraint_str}")

            result = QuestionNumerical(**kwargs)
            if self.config.enable_logging:
                print("      ✅ Numerical conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ Numerical conversion failed: {e}")
            return None

    def _infer_numerical_constraints(
        self, question: Question, analysis: Dict[str, Any]
    ) -> tuple:
        """Infer min/max constraints for numerical questions."""
        min_val, max_val = None, None

        # Look for year constraints
        if "year" in question.question_text.lower():
            if "birth" in question.question_text.lower():
                min_val, max_val = 1900, 2024  # Birth year range
            else:
                min_val, max_val = 1900, 2100  # General year range

        # Look for percentage constraints
        elif (
            "percentage" in question.question_text.lower()
            or "%" in question.question_text
        ):
            min_val, max_val = 0, 100

        # Look for rating constraints
        elif any(
            word in question.question_text.lower()
            for word in ["rate", "rating", "scale"]
        ):
            if "1 to 10" in question.question_text or "1-10" in question.question_text:
                min_val, max_val = 1, 10
            elif "1 to 5" in question.question_text or "1-5" in question.question_text:
                min_val, max_val = 1, 5

        # Look for count constraints (assignment, contract counts, etc.)
        elif "count" in question.question_text.lower():
            min_val = 0  # Counts are non-negative

        return min_val, max_val

    def _convert_to_multiple_choice_with_other(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Optional[Question]:
        """Convert to QuestionMultipleChoiceWithOther."""
        if self.config.enable_logging:
            print("      🔍 Converting to MultipleChoiceWithOther...")
        try:
            from edsl.questions import QuestionMultipleChoiceWithOther

            # Get options from current question or analysis
            options = getattr(question, "question_options", None) or analysis.get(
                "improved_options", []
            )
            if not options:
                if self.config.enable_logging:
                    print("      ❌ No options found for MultipleChoiceWithOther")
                return None

            # Find and separate "Other" options
            other_patterns = [
                "other",
                "specify",
                "else",
                "different",
                "not listed",
                "prefer to self-describe",
            ]
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
                question_options=regular_options,
            )
            if self.config.enable_logging:
                print("      ✅ MultipleChoiceWithOther conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ MultipleChoiceWithOther conversion failed: {e}")
            return None

    def _convert_to_budget(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Optional[Question]:
        """Convert to QuestionBudget."""
        if self.config.enable_logging:
            print("      🔍 Converting to Budget...")
        try:
            from edsl.questions import QuestionBudget

            # Get options that should represent percentages
            options = getattr(question, "question_options", None) or analysis.get(
                "improved_options", []
            )
            if not options:
                if self.config.enable_logging:
                    print("      ❌ No options found for Budget conversion")
                return None

            # Convert string options to numeric values for validation
            try:
                numeric_options = [
                    float(opt.replace("%", ""))
                    for opt in options
                    if opt.replace(".", "").replace("%", "").isdigit()
                ]
                if self.config.enable_logging:
                    print(
                        f"      📊 Found {len(numeric_options)} numeric values: {numeric_options[:10]}{'...' if len(numeric_options) > 10 else ''}"
                    )
            except (ValueError, AttributeError):
                if self.config.enable_logging:
                    print(
                        f"      ❌ Could not parse options as numbers: {options[:5]}{'...' if len(options) > 5 else ''}"
                    )
                return None

            # Use the text to infer budget categories from the question
            question_text = question.question_text.lower()

            # Try to extract categories from question text
            if "freelancer" in question_text and "ai" in question_text:
                # This appears to be about freelancer vs AI work allocation
                budget_sum_to = 100  # percentage allocation
                question_options = [
                    "Work done by freelancers",
                    "Work done with AI tools",
                ]
            else:
                # Generic budget allocation
                budget_sum_to = 100
                question_options = ["Category A", "Category B", "Other"]
                if self.config.enable_logging:
                    print(
                        "      ⚠️  Using generic categories - budget question not fully parsed"
                    )

            if self.config.enable_logging:
                print(f"      💰 Budget categories: {question_options}")
                print(f"      📊 Budget must sum to: {budget_sum_to}")

            result = QuestionBudget(
                question_name=question.question_name,
                question_text=question.question_text,
                question_options=question_options,
                budget_sum=budget_sum_to,
            )
            if self.config.enable_logging:
                print("      ✅ Budget conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ Budget conversion failed: {e}")
            return None

    def _convert_to_checkbox(
        self, question: Question, analysis: Dict[str, Any]
    ) -> Optional[Question]:
        """Convert to QuestionCheckBox."""
        if self.config.enable_logging:
            print("      🔍 Converting to CheckBox...")
        try:
            from edsl.questions import QuestionCheckBox

            # Get options from current question
            options = getattr(question, "question_options", None) or analysis.get(
                "improved_options", []
            )
            if not options:
                if self.config.enable_logging:
                    print("      ❌ No options found for CheckBox conversion")
                return None

            if self.config.enable_logging:
                print(f"      ☑️  Creating checkbox with {len(options)} options")
                if self.config.verbose_logging:
                    print(
                        f"      📋 Options: {options[:5]}{'...' if len(options) > 5 else ''}"
                    )

            result = QuestionCheckBox(
                question_name=question.question_name,
                question_text=question.question_text,
                question_options=options,
            )
            if self.config.enable_logging:
                print("      ✅ CheckBox conversion successful")
            return result
        except Exception as e:
            if self.config.enable_logging:
                print(f"      ❌ CheckBox conversion failed: {e}")
            return None

    def process_survey_sync(
        self, survey: Survey, response_data: Optional[Dict[str, List[str]]] = None
    ) -> Survey:
        """
        Synchronous wrapper for survey processing.

        Args:
            survey: Survey to process
            response_data: Optional response data for extracting options

        Returns:
            Processed survey
        """
        return asyncio.run(self.process_survey(survey, response_data))

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
                "total_changes": 0,
                "changes_by_type": {},
                "questions_modified": 0,
                "average_confidence": 0.0,
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
            "total_changes": len(self.changes),
            "changes_by_type": changes_by_type,
            "questions_modified": len(questions_modified),
            "average_confidence": (
                total_confidence / len(self.changes) if self.changes else 0.0
            ),
            "modified_questions": list(questions_modified),
        }

    def print_change_summary(self) -> None:
        """Print a formatted summary of all changes made."""
        summary = self.get_change_summary()

        print(f"\n{'='*60}")
        print("🔍 VIBE PROCESSING SUMMARY")
        print(f"{'='*60}")

        if summary["total_changes"] == 0:
            print("✅ No conversion issues found - all questions clean!")
        else:
            print("📊 Results:")
            print(f"   • Total fixes applied: {summary['total_changes']}")
            print(f"   • Questions modified: {summary['questions_modified']}")
            print(f"   • Average confidence: {summary['average_confidence']:.1%}")

            if summary["changes_by_type"]:
                print("\n🔧 Fixes by type:")
                change_icons = {"text": "🔧", "options": "⚙️", "type": "🔄"}
                for change_type, count in summary["changes_by_type"].items():
                    icon = change_icons.get(change_type, "•")
                    change_desc = {
                        "text": "HTML/formatting cleanup",
                        "options": "Option list repairs",
                        "type": "Question type conversions",
                    }.get(change_type, change_type)
                    print(f"   {icon} {change_desc}: {count}")

        if self.config.verbose_logging and self.changes:
            print("\n📋 Change Details:")
            for i, change in enumerate(self.changes, 1):
                print(f"   {i}. {change.question_name} ({change.change_type})")
                print(
                    f"      {change.reasoning[:80]}{'...' if len(change.reasoning) > 80 else ''}"
                )
                print()

        print(f"{'='*60}")
