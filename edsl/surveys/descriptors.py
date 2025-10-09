"""This module contains the descriptors for the classes in the edsl package."""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Not using any imported types in this file


class BaseDescriptor(ABC):
    """ABC for something."""

    @abstractmethod
    def validate(self, value: Any) -> None:
        """Validate the value. If it is invalid, raise an exception. If it is valid, do nothing."""
        pass

    def __get__(self, instance, owner):
        """Get the value of the attribute."""
        return instance.__dict__[self.name]

    def __set__(self, instance, value: Any) -> None:
        """Set the value of the attribute."""
        self.validate(value, instance)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name


class QuestionsDescriptor(BaseDescriptor):
    """Descriptor for questions."""

    def __get__(self, instance, owner):
        """Get the value of the attribute."""
        return instance.__dict__[self.name]

    def validate(self, value: Any, instance) -> None:
        """Validate the value. If it is invalid, raise an exception. If it is valid, do nothing."""
        from ..questions import QuestionBase

        if not isinstance(value, list):
            raise TypeError("Questions must be a list.")
        if not all(isinstance(question, QuestionBase) for question in value):
            raise TypeError("Questions must be a list of Question objects.")
        question_names = [question.question_name for question in value]
        if len(question_names) != len(set(question_names)):
            raise ValueError("Question names must be unique.")

    def __set__(self, instance, value: Any) -> None:
        """Set the value of the attribute."""
        import time

        # Track timing for this method
        if not hasattr(QuestionsDescriptor, "_set_timing"):
            QuestionsDescriptor._set_timing = {
                "validate": 0.0,
                "add_question": 0.0,
                "total": 0.0,
                "call_count": 0,
                "total_questions": 0,
            }

        start = time.time()

        t1 = time.time()
        self.validate(value, instance)
        QuestionsDescriptor._set_timing["validate"] += time.time() - t1

        instance.__dict__[self.name] = []

        t2 = time.time()
        for question in value:
            instance.add_question(question)
        QuestionsDescriptor._set_timing["add_question"] += time.time() - t2
        QuestionsDescriptor._set_timing["total_questions"] += len(value)

        QuestionsDescriptor._set_timing["total"] += time.time() - start
        QuestionsDescriptor._set_timing["call_count"] += 1

        # Print stats every 1000 calls
        if QuestionsDescriptor._set_timing["call_count"] % 1000 == 0:
            stats = QuestionsDescriptor._set_timing
            print(f"\n{'='*70}")
            print(f"[QUESTIONS_DESCRIPTOR.__SET__] Call #{stats['call_count']}")
            print(f"{'='*70}")
            print(f"Total time:              {stats['total']:.3f}s")
            print(f"Total questions added:   {stats['total_questions']}")
            print(f"")
            print(f"Component breakdown:")
            print(
                f"  add_question loop {stats['add_question']:.3f}s ({100*stats['add_question']/stats['total']:.1f}%)"
            )
            print(
                f"  validate          {stats['validate']:.3f}s ({100*stats['validate']/stats['total']:.1f}%)"
            )
            print(f"")
            print(f"Overall avg per call:    {stats['total']/stats['call_count']:.4f}s")
            if stats["total_questions"] > 0:
                print(
                    f"Avg per question:        {stats['add_question']/stats['total_questions']:.6f}s"
                )
            print(f"{'='*70}\n")

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name
