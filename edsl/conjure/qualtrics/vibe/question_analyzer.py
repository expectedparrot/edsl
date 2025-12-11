"""
AI-powered question analysis using OpenAI API for identifying conversion issues.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from edsl.questions import Question
from edsl.questions.question_description import EDSLQuestionDescription
from edsl.base.openai_utils import create_openai_client



class EDSLQuestionInfo:
    """Information about an EDSL question."""

    exclude_list = ['budget', 'compute', 'demand', 'dict', 'dropdown', 'edsl_object', 'extract', 'file_upload', 'functional', 'markdown', 'pydantic', 'random']

    def __init__(self): 
        self._question_info = {}
        self._prompt = None

    @property
    def prompt(self):
        if self._prompt is None:
            self._prompt = ""
            from edsl.questions import question_registry
            for question_type in [qt for qt in Question.available().select('question_type').to_list() if qt not in self.exclude_list]:
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
        description="Cleaned up version of the question text, or null if no technical issues found"
    )
    improved_options: Optional[list[str]] = Field(
        None,
        description="Fixed question options list, or null if no issues found"
    )
    suggested_type: Optional[str] = Field(
        None,
        description="Better question type if current type is due to conversion error, or null"
    )
    issues_found: list[str] = Field(
        default_factory=list,
        description="List of technical conversion issues identified"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="List of specific technical fixes recommended"
    )
    confidence: float = Field(
        0.5,
        description="Confidence level in the analysis (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )
    reasoning: str = Field(
        "",
        description="Brief explanation of the technical issues and fixes"
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

    async def analyze_question(self, question: Question) -> Dict[str, Any]:
        """
        Analyze a question for conversion issues using OpenAI API.

        Args:
            question: Question to analyze

        Returns:
            Analysis results with suggested fixes
        """
        try:
            # Run the OpenAI API call in a thread to avoid blocking
            analysis = await asyncio.get_event_loop().run_in_executor(
                None, self._analyze_question_sync, question
            )
            return analysis.model_dump()
        except Exception as e:
            print(f"Analysis failed for {question.question_name}: {e}")
            return {
                'improved_text': None,
                'improved_options': None,
                'suggested_type': None,
                'issues_found': [],
                'recommendations': [],
                'confidence': 0.0,
                'reasoning': f'Analysis failed: {str(e)}'
            }

    def _analyze_question_sync(self, question: Question) -> QuestionAnalysisResult:
        """
        Synchronous analysis using OpenAI API.

        Args:
            question: Question to analyze

        Returns:
            QuestionAnalysisResult with fixes
        """
        prompt = self._create_analysis_prompt(question)

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

    def _create_analysis_prompt(self, question: Question) -> str:
        """
        Create the analysis prompt for the AI.

        Args:
            question: Question to analyze

        Returns:
            Analysis prompt string
        """
        question_info = {
            'name': question.question_name,
            'text': question.question_text,
            'type': question.__class__.__name__,
            'options': getattr(question, 'question_options', None)
        }

        edsl_question_info = EDSLQuestionInfo().prompt

        prompt = f"""
Analyze the following survey question for TECHNICAL conversion errors from Qualtrics CSV export:

Question Name: {question_info['name']}
Question Text: {question_info['text']}
Current Question Type: {question_info['type']}
Current Question Options: {question_info['options']}

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
- Incomplete option lists (e.g., [3,5] instead of [1,2,3,4,5] for a 1-5 scale)

Provide your analysis focusing only on technical conversion artifacts that need fixing.

IMPORTANT: Only suggest question types that are listed in the EDSL Question Info below. Do not suggest any question types that are not explicitly documented below.

EDSL Question Info:
{edsl_question_info}

CRITICAL: Your suggested_type field must ONLY contain question types that appear in the "Question Type:" sections above. Do not suggest any other question types.
"""
        return prompt