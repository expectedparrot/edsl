"""Pseudo-indices for managing survey item ordering.

This module provides the PseudoIndices class, which manages indices for both questions 
and instructions in a survey. It assigns floating-point indices to instructions so they 
can be interspersed between integer-indexed questions while maintaining order.
"""

from collections import UserDict


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
            >>> s = Survey.example()
            >>> s._pseudo_indices.last_item_was_instruction
            False
            >>> from edsl.instructions import Instruction
            >>> s = s.add_instruction(Instruction(text="Pay attention to the following questions.", name="intro"))
            >>> s._pseudo_indices.last_item_was_instruction
            True
        """
        return isinstance(self.max_pseudo_index, float)

