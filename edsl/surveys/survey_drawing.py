"""Survey drawing and randomization functionality.

This module provides the SurveyDrawing class which handles all drawing and randomization logic
for surveys, including question option randomization, seed management, and creating randomized
survey instances. This separation allows for cleaner Survey class code and more focused
randomization logic.
"""

from __future__ import annotations
import random
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey
    from ..questions import QuestionBase


class SurveyDrawing:
    """Handles drawing and randomization logic for Survey objects.
    
    This class is responsible for managing randomization seeds, creating randomized
    survey instances, and handling question option randomization.
    """
    
    def __init__(self, survey: "Survey"):
        """Initialize the drawing handler.
        
        Args:
            survey: The survey to handle drawing for.
        """
        self.survey = survey
    
    def draw(self) -> "Survey":
        """Return a new survey with a randomly selected permutation of the options.

        This method creates a new survey instance where questions marked for randomization
        (in survey.questions_to_randomize) will have their options randomly shuffled.
        The randomization is deterministic based on a seed derived from the survey hash.

        Returns:
            Survey: A new survey with randomized question options.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> drawer = SurveyDrawing(s)
            >>> new_s = drawer.draw()
            >>> new_s.questions[0].question_options
            ['yes', 'no']
            
            With questions marked for randomization:
            
            >>> s_with_randomization = Survey.example()
            >>> s_with_randomization.questions_to_randomize = ['q0']
            >>> drawer2 = SurveyDrawing(s_with_randomization)
            >>> randomized_s = drawer2.draw()
            >>> # Options may be shuffled for q0
        """
        # Set seed if not already set (only set once per survey instance)
        if self.survey._seed is None:
            self.survey._seed = hash(self.survey)
            random.seed(self.survey._seed)  # type: ignore

        # Always create new questions to avoid sharing state between interviews
        new_questions = []
        for question in self.survey.questions:
            if question.question_name in self.survey.questions_to_randomize:
                # Call draw() on the question to randomize its options
                new_questions.append(question.draw())
            else:
                # Just duplicate the question without randomization
                new_questions.append(question.duplicate())

        # Create a new survey with the new questions
        d = self.survey.to_dict()
        d["questions"] = [q.to_dict() for q in new_questions]
        new_survey = self.survey.__class__.from_dict(d)
        
        # Preserve any non-serialized attributes from the new_questions
        for i, new_question in enumerate(new_questions):
            survey_question = new_survey.questions[i]
            if hasattr(new_question, "exception_to_throw"):
                survey_question.exception_to_throw = new_question.exception_to_throw
            if hasattr(new_question, "override_answer"):
                survey_question.override_answer = new_question.override_answer
                
        return new_survey

    def set_randomization_seed(self, seed: int) -> None:
        """Set the randomization seed for this survey.
        
        Args:
            seed: The seed value to use for randomization.
        """
        self.survey._seed = seed
        random.seed(seed)

    def add_question_to_randomize(self, question_name: str) -> "Survey":
        """Add a question to the list of questions to randomize.
        
        Args:
            question_name: The name of the question to add to randomization list.
            
        Returns:
            Survey: A new survey with the question added to randomization list.
            
        Raises:
            ValueError: If the question name is not found in the survey.
        """
        if question_name not in self.survey.question_name_to_index:
            raise ValueError(f"Question '{question_name}' not found in survey")
            
        # Create a copy of the survey with updated randomization list
        new_questions_to_randomize = self.survey.questions_to_randomize.copy()
        if question_name not in new_questions_to_randomize:
            new_questions_to_randomize.append(question_name)
            
        # Create new survey with updated randomization list
        d = self.survey.to_dict()
        d["questions_to_randomize"] = new_questions_to_randomize
        return self.survey.__class__.from_dict(d)

    def remove_question_from_randomize(self, question_name: str) -> "Survey":
        """Remove a question from the list of questions to randomize.
        
        Args:
            question_name: The name of the question to remove from randomization list.
            
        Returns:
            Survey: A new survey with the question removed from randomization list.
        """
        # Create a copy of the survey with updated randomization list
        new_questions_to_randomize = self.survey.questions_to_randomize.copy()
        if question_name in new_questions_to_randomize:
            new_questions_to_randomize.remove(question_name)
            
        # Create new survey with updated randomization list
        d = self.survey.to_dict()
        d["questions_to_randomize"] = new_questions_to_randomize
        return self.survey.__class__.from_dict(d)

    def clear_randomization(self) -> "Survey":
        """Remove all questions from the randomization list.
        
        Returns:
            Survey: A new survey with no questions marked for randomization.
        """
        d = self.survey.to_dict()
        d["questions_to_randomize"] = []
        return self.survey.__class__.from_dict(d)

    def get_randomization_info(self) -> Dict[str, Any]:
        """Get information about the current randomization settings.
        
        Returns:
            Dict containing randomization information:
                - questions_to_randomize: List of question names to randomize
                - seed: Current randomization seed (if set)
                - has_randomizable_questions: Whether any questions are marked for randomization
        """
        return {
            "questions_to_randomize": self.survey.questions_to_randomize.copy(),
            "seed": self.survey._seed,
            "has_randomizable_questions": len(self.survey.questions_to_randomize) > 0,
        }

    def is_question_randomized(self, question_name: str) -> bool:
        """Check if a specific question is marked for randomization.
        
        Args:
            question_name: The name of the question to check.
            
        Returns:
            bool: True if the question is marked for randomization, False otherwise.
        """
        return question_name in self.survey.questions_to_randomize

    @classmethod
    def create_for_survey(cls, survey: "Survey") -> "SurveyDrawing":
        """Factory method to create a drawing handler for a specific survey.
        
        Args:
            survey: The survey to create a drawing handler for.
            
        Returns:
            SurveyDrawing: A new drawing handler instance for the given survey.
        """
        return cls(survey)
