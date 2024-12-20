"""This module contains the Answers class, which is a helper class to hold the answers to a survey."""

from collections import UserDict
from edsl.data_transfer_models import EDSLResultObjectInput


class Answers(UserDict):
    """Helper class to hold the answers to a survey."""

    def add_answer(
        self, response: EDSLResultObjectInput, question: "QuestionBase"
    ) -> None:
        """Add a response to the answers dictionary."""
        answer = response.answer
        comment = response.comment
        generated_tokens = response.generated_tokens
        # record the answer
        if generated_tokens:
            self[question.question_name + "_generated_tokens"] = generated_tokens
        self[question.question_name] = answer
        if comment:
            self[question.question_name + "_comment"] = comment

    def replace_missing_answers_with_none(self, survey: "Survey") -> None:
        """Replace missing answers with None. Answers can be missing if the agent skips a question."""
        for question_name in survey.question_names:
            if question_name not in self:
                self[question_name] = None

    def to_dict(self):
        """Return a dictionary of the answers."""
        return self.data

    @classmethod
    def from_dict(cls, d):
        """Return an Answers object from a dictionary."""
        return cls(d)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
