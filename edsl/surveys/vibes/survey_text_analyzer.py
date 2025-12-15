"""
Survey Text Analyzer: Classify and parse survey input text using LLMs.

This module provides functionality to:
1. Detect whether input text is a survey description or pasted survey content
2. Parse pasted survey content to extract questions and infer types
3. Generate surveys from both description and pasted text scenarios
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Optional
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..survey import Survey

from .survey_generator import SurveyGenerator
from ...base.openai_utils import create_openai_client


class SurveyTextClassification(BaseModel):
    """Pydantic model for survey text classification results."""

    input_type: str = Field(
        description="Type of input: 'description' for survey description or 'pasted_survey' for pasted survey text"
    )
    confidence: float = Field(
        description="Confidence score between 0 and 1 for the classification"
    )
    reasoning: str = Field(
        description="Explanation for why this classification was chosen"
    )


class ParsedSurveyQuestion(BaseModel):
    """Pydantic model for a parsed survey question."""

    question_text: str = Field(description="The question text, cleaned of numbering")
    question_type: str = Field(description="Inferred question type")
    question_options: Optional[List[str]] = Field(
        default=None,
        description="List of options for multiple choice/checkbox questions",
    )
    min_value: Optional[int] = Field(
        default=None, description="Minimum value for scale questions"
    )
    max_value: Optional[int] = Field(
        default=None, description="Maximum value for scale questions"
    )
    question_name: Optional[str] = Field(
        default=None, description="Generated question name"
    )


class ParsedSurvey(BaseModel):
    """Pydantic model for a complete parsed survey."""

    questions: List[ParsedSurveyQuestion] = Field(
        description="List of parsed questions"
    )
    survey_title: Optional[str] = Field(
        default=None, description="Inferred survey title"
    )
    raw_text: str = Field(description="Original input text")


class SurveyTextAnalyzer:
    """
    Analyzes and processes survey text using LLMs.

    This class can:
    - Classify whether input text is a survey description or pasted survey content
    - Parse pasted survey text to extract structured question data
    - Generate appropriate EDSL survey objects from both types of input
    """

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.3):
        """
        Initialize the survey text analyzer.

        Args:
            model: OpenAI model to use for text analysis
            temperature: Temperature for LLM generation (lower for more consistent results)
        """
        self.model = model
        self.temperature = temperature
        self.client = create_openai_client()

    def classify_input_text(self, text: str) -> SurveyTextClassification:
        """
        Classify whether input text is a survey description or pasted survey content.

        Args:
            text: Input text to classify

        Returns:
            SurveyTextClassification: Classification results with type, confidence, and reasoning
        """
        classification_prompt = self._build_classification_prompt(text)

        messages = [
            {
                "role": "system",
                "content": "You are a survey analysis expert. Analyze the input text and classify it as either a survey description or pasted survey content.",
            },
            {"role": "user", "content": classification_prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

        result_dict = json.loads(response.choices[0].message.content)
        return SurveyTextClassification(**result_dict)

    def parse_survey_text(self, text: str) -> ParsedSurvey:
        """
        Parse pasted survey text to extract structured question data.

        Args:
            text: Pasted survey text to parse

        Returns:
            ParsedSurvey: Structured representation of the parsed survey
        """
        parsing_prompt = self._build_parsing_prompt(text)

        messages = [
            {
                "role": "system",
                "content": "You are a survey parsing expert. Extract questions and infer question types from the provided survey text.",
            },
            {"role": "user", "content": parsing_prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

        result_dict = json.loads(response.choices[0].message.content)
        return ParsedSurvey(**result_dict)

    def process_survey_input(
        self,
        text: str,
        survey_cls: type,
        num_questions: Optional[int] = None,
        force_type: Optional[str] = None,
    ) -> "Survey":
        """
        Process survey input text, automatically detecting type and handling appropriately.

        Args:
            text: Input text (either description or pasted survey)
            survey_cls: Survey class to instantiate
            num_questions: Optional number of questions (only used for descriptions)
            force_type: Force interpretation as 'description' or 'pasted_survey'

        Returns:
            Survey: Generated or parsed survey instance
        """
        # Classify input type unless forced
        if force_type:
            input_type = force_type
        else:
            classification = self.classify_input_text(text)
            input_type = classification.input_type

        if input_type == "pasted_survey":
            # Parse the pasted survey content
            parsed_survey = self.parse_survey_text(text)
            return self._create_survey_from_parsed_data(parsed_survey, survey_cls)
        else:
            # Generate survey from description using existing SurveyGenerator
            generator = SurveyGenerator(model=self.model, temperature=0.7)
            survey_data = generator.generate_survey(text, num_questions=num_questions)

            # Convert to Survey instance
            questions = []
            for i, q_data in enumerate(survey_data["questions"]):
                question_obj = survey_cls._create_question_from_dict(q_data, f"q{i}")
                questions.append(question_obj)

            return survey_cls(questions)

    def _build_classification_prompt(self, text: str) -> str:
        """Build prompt for classifying input text."""
        return f"""
