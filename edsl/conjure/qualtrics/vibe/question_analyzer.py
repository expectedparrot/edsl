"""
AI-powered question analysis using OpenAI API for identifying conversion issues.
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from edsl.questions import Question
from edsl.questions.question_description import EDSLQuestionDescription
from edsl.base.openai_utils import create_openai_client


class EDSLQuestionInfo:
    """Information about an EDSL question."""

    exclude_list = [
        "budget",
        "compute",
        "demand",
        "dict",
        "dropdown",
        "edsl_object",
        "extract",
        "file_upload",
        "functional",
        "markdown",
        "pydantic",
        "random",
    ]

    def __init__(self):
        self._question_info = {}
        self._prompt = None

    @property
    def prompt(self):
        if self._prompt is None:
            self._prompt = ""
            from edsl.questions import question_registry

            for question_type in [
                qt
                for qt in Question.available().select("question_type").to_list()
                if qt not in self.exclude_list
            ]:
                question_class = question_registry.get_question_class(question_type)
                info = question_class.__init__.__doc__
                self._question_info[question_type] = info
                self._prompt += f"Question Type: {question_type}\n{info}\n"
            return self._prompt
        else:
            return self._prompt


class QuestionAnalysisResult(BaseModel):
    """Structured result from question analysis."""

    improved_text: Optional[str] = Field(
        None,
        description="Cleaned up version of the question text, or null if no technical issues found",
    )
    improved_options: Optional[list[str]] = Field(
        None, description="Fixed question options list, or null if no issues found"
    )
    suggested_type: Optional[str] = Field(
        None,
        description="Better question type if current type is due to conversion error, or null",
    )
    issues_found: list[str] = Field(
        default_factory=list,
        description="List of technical conversion issues identified",
    )
    recommendations: list[str] = Field(
        default_factory=list, description="List of specific technical fixes recommended"
    )
    confidence: float = Field(
        0.5, description="Confidence level in the analysis (0.0 to 1.0)", ge=0.0, le=1.0
    )
    reasoning: str = Field(
        "", description="Brief explanation of the technical issues and fixes"
    )


class QuestionValidationResult(BaseModel):
    """Structured result from question validation."""

    is_sensible: bool = Field(
        True,
        description="Whether the question configuration makes sense overall",
    )
    issues_found: list[str] = Field(
        default_factory=list,
        description="List of issues with the current question configuration",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="List of specific suggestions to improve the question",
    )
    confidence: float = Field(
        0.5,
        description="Confidence level in the validation assessment (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        "", description="Explanation of why the question is or isn't sensible"
    )


class QuestionAnalyzer:
    """Analyzes and fixes survey questions using OpenAI API for conversion issues."""

    def __init__(self, config):
        """
        Initialize the question analyzer.

        Args:
            config: VibeConfig instance with analysis settings
        """
        self.config = config
        self._client = None

    @property
    def client(self):
        """Get or create the OpenAI client."""
        if self._client is None:
            self._client = create_openai_client()
        return self._client

    async def analyze_question(
        self, question: Question, response_data: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a question for conversion issues using OpenAI API.

        Args:
            question: Question to analyze
            response_data: Optional response data for extracting options

        Returns:
            Analysis results with suggested fixes
        """
        try:
            # Run the OpenAI API call in a thread to avoid blocking
            analysis = await asyncio.get_event_loop().run_in_executor(
                None, self._analyze_question_sync, question, response_data
            )
            return analysis.model_dump()
        except Exception as e:
            print(f"Analysis failed for {question.question_name}: {e}")
            return {
                "improved_text": None,
                "improved_options": None,
                "suggested_type": None,
                "issues_found": [],
                "recommendations": [],
                "confidence": 0.0,
                "reasoning": f"Analysis failed: {str(e)}",
            }

    def _analyze_question_sync(
        self, question: Question, response_data: Optional[Dict[str, List[str]]] = None
    ) -> QuestionAnalysisResult:
        """
        Synchronous analysis using OpenAI API.

        Args:
            question: Question to analyze
            response_data: Optional response data for extracting options

        Returns:
            QuestionAnalysisResult with fixes
        """
        prompt = self._create_analysis_prompt(question, response_data)

        response = self.client.responses.parse(
            model=self.config.model or "gpt-4o",
            input=[
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": prompt},
            ],
            text_format=QuestionAnalysisResult,
            temperature=self.config.temperature,
        )

        return response.output_parsed

    def _create_analysis_prompt(
        self, question: Question, response_data: Optional[Dict[str, List[str]]] = None
    ) -> str:
        """
        Create the analysis prompt for the AI.

        Args:
            question: Question to analyze
            response_data: Optional response data for extracting options

        Returns:
            Analysis prompt string
        """
        question_info = {
            "name": question.question_name,
            "text": question.question_text,
            "type": question.__class__.__name__,
            "options": getattr(question, "question_options", None),
            "items": getattr(question, "question_items", None),
            "columns": getattr(question, "question_columns", None),
            "min_value": getattr(question, "min_value", None),
            "max_value": getattr(question, "max_value", None),
        }

        edsl_question_info = EDSLQuestionInfo().prompt

        # Check if we have response data for this question
        actual_responses = None
        if response_data and question.question_name in response_data:
            actual_responses = response_data[question.question_name]

        response_data_section = ""
        if actual_responses:
            # Analyze response data to provide statistical insights
            response_analysis = self._analyze_response_data(actual_responses)
            response_data_section = f"""

ACTUAL RESPONSE DATA ANALYSIS:
{response_analysis}

Use this analysis to determine the correct question type and options.
"""

        prompt = f"""
Analyze the following survey question for TECHNICAL conversion errors from Qualtrics CSV export:

Question Name: {question_info['name']}
Question Text: {question_info['text']}
Current Question Type: {question_info['type']}
Current Question Options: {question_info['options']}
Current Question Items: {question_info['items']}
Current Question Columns: {question_info['columns']}
Current Scale Range: {question_info['min_value']}-{question_info['max_value']}{response_data_section}

ANALYSIS FOCUS:
Look ONLY for technical conversion issues such as:
1. HTML tags, entities, or artifacts (e.g., <p>, <b>, &nbsp;, &lt;, etc.)
2. Encoding problems or corrupted characters
3. Question type misclassification due to conversion errors
4. Corrupted or incomplete option lists from CSV export issues
5. Structural problems from matrix question flattening

Do NOT fix grammar, spelling, capitalization, or language style - preserve the original author's wording completely.

Common conversion errors to check:
- Rating scales (1-5, 1-10) should be QuestionLinearScale, not QuestionMultipleChoice
- Agree/disagree statements should be QuestionLikertFive, not QuestionMultipleChoice
- Yes/No questions should be QuestionYesNo, not QuestionMultipleChoice
- Open text should be QuestionFreeText, not QuestionMultipleChoice
- Text questions with common categorical responses should be QuestionMultipleChoiceWithOther
- Incomplete option lists (e.g., [3,5] instead of [1,2,3,4,5] for a 1-5 scale)
- IMPORTANT: Do NOT convert QuestionMatrix to QuestionMatrixEntry if the QuestionMatrix has proper structure (question_items as scenarios, question_options as rating scale numbers, option_labels as scale endpoints). QuestionMatrix is correct for rating multiple scenarios on a scale.

Provide your analysis focusing only on technical conversion artifacts that need fixing.

IMPORTANT: Only suggest question types that are listed in the EDSL Question Info below. Do not suggest any question types that are not explicitly documented below.

EDSL Question Info:
{edsl_question_info}

CRITICAL: Your suggested_type field must ONLY contain question types that appear in the "Question Type:" sections above. Do not suggest any other question types.
"""
        return prompt

    def _analyze_response_data(self, responses: List[str]) -> str:
        """
        Analyze response data to provide statistical insights for question type determination.

        Args:
            responses: List of response values

        Returns:
            Formatted analysis string
        """
        if not responses:
            return "No response data available."

        # Basic stats
        total_responses = len(responses)
        unique_responses = list(set(responses))
        unique_count = len(unique_responses)

        # Analyze response types
        numeric_responses = []
        text_responses = []
        empty_responses = 0

        for response in responses:
            if not response or str(response).strip() == "":
                empty_responses += 1
                continue

            response_str = str(response).strip()
            try:
                # Try to parse as number
                float(response_str)
                numeric_responses.append(response_str)
            except ValueError:
                text_responses.append(response_str)

        # Calculate percentages
        numeric_pct = (
            len(numeric_responses) / total_responses * 100 if total_responses > 0 else 0
        )
        text_pct = (
            len(text_responses) / total_responses * 100 if total_responses > 0 else 0
        )
        empty_pct = (
            empty_responses / total_responses * 100 if total_responses > 0 else 0
        )

        # Sort responses by frequency for better insights
        response_counts = {}
        for response in responses:
            response_counts[response] = response_counts.get(response, 0) + 1

        # Get most common responses
        sorted_responses = sorted(
            response_counts.items(), key=lambda x: x[1], reverse=True
        )
        most_common = sorted_responses[:10]

        analysis = f"""
Total responses: {total_responses}
Unique values: {unique_count}

RESPONSE TYPE BREAKDOWN:
• Numeric responses: {len(numeric_responses)} ({numeric_pct:.1f}%)
• Text responses: {len(text_responses)} ({text_pct:.1f}%)
• Empty responses: {empty_responses} ({empty_pct:.1f}%)

MOST COMMON RESPONSES (with frequency):
{[f"{resp}: {count}x" for resp, count in most_common]}

ALL UNIQUE VALUES (up to 20):
{unique_responses[:20]}"""

        # Additional analysis for numeric responses
        if numeric_responses:
            try:
                numeric_values = [float(x) for x in numeric_responses]
                min_val = min(numeric_values)
                max_val = max(numeric_values)

                # Statistical analysis
                import statistics

                mean_val = statistics.mean(numeric_values) if numeric_values else 0
                median_val = statistics.median(numeric_values) if numeric_values else 0

                # Pattern analysis
                percentage_like = all(0 <= x <= 100 for x in numeric_values)
                int_values = [x for x in numeric_values if x == int(x)]
                all_integers = len(int_values) == len(numeric_values)
                small_range = (max_val - min_val) <= 10

                # Check for common scale patterns
                unique_numeric = sorted(list(set(numeric_values)))
                consecutive = (
                    all(
                        unique_numeric[i] == unique_numeric[i - 1] + 1
                        for i in range(1, len(unique_numeric))
                    )
                    if len(unique_numeric) > 1
                    else False
                )

                analysis += f"""

NUMERIC ANALYSIS:
• Range: {min_val} - {max_val}
• Mean: {mean_val:.2f}, Median: {median_val:.2f}
• All integers: {all_integers}
• Small range (≤10): {small_range}
• Appears to be percentage (0-100 range): {percentage_like}
• Consecutive values: {consecutive}
• Unique numeric values: {unique_numeric}"""

            except Exception as e:
                analysis += f"\n• Numeric analysis failed: {e}"

        # Analysis for text responses
        if text_responses:
            unique_text = list(set(text_responses))

            # Get most common text responses
            text_counts = {}
            for text in text_responses:
                text_counts[text] = text_counts.get(text, 0) + 1
            sorted_text = sorted(text_counts.items(), key=lambda x: x[1], reverse=True)

            analysis += f"""

TEXT ANALYSIS:
• Unique text responses: {len(unique_text)}
• Most common text responses: {[(text, count) for text, count in sorted_text[:5]]}
• All unique text values: {unique_text[:10]}"""

            # Pattern analysis (without making recommendations)
            likert_keywords = [
                "agree",
                "disagree",
                "strongly",
                "neutral",
                "somewhat",
                "likely",
                "unlikely",
            ]
            yesno_keywords = ["yes", "no"]
            scale_keywords = [
                "never",
                "rarely",
                "sometimes",
                "often",
                "always",
                "poor",
                "fair",
                "good",
                "excellent",
            ]

            text_lower_joined = " ".join([t.lower() for t in unique_text])
            has_likert = any(
                keyword in text_lower_joined for keyword in likert_keywords
            )
            has_yesno = any(keyword in text_lower_joined for keyword in yesno_keywords)
            has_scale = any(keyword in text_lower_joined for keyword in scale_keywords)

            # Length analysis
            avg_length = (
                sum(len(text) for text in unique_text) / len(unique_text)
                if unique_text
                else 0
            )
            short_responses = sum(1 for text in unique_text if len(text) < 20)
            long_responses = sum(1 for text in unique_text if len(text) > 100)

            analysis += f"""
• Average text length: {avg_length:.1f} characters
• Short responses (<20 chars): {short_responses}
• Long responses (>100 chars): {long_responses}
• Contains likert-style keywords: {has_likert}
• Contains yes/no style responses: {has_yesno}
• Contains scale keywords: {has_scale}"""

        return analysis.strip()

    async def validate_question(
        self, question: Question, response_data: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Validate a question's final configuration for sensibility using LLM.

        Args:
            question: Final question to validate
            response_data: Optional response data for context

        Returns:
            Validation results with suggested fixes
        """
        try:
            # Run the validation in a thread to avoid blocking
            validation = await asyncio.get_event_loop().run_in_executor(
                None, self._validate_question_sync, question, response_data
            )
            return validation.model_dump()
        except Exception as e:
            print(f"Validation failed for {question.question_name}: {e}")
            return {
                "is_sensible": True,  # Default to sensible if validation fails
                "issues_found": [],
                "suggestions": [],
                "confidence": 0.0,
                "reasoning": f"Validation failed: {str(e)}",
            }

    def _validate_question_sync(
        self, question: Question, response_data: Optional[Dict[str, List[str]]] = None
    ) -> QuestionValidationResult:
        """
        Synchronous validation using OpenAI API.

        Args:
            question: Question to validate
            response_data: Optional response data for context

        Returns:
            QuestionValidationResult with validation assessment
        """
        prompt = self._create_validation_prompt(question, response_data)

        response = self.client.responses.parse(
            model=self.config.model or "gpt-4o",
            input=[
                {"role": "system", "content": self._get_validation_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            text_format=QuestionValidationResult,
            temperature=0.1,  # Lower temperature for more consistent validation
        )

        return response.output_parsed

    def _get_validation_system_prompt(self) -> str:
        """Get the system prompt for question validation."""
        return """You are an expert survey methodologist reviewing question configurations for sensibility and best practices.

Your task is to evaluate whether a survey question is properly configured - whether it makes sense as presented, has the right question type, appropriate options, and follows good survey design principles.

Focus on:
1. QUESTION TYPE APPROPRIATENESS: Does the question type match what's being asked?
2. OPTION QUALITY: Are the options logical, complete, mutually exclusive, and properly ordered?
3. SURVEY DESIGN BEST PRACTICES: Clear wording, no leading questions, appropriate response scales
4. DATA ALIGNMENT: Do the actual response patterns support the chosen question configuration?

Common issues to check:
- Numerical questions that should use ranges instead of exact numbers
- Multiple choice questions with options that aren't mutually exclusive
- Scale questions with illogical ordering (e.g., education levels out of sequence)
- Missing "Other" or "Prefer not to answer" options where appropriate
- Question types that don't match the actual response format people used
- DATA CORRUPTION: Options like "4-Feb", "1-May", etc. that are clearly Excel date formatting errors
- NONSENSICAL OPTIONS: Options that don't make sense for the question being asked
- INCOMPLETE OPTION SETS: Missing obvious options (e.g., missing age ranges, education levels)
"""

    def _create_validation_prompt(
        self, question: Question, response_data: Optional[Dict[str, List[str]]] = None
    ) -> str:
        """
        Create the validation prompt for the AI.

        Args:
            question: Question to validate
            response_data: Optional response data for context

        Returns:
            Validation prompt string
        """
        question_info = {
            "name": question.question_name,
            "text": question.question_text,
            "type": question.__class__.__name__,
            "options": getattr(question, "question_options", None),
            "items": getattr(question, "question_items", None),
            "columns": getattr(question, "question_columns", None),
            "min_value": getattr(question, "min_value", None),
            "max_value": getattr(question, "max_value", None),
        }

        # Include response data analysis if available
        response_context = ""
        if response_data and question.question_name in response_data:
            actual_responses = response_data[question.question_name]
            response_analysis = self._analyze_response_data(actual_responses)
            response_context = f"""

ACTUAL RESPONSE DATA CONTEXT:
{response_analysis}
"""

        prompt = f"""
Please validate this survey question configuration for sensibility and best practices:

QUESTION TO VALIDATE:
Question Name: {question_info['name']}
Question Text: {question_info['text']}
Question Type: {question_info['type']}
Question Options: {question_info['options']}
Question Items: {question_info['items']}
Question Columns: {question_info['columns']}
Scale Range: {question_info['min_value']}-{question_info['max_value']}{response_context}

VALIDATION CHECKLIST:
1. Does the question type appropriately match what's being asked?
2. Are the options (if any) complete, logical, and properly ordered?
3. Does the configuration align with how people actually responded?
4. Are there any survey design best practice violations?
5. Would a respondent be able to answer this question clearly and accurately?

Provide your assessment of whether this question configuration makes sense and any suggestions for improvement.
"""
        return prompt
