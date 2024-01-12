from collections import UserList


class Memory(UserList):
    """This list holds the questions (stored as names) that we want the
    the agent to have available when answering a question.
    """

    def __init__(self, prior_questions: list[str] = None):
        super().__init__(prior_questions or [])

    def add_prior_question(self, prior_question):
        if prior_question not in self:
            self.append(prior_question)
        else:
            raise ValueError(f"{prior_question} is already in the memory.")

    def __repr__(self):
        return f"Memory(prior_questions={self.data})"

    def to_dict(self):
        return {"prior_questions": self}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)