Analyze the following text and determine if it represents:

1. **Survey Description**: A natural language description of what kind of survey should be created
   - Examples: "Create a customer satisfaction survey for a restaurant", "I need an employee engagement survey"

2. **Pasted Survey**: Actual survey content that was copied from somewhere else
   - Examples: Numbered questions with options, formatted survey text, questions with bullet points

Text to analyze:
```
{text.strip()}
```

Respond with JSON in this exact format:
{{
    "input_type": "description" or "pasted_survey",
    "confidence": 0.0 to 1.0,
    "reasoning": "Brief explanation of why you classified it this way"
}}

Consider these indicators:
- **Description indicators**: Phrases like "survey about", "create a survey", "I need", contains goals/objectives
- **Pasted survey indicators**: Numbered questions, multiple choice options (a), b), c)), structured formatting, actual question text

Choose the most likely classification based on the content and structure.
"""

    def _build_parsing_prompt(self, text: str) -> str:
        """Build prompt for parsing survey text."""
        return f"""
Parse the following survey text and extract all questions with their inferred types.

Available question types:
- **free_text**: Open-ended questions requiring text responses
- **multiple_choice**: Questions with predefined options where user selects one
- **checkbox**: Questions with predefined options where user can select multiple
- **yes_no**: Simple yes/no questions
- **linear_scale**: Rating scales (1-5, 1-10, etc.)
- **rank**: Questions asking to rank or order items

Survey text to parse:
```
{text.strip()}
```

For each question, determine:
1. Clean question text (remove numbering/formatting)
2. Most appropriate question type
3. Options if applicable (for multiple_choice, checkbox, rank)
4. Scale range if applicable (for linear_scale)
5. Generate a concise question_name (snake_case, descriptive)

Respond with JSON in this exact format:
{{
    "questions": [
        {{
            "question_text": "Clean question text without numbering",
            "question_type": "one of the available types above",
            "question_options": ["option1", "option2"] or null,
            "min_value": 1 or null,
            "max_value": 5 or null,
            "question_name": "descriptive_snake_case_name"
        }}
    ],
    "survey_title": "Inferred title if obvious" or null,
    "raw_text": "Original text"
}}

Guidelines:
- Remove question numbering (1., 2., Q1, etc.) from question_text
- For multiple choice: look for a), b), c) or 1., 2., 3. or bullet points
- For checkbox: look for "select all", "check all", or multiple selection language
- For scales: look for "rate", "scale", number ranges like "1-5", or likert language
- For yes/no: binary questions or those ending with explicit yes/no options
- Generate meaningful question_names based on the question content
- If you see scale indicators like (1-5) or "rate from 1 to 10", use linear_scale with appropriate min/max
"""

    def _create_survey_from_parsed_data(
        self, parsed_survey: ParsedSurvey, survey_cls: type
    ) -> "Survey":
        """Create Survey instance from parsed survey data."""
        questions = []

        for i, q_data in enumerate(parsed_survey.questions):
            # Convert ParsedSurveyQuestion to dict format expected by _create_question_from_dict
            question_dict = {
                "question_text": q_data.question_text,
                "question_type": q_data.question_type,
                "question_name": q_data.question_name or f"q{i+1}",
            }

            # Add type-specific fields
            if q_data.question_options:
                question_dict["question_options"] = q_data.question_options

            if q_data.min_value is not None:
                question_dict["min_value"] = q_data.min_value

            if q_data.max_value is not None:
                question_dict["max_value"] = q_data.max_value

            # Create question object
            question_obj = survey_cls._create_question_from_dict(
                question_dict, question_dict["question_name"]
            )
            questions.append(question_obj)

        return survey_cls(questions)
