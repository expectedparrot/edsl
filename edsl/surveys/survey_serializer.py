"""Survey JSONL serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Generator, Iterable, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey


class SurveySerializer:
    """JSONL serialization for Survey objects.

    JSONL format:
      - Line 1: metadata header with ``__header__: true``, class name, count,
        plus ``memory_plan``, ``rule_collection``, ``question_groups``, and
        optional ``name`` / ``questions_to_randomize``.
      - Lines 2+: one question/instruction per line
        (``to_dict(add_edsl_version=False)``).
    """

    def __init__(self, survey: "Survey") -> None:
        self._survey = survey

    # ------------------------------------------------------------------
    # export
    # ------------------------------------------------------------------

    def _build_metadata(self, add_edsl_version: bool = True) -> dict:
        s = self._survey
        meta: dict = {
            "__header__": True,
            "edsl_class_name": "Survey",
            "n_questions": len(s._recombined_questions_and_instructions()),
            "memory_plan": s.memory_plan.to_dict(add_edsl_version=False),
            "rule_collection": s.rule_collection.to_dict(add_edsl_version=False),
            "question_groups": s.question_groups,
        }
        if s.name is not None:
            meta["name"] = s.name
        if s.questions_to_randomize:
            meta["questions_to_randomize"] = s.questions_to_randomize
        if add_edsl_version:
            from edsl import __version__

            meta["edsl_version"] = __version__
        return meta

    def to_jsonl_rows(self, add_edsl_version: bool = True) -> Generator[str, None, None]:
        """Yield one JSON string per line — header then one question per line."""
        yield json.dumps(self._build_metadata(add_edsl_version))
        for q in self._survey._recombined_questions_and_instructions():
            yield json.dumps(q.to_dict(add_edsl_version=False))

    def to_jsonl(self, filename: Union[str, Path, None] = None) -> Optional[str]:
        """Export as JSONL string or write to *filename*.

        Examples:
            >>> from edsl.surveys import Survey
            >>> sv = Survey.example()
            >>> text = sv.to_jsonl()
            >>> lines = text.strip().splitlines()
            >>> len(lines)
            4
            >>> import json; json.loads(lines[0])['n_questions']
            3
        """
        if filename is not None:
            with open(filename, "w") as f:
                for row in self.to_jsonl_rows():
                    f.write(row + "\n")
            return None
        return "\n".join(self.to_jsonl_rows()) + "\n"

    # ------------------------------------------------------------------
    # import (static — no instance needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _open_lines(source: Union[str, Path, Iterable[str]]) -> Iterable[str]:
        """Normalise *source* into an iterable of lines."""
        if isinstance(source, Path):
            with open(source, "r") as fh:
                yield from fh
            return

        if isinstance(source, str):
            if "\n" not in source.rstrip("\n"):
                candidate = Path(source)
                try:
                    if candidate.is_file():
                        with open(candidate, "r") as fh:
                            yield from fh
                        return
                except OSError:
                    pass
            yield from source.splitlines()
        else:
            yield from source

    @staticmethod
    def from_jsonl(source: Union[str, Path, Iterable[str]]) -> "Survey":
        """Create a Survey from a JSONL source.

        Examples:
            >>> from edsl.surveys import Survey
            >>> sv = Survey.example()
            >>> sv2 = Survey.from_jsonl(sv.to_jsonl())
            >>> sv == sv2
            True
        """
        from ..questions import QuestionBase
        from ..instructions import Instruction, ChangeInstruction
        from .memory.memory_plan import MemoryPlan
        from .rules.rule_collection import RuleCollection
        from .survey import Survey

        def get_class(d):
            cn = d.get("edsl_class_name")
            if cn == "Instruction":
                return Instruction
            elif cn == "ChangeInstruction":
                return ChangeInstruction
            elif cn == "QuestionDict":
                from ..questions import QuestionDict
                return QuestionDict
            return QuestionBase

        lines = SurveySerializer._open_lines(source)
        line_iter = iter(lines)
        meta = json.loads(next(line_iter))

        questions = []
        for line in line_iter:
            if line.strip():
                d = json.loads(line)
                questions.append(get_class(d).from_dict(d))

        memory_plan = MemoryPlan.from_dict(meta["memory_plan"])

        rule_collection_data = meta["rule_collection"]
        if not rule_collection_data.get("question_name_to_index"):
            rule_collection_data["question_name_to_index"] = {
                q.question_name: i for i, q in enumerate(questions)
            }
        rule_collection = RuleCollection.from_dict(rule_collection_data)

        return Survey(
            questions=questions,
            memory_plan=memory_plan,
            rule_collection=rule_collection,
            question_groups=meta.get("question_groups", {}),
            questions_to_randomize=meta.get("questions_to_randomize"),
            name=meta.get("name"),
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod()
