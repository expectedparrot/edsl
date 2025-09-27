"""
Converter to transform EDSL surveys into SurveyJS JSON format.

This module provides functionality to convert EDSL Survey objects into the JSON format
expected by SurveyJS, enabling EDSL surveys to be rendered in React applications using
the SurveyJS library.
"""

from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass


class EDSLToSurveyJSConverter:
    """Converts EDSL Survey objects to SurveyJS JSON format."""
    
    def __init__(self):
        """Initialize the converter with question type mappings."""
        # Store question type mappings using string names to avoid import issues
        self.question_type_mappings = {
            'QuestionFreeText': self._convert_free_text,
            'QuestionMultipleChoice': self._convert_multiple_choice,
            'QuestionCheckBox': self._convert_checkbox,
            'QuestionNumerical': self._convert_numerical,
            'QuestionYesNo': self._convert_yes_no,
            'QuestionLikertFive': self._convert_likert_five,
            'QuestionLinearScale': self._convert_linear_scale,
            'QuestionRank': self._convert_rank,
            'QuestionMatrix': self._convert_matrix,
        }
    
    def convert_survey(self, edsl_survey: Any, title: Optional[str] = None) -> Dict[str, Any]:
        """
        Convert an EDSL Survey to SurveyJS JSON format.
        
        Args:
            edsl_survey: The EDSL Survey object to convert
            title: Optional title for the survey
            
        Returns:
            Dictionary in SurveyJS JSON format
        """
        surveyjs_json = {
            "title": title or "EDSL Survey",
            "showProgressBar": "top",
            "showQuestionNumbers": "on",
            "questionTitleLocation": "top",
            "pages": [
                {
                    "name": "page1",
                    "elements": []
                }
            ]
        }
        
        # Convert each question
        for question in edsl_survey.questions:
            surveyjs_question = self._convert_question(question)
            if surveyjs_question:
                surveyjs_json["pages"][0]["elements"].append(surveyjs_question)
        
        return surveyjs_json
    
    def _convert_question(self, question: Any) -> Optional[Dict[str, Any]]:
        """
        Convert a single EDSL question to SurveyJS format.
        
        Args:
            question: The EDSL question to convert
            
        Returns:
            Dictionary representing the question in SurveyJS format, or None if unsupported
        """
        question_type_name = type(question).__name__
        if question_type_name in self.question_type_mappings:
            return self.question_type_mappings[question_type_name](question)
        else:
            # Fallback to text input for unsupported question types
            return self._convert_unsupported_question(question)
    
    def _convert_free_text(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionFreeText to SurveyJS text question."""
        return {
            "type": "text",
            "name": question.question_name,
            "title": question.question_text,
            "isRequired": getattr(question, 'required', False)
        }
    
    def _convert_multiple_choice(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionMultipleChoice to SurveyJS radiogroup question."""
        choices = []
        for option in question.question_options:
            if isinstance(option, str):
                choices.append({"value": option, "text": option})
            else:
                # Handle cases where options might be more complex
                choices.append({"value": str(option), "text": str(option)})
        
        return {
            "type": "radiogroup",
            "name": question.question_name,
            "title": question.question_text,
            "choices": choices,
            "isRequired": getattr(question, 'required', False)
        }
    
    def _convert_checkbox(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionCheckBox to SurveyJS checkbox question."""
        choices = []
        for option in question.question_options:
            if isinstance(option, str):
                choices.append({"value": option, "text": option})
            else:
                choices.append({"value": str(option), "text": str(option)})
        
        return {
            "type": "checkbox",
            "name": question.question_name,
            "title": question.question_text,
            "choices": choices,
            "isRequired": getattr(question, 'required', False)
        }
    
    def _convert_numerical(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionNumerical to SurveyJS text question with number validation."""
        surveyjs_question = {
            "type": "text",
            "name": question.question_name,
            "title": question.question_text,
            "inputType": "number",
            "isRequired": getattr(question, 'required', False)
        }
        
        # Add min/max validation if specified
        validators = []
        if hasattr(question, 'min_value') and question.min_value is not None:
            validators.append({"type": "numeric", "minValue": question.min_value})
        if hasattr(question, 'max_value') and question.max_value is not None:
            if validators:
                validators[0]["maxValue"] = question.max_value
            else:
                validators.append({"type": "numeric", "maxValue": question.max_value})
        
        if validators:
            surveyjs_question["validators"] = validators
            
        return surveyjs_question
    
    def _convert_yes_no(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionYesNo to SurveyJS boolean question."""
        return {
            "type": "boolean",
            "name": question.question_name,
            "title": question.question_text,
            "isRequired": getattr(question, 'required', False)
        }
    
    def _convert_likert_five(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionLikertFive to SurveyJS radiogroup with Likert scale."""
        return {
            "type": "radiogroup",
            "name": question.question_name,
            "title": question.question_text,
            "choices": [
                {"value": "strongly_disagree", "text": "Strongly Disagree"},
                {"value": "disagree", "text": "Disagree"},
                {"value": "neutral", "text": "Neutral"},
                {"value": "agree", "text": "Agree"},
                {"value": "strongly_agree", "text": "Strongly Agree"}
            ],
            "isRequired": getattr(question, 'required', False)
        }
    
    def _convert_linear_scale(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionLinearScale to SurveyJS rating question."""
        min_value = getattr(question, 'min_value', 1)
        max_value = getattr(question, 'max_value', 10)
        
        return {
            "type": "rating",
            "name": question.question_name,
            "title": question.question_text,
            "rateMin": min_value,
            "rateMax": max_value,
            "isRequired": getattr(question, 'required', False)
        }
    
    def _convert_rank(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionRank to SurveyJS ranking question."""
        choices = []
        if hasattr(question, 'question_options'):
            for option in question.question_options:
                choices.append({"value": str(option), "text": str(option)})
        
        return {
            "type": "ranking",
            "name": question.question_name,
            "title": question.question_text,
            "choices": choices,
            "isRequired": getattr(question, 'required', False)
        }
    
    def _convert_matrix(self, question: Any) -> Dict[str, Any]:
        """Convert EDSL QuestionMatrix to SurveyJS matrix question."""
        rows = []
        columns = []
        
        if hasattr(question, 'question_rows'):
            for row in question.question_rows:
                rows.append({"value": str(row), "text": str(row)})
        
        if hasattr(question, 'question_columns'):
            for col in question.question_columns:
                columns.append({"value": str(col), "text": str(col)})
        
        return {
            "type": "matrix",
            "name": question.question_name,
            "title": question.question_text,
            "rows": rows,
            "columns": columns,
            "isRequired": getattr(question, 'required', False)
        }
    
    def _convert_unsupported_question(self, question: Any) -> Dict[str, Any]:
        """Fallback conversion for unsupported question types."""
        return {
            "type": "text",
            "name": question.question_name,
            "title": f"{question.question_text} (Note: {type(question).__name__} converted to text input)",
            "isRequired": getattr(question, 'required', False)
        }


def convert_edsl_to_surveyjs(edsl_survey: Any, title: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to convert an EDSL Survey to SurveyJS JSON format.
    
    Args:
        edsl_survey: The EDSL Survey object to convert
        title: Optional title for the survey
        
    Returns:
        Dictionary in SurveyJS JSON format
    """
    converter = EDSLToSurveyJSConverter()
    return converter.convert_survey(edsl_survey, title)