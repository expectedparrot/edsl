"""Survey question and instruction processing functionality.

This module provides the SurveyQuestionProcessor class which handles the separation
and processing of questions and instructions from raw input. This follows the
Command-Query Separation principle by returning all processed data without
modifying any external state.
"""

from __future__ import annotations
from collections import UserDict
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from ..instructions import Instruction, ChangeInstruction

    QuestionType = Union[QuestionBase, Instruction, ChangeInstruction]


class PseudoIndices(UserDict):
    """A dictionary of pseudo-indices for the survey.

    This class manages indices for both questions and instructions in a survey. It assigns
    floating-point indices to instructions so they can be interspersed between integer-indexed
    questions while maintaining order. This is crucial for properly serializing and deserializing
    surveys with both questions and instructions.

    Attributes:
        data (dict): The underlying dictionary mapping item names to their pseudo-indices.
    """

    @property
    def max_pseudo_index(self) -> float:
        """Return the maximum pseudo index in the survey.

        Returns:
            float: The highest pseudo-index value currently assigned, or -1 if empty.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> Survey.example()._pseudo_indices.max_pseudo_index
            2
        """
        if len(self) == 0:
            return -1
        return max(self.values())

    @property
    def last_item_was_instruction(self) -> bool:
        """Determine if the last item added to the survey was an instruction.

        This is used to determine the pseudo-index of the next item added to the survey.
        Instructions are assigned floating-point indices (e.g., 1.5) while questions
        have integer indices.

        Returns:
            bool: True if the last added item was an instruction, False otherwise.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s._pseudo_indices.last_item_was_instruction
            False
            >>> from edsl.instructions import Instruction
            >>> s = s.add_instruction(Instruction(text="Pay attention to the following questions.", name="intro"))
            >>> s._pseudo_indices.last_item_was_instruction
            True
        """
        return isinstance(self.max_pseudo_index, float)


class ProcessedQuestions:
    """Container for processed questions and instructions data.
    
    This class holds the results of processing raw questions/instructions input,
    providing a clean interface for accessing the separated components.
    """
    
    def __init__(
        self,
        true_questions: List["QuestionBase"],
        instruction_names_to_instructions: Dict[str, Union["Instruction", "ChangeInstruction"]],
        pseudo_indices: Dict[str, float],
    ):
        """Initialize the processed questions container.
        
        Args:
            true_questions: List of actual question objects (not instructions)
            instruction_names_to_instructions: Mapping of instruction names to instruction objects
            pseudo_indices: Mapping of item names to their pseudo-indices for ordering
        """
        self.true_questions = true_questions
        self.instruction_names_to_instructions = instruction_names_to_instructions
        self.pseudo_indices = PseudoIndices(pseudo_indices)

    def unpack(self) -> Tuple[List["QuestionBase"], Dict[str, Union["Instruction", "ChangeInstruction"]], PseudoIndices]:
        """Unpack the processed data into a tuple.
        
        Returns:
            Tuple containing:
                - true_questions: List of question objects
                - instruction_names_to_instructions: Dictionary of instructions
                - pseudo_indices: PseudoIndices object for ordering
        """
        return self.true_questions, self.instruction_names_to_instructions, self.pseudo_indices


class SurveyQuestionProcessor:
    """Handles processing of raw questions and instructions for Survey objects.
    
    This class is responsible for separating questions from instructions and
    creating the appropriate data structures, following Command-Query Separation
    by returning all data without modifying external state.
    """
    
    @staticmethod
    def process_raw_questions(
        questions: Optional[List["QuestionType"]], 
        survey_for_handler: Optional["Survey"] = None
    ) -> ProcessedQuestions:
        """Process raw questions and instructions into separated components.
        
        This method takes a list of mixed questions and instructions and separates them
        into their appropriate data structures. It returns all processed data without
        modifying any external state, following Command-Query Separation principle.
        
        Args:
            questions: A list of question objects and/or instruction objects to process.
            survey_for_handler: Optional survey instance needed by InstructionHandler.
                If None, a temporary survey will be created for processing.
        
        Returns:
            ProcessedQuestions: Container with separated questions, instructions, and indices.
            
        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> from edsl.questions import QuestionFreeText
            >>> from edsl.instructions import Instruction
            >>> 
            >>> q1 = QuestionFreeText(question_name="q1", question_text="What's your name?")
            >>> inst = Instruction(name="intro", text="Please answer carefully")
            >>> q2 = QuestionFreeText(question_name="q2", question_text="What's your age?")
            >>> 
            >>> processed = SurveyQuestionProcessor.process_raw_questions([inst, q1, q2])
            >>> len(processed.true_questions)
            2
            >>> len(processed.instruction_names_to_instructions)
            1
            >>> list(processed.pseudo_indices.keys())
            ['intro', 'q1', 'q2']
        """
        from ..instructions import InstructionHandler
        
        # Create a temporary survey for the handler if none provided
        if survey_for_handler is None:
            # Import here to avoid circular imports
            from .survey import Survey
            survey_for_handler = Survey.__new__(Survey)  # Create without calling __init__
        
        handler = InstructionHandler(survey_for_handler)
        result = handler.separate_questions_and_instructions(questions or [])

        # Handle result safely for mypy - this logic is preserved from the original
        if (
            hasattr(result, "true_questions")
            and hasattr(result, "instruction_names_to_instructions")
            and hasattr(result, "pseudo_indices")
        ):
            # It's the SeparatedComponents dataclass
            return ProcessedQuestions(
                true_questions=result.true_questions,  # type: ignore
                instruction_names_to_instructions=result.instruction_names_to_instructions,  # type: ignore
                pseudo_indices=result.pseudo_indices,  # type: ignore
            )
        else:
            # For older versions that return a tuple
            # This is a hacky way to get mypy to allow tuple unpacking of an Any type
            result_list = list(result)  # type: ignore
            if len(result_list) == 3:
                true_q = result_list[0]
                inst_dict = result_list[1]
                pseudo_idx = result_list[2]
                return ProcessedQuestions(
                    true_questions=true_q,
                    instruction_names_to_instructions=inst_dict,
                    pseudo_indices=pseudo_idx,
                )
            else:
                raise TypeError(
                    f"Unexpected result type from separate_questions_and_instructions: {type(result)}"
                )

    @staticmethod
    def create_empty_processed_questions() -> ProcessedQuestions:
        """Create an empty ProcessedQuestions instance.
        
        Returns:
            ProcessedQuestions: Empty container with no questions or instructions.
        """
        return ProcessedQuestions(
            true_questions=[],
            instruction_names_to_instructions={},
            pseudo_indices={},
        )
