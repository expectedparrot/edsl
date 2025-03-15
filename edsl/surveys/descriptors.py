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
        self.validate(value, instance)
        instance.__dict__[self.name] = []
        for question in value:
            instance.add_question(question)

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name
