"""This module contains the Memory class, which is a list of prior questions."""

from collections import UserList


class Memory(UserList):
    """Class for holding the questions (stored as names) that we want the the agent to have available when answering a question."""

    def __init__(self, prior_questions: list[str] = None):
        """Initialize the Memory object."""
        super().__init__(prior_questions or [])

    def add_prior_question(self, prior_question):
        """Add a prior question to the memory."""
        if prior_question not in self:
            self.append(prior_question)
        else:
            raise ValueError(f"{prior_question} is already in the memory.")

    def __repr__(self):
        """Return a string representation of the Memory object."""
        return f"Memory(prior_questions={self.data})"

    def to_dict(self):
        """Create a dictionary representation of the Memory object."""
        return {"prior_questions": self.data}

    @classmethod
    def from_dict(cls, data):
        """Create a Memory object from a dictionary."""
        return cls(**data)
