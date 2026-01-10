"""Codec for Survey entries (questions and instructions).

This module provides the SurveyCodec class for encoding and decoding
survey entries (Questions and Instructions) to/from dictionary representations.

Created: 2026-01-08
"""

from __future__ import annotations
from typing import Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from ..instructions import Instruction, ChangeInstruction


class SurveyCodec:
    """Codec for Survey entries - handles encoding/decoding questions and instructions.

    This codec is used by the Survey's Store to convert between QuestionBase/Instruction
    objects and their dictionary representations.
    """

    def encode(
        self,
        obj: Union["QuestionBase", "Instruction", "ChangeInstruction", dict[str, Any]],
    ) -> dict[str, Any]:
        """Encode a Question or Instruction to a dictionary for storage.

        Args:
            obj: A QuestionBase, Instruction, ChangeInstruction, or dict to encode.

        Returns:
            A dictionary representation suitable for storage.
        """
        if isinstance(obj, dict):
            return dict(obj)
        return obj.to_dict(add_edsl_version=False)

    def decode(
        self, data: dict[str, Any]
    ) -> Union["QuestionBase", "Instruction", "ChangeInstruction"]:
        """Decode a dictionary back to a Question or Instruction object.

        Args:
            data: Dictionary representation of a question or instruction.

        Returns:
            The reconstructed QuestionBase, Instruction, or ChangeInstruction object.
        """
        from ..questions import QuestionBase
        from ..instructions import Instruction, ChangeInstruction

        class_name = data.get("edsl_class_name", "QuestionBase")

        if class_name == "Instruction":
            return Instruction.from_dict(data)
        elif class_name == "ChangeInstruction":
            return ChangeInstruction.from_dict(data)
        elif class_name == "QuestionDict":
            from ..questions import QuestionDict

            return QuestionDict.from_dict(data)
        else:
            # Default to QuestionBase for all question types
            return QuestionBase.from_dict(data)

    def is_instruction(self, data: dict[str, Any]) -> bool:
        """Check if the encoded data represents an instruction.

        Args:
            data: Dictionary representation of an entry.

        Returns:
            True if the data represents an Instruction or ChangeInstruction.
        """
        class_name = data.get("edsl_class_name", "")
        return class_name in ("Instruction", "ChangeInstruction")


if __name__ == "__main__":
    import doctest

    doctest.testmod()
