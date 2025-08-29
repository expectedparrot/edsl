"""Survey serialization and deserialization functionality.

This module provides the SurveySerializer class which handles converting Survey objects
to and from dictionary representations. This separation allows for cleaner Survey class
code and more focused serialization logic.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey
    from ..utilities import remove_edsl_version


class SurveySerializer:
    """Handles serialization and deserialization of Survey objects.
    
    This class is responsible for converting Survey objects to dictionary format
    (for JSON serialization, storage, etc.) and reconstructing Survey objects
    from dictionary data.
    """
    
    def __init__(self, survey: Optional["Survey"] = None):
        """Initialize the serializer.
        
        Args:
            survey: The survey to serialize. Not needed for deserialization.
        """
        self._survey = survey
    
    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize the Survey object to a dictionary for storage or transmission.

        This method converts the entire survey structure, including questions, rules,
        memory plan, and question groups, into a dictionary that can be serialized to JSON.
        This is essential for saving surveys, sharing them, or transferring them between
        systems.

        The serialized dictionary contains the complete state of the survey, allowing it
        to be fully reconstructed using the from_dict() method.

        Args:
            add_edsl_version: If True (default), includes the EDSL version and class name
                in the dictionary, which can be useful for backward compatibility when
                deserializing.

        Returns:
            Dict[str, Any]: A dictionary representation of the survey with the following keys:
                - 'questions': List of serialized questions and instructions
                - 'memory_plan': Serialized memory plan
                - 'rule_collection': Serialized rule collection
                - 'question_groups': Dictionary of question groups
                - 'questions_to_randomize': List of questions to randomize (if any)
                - 'edsl_version': EDSL version (if add_edsl_version=True)
                - 'edsl_class_name': Class name (if add_edsl_version=True)

        Raises:
            ValueError: If no survey is associated with this serializer.

        Examples:
            >>> from edsl.surveys import Survey
            >>> s = Survey.example()
            >>> serializer = SurveySerializer(s)
            >>> d = serializer.to_dict(add_edsl_version=False)
            >>> list(d.keys())
            ['questions', 'memory_plan', 'rule_collection', 'question_groups']

            With version information:

            >>> d = serializer.to_dict(add_edsl_version=True)
            >>> 'edsl_version' in d and 'edsl_class_name' in d
            True
        """
        if self._survey is None:
            raise ValueError("No survey associated with this serializer")
            
        from edsl import __version__

        # Create the base dictionary with all survey components
        d = {
            "questions": [
                q.to_dict(add_edsl_version=add_edsl_version)
                for q in self._survey._recombined_questions_and_instructions()
            ],
            "memory_plan": self._survey.memory_plan.to_dict(add_edsl_version=add_edsl_version),
            "rule_collection": self._survey.rule_collection.to_dict(
                add_edsl_version=add_edsl_version
            ),
            "question_groups": self._survey.question_groups,
        }
        
        # Add optional fields if they exist
        if self._survey.name is not None:
            d["name"] = self._survey.name

        # Include randomization information if present
        if self._survey.questions_to_randomize != []:
            d["questions_to_randomize"] = self._survey.questions_to_randomize

        # Add version information if requested
        if add_edsl_version:
            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Survey"

        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Survey":
        """Reconstruct a Survey object from its dictionary representation.

        This class method is the counterpart to to_dict() and allows you to recreate
        a Survey object from a serialized dictionary. This is useful for loading saved
        surveys, receiving surveys from other systems, or cloning surveys.

        The method handles deserialization of all survey components, including questions,
        instructions, memory plan, rules, and question groups.

        Args:
            data: A dictionary containing the serialized survey data, typically
                created by the to_dict() method.

        Returns:
            Survey: A fully reconstructed Survey object with all the original
                questions, rules, and configuration.

        Examples:
            Create a survey, serialize it, and deserialize it back:

            >>> from edsl.surveys import Survey
            >>> d = Survey.example().to_dict()
            >>> s = SurveySerializer.from_dict(d)
            >>> s == Survey.example()
            True

            Works with instructions as well:

            >>> s = Survey.example(include_instructions=True)
            >>> d = s.to_dict()
            >>> news = SurveySerializer.from_dict(d)
            >>> news == s
            True
        """
        # Import here to avoid circular imports
        from .survey import Survey
        from .memory import MemoryPlan
        from .rules import RuleCollection

        # Helper function to determine the correct class for each serialized component
        def get_class(pass_dict):
            from ..questions import QuestionBase

            if (class_name := pass_dict.get("edsl_class_name")) == "QuestionBase":
                return QuestionBase
            elif pass_dict.get("edsl_class_name") == "QuestionDict":
                from ..questions import QuestionDict
                return QuestionDict
            elif class_name == "Instruction":
                from ..instructions import Instruction
                return Instruction
            elif class_name == "ChangeInstruction":
                from ..instructions import ChangeInstruction
                return ChangeInstruction
            else:
                return QuestionBase

        # Deserialize each question and instruction
        questions = [
            get_class(q_dict).from_dict(q_dict) for q_dict in data["questions"]
        ]

        # Deserialize the memory plan
        memory_plan = MemoryPlan.from_dict(data["memory_plan"])

        # Get optional fields with defaults
        questions_to_randomize = data.get("questions_to_randomize", None)
        name = data.get("name", None)

        # Create and return the reconstructed survey
        survey = Survey(
            questions=questions,
            memory_plan=memory_plan,
            rule_collection=RuleCollection.from_dict(data["rule_collection"]),
            question_groups=data["question_groups"],
            questions_to_randomize=questions_to_randomize,
            name=name,
        )
        return survey

    @classmethod
    def create_for_survey(cls, survey: "Survey") -> "SurveySerializer":
        """Factory method to create a serializer for a specific survey.
        
        Args:
            survey: The survey to create a serializer for.
            
        Returns:
            SurveySerializer: A new serializer instance for the given survey.
        """
        return cls(survey)
