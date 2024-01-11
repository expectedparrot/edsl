from abc import ABC, abstractmethod
from typing import Any
from edsl.questions import Question


class BaseDescriptor(ABC):
    """ABC for something."""

    @abstractmethod
    def validate(self, value: Any) -> None:
        """Validates the value. If it is invalid, raises an exception. If it is valid, does nothing."""
        pass

    def __get__(self, instance, owner):
        """"""
        return instance.__dict__[self.name]

    def __set__(self, instance, value: Any) -> None:
        self.validate(value, instance)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name: str) -> None:
        self.name = "_" + name


class QuestionsDescriptor(BaseDescriptor):
    """Descriptor for questions."""

    def __get__(self, instance, owner):
        """"""
        return instance.__dict__[self.name]

    def validate(self, value: Any, instance) -> None:
        if not isinstance(value, list):
            raise TypeError("Questions must be a list.")
        if not all(isinstance(question, Question) for question in value):
            raise TypeError("Questions must be a list of Question objects.")
        question_names = [question.question_name for question in value]
        if len(question_names) != len(set(question_names)):
            raise ValueError("Question names must be unique.")

    def __set__(self, instance, value: Any) -> None:
        self.validate(value, instance)
        instance.__dict__[self.name] = []
        for question in value:
            instance.add_question(question)

    def __set_name__(self, owner, name: str) -> None:
        self.name = "_" + name
