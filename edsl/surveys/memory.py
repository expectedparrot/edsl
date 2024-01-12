from collections import UserDict, UserList


class Memory(UserList):
    def __init__(self, prior_questions: list[str] = None):
        super().__init__(prior_questions or [])

    def add_prior_question(self, prior_question):
        self.append(prior_question)

    def __repr__(self):
        return f"Memory(prior_questions={self.data})"

    def to_dict(self):
        return {"prior_questions": self}

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class MemoryPlan(UserDict):
    """A survey has a memory plan that specifies what the agent should remember when answering a question.
    {focal_question: [prior_questions], focal_question: [prior_questions]}
    """

    def __init__(self, survey_questions: list[str], data=None):
        self.survey_questions = survey_questions
        super().__init__(data or {})

    def check_valid_question_name(self, question_name):
        if question_name not in self.survey_questions:
            raise ValueError(f"{question_name} is not in the survey.")

    def add_single_memory(self, focal_question: str, prior_question: str):
        self.check_valid_question_name(focal_question)
        self.check_valid_question_name(prior_question)

        if focal_question not in self:
            memory = Memory()
            memory.add_prior_question(prior_question)
            self[focal_question] = memory
        else:
            self[focal_question].add_prior_question(prior_question)

    def add_memory_collection(self, focal_question, prior_questions: list[str]):
        for question in prior_questions:
            self.add_single_memory(focal_question, question)

    def to_dict(self):
        return {
            "survey_questions": self.survey_questions,
            "data": {k: v.to_dict() for k, v in self.items()},
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            survey_questions=data["survey_questions"],
            data={k: Memory.from_dict(v) for k, v in data["data"].items()},
        )
