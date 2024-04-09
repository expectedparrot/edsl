"""This module contains the Answers class, which is a helper class to hold the answers to a survey."""
from collections import UserDict
from rich.table import Table


class Answers(UserDict):
    """Helper class to hold the answers to a survey."""

    def add_answer(self, response, question) -> None:
        """Add a response to the answers dictionary."""
        answer = response.get("answer")
        comment = response.pop("comment", None)
        # record the answer
        self[question.question_name] = answer
        if comment:
            self[question.question_name + "_comment"] = comment

    def replace_missing_answers_with_none(self, survey) -> None:
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

    def rich_print(self):
        """Display an object as a table."""
        table = Table(title="Answers")
        table.add_column("Attribute", style="bold")
        table.add_column("Value")

        to_display = self
        for attr_name, attr_value in to_display.items():
            table.add_row(attr_name, repr(attr_value))

        return table
