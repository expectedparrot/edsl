from collections import UserDict, UserList


class Memory(UserList):
    def __init__(self, prior_questions: list[str] = None):
        super().__init__(prior_questions or [])

    def add_prior_question(self, prior_question):
        if prior_question not in self:
            self.append(prior_question)
        else:
            print("Warning: prior question already in memory.")

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

    def __init__(self, survey_question_names: list[str], data=None):
        super().__init__(data or {})
        self.survey_question_names = survey_question_names

    def check_valid_question_name(self, question_name):
        if question_name not in self.survey_question_names:
            raise ValueError(f"{question_name} is not in the survey.")

    def check_order(self, focal_question, prior_question):
        focal_index = self.survey_question_names.index(focal_question)
        prior_index = self.survey_question_names.index(prior_question)
        if focal_index <= prior_index:
            raise ValueError(f"{prior_question} must come before {focal_question}.")

    def add_single_memory(self, focal_question: str, prior_question: str):
        self.check_valid_question_name(focal_question)
        self.check_valid_question_name(prior_question)
        self.check_order(focal_question, prior_question)

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
            "survey_question_names": self.survey_question_names,
            "data": {k: v.to_dict() for k, v in self.items()},
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            survey_question_names=data["survey_question_names"],
            data={k: Memory.from_dict(v) for k, v in data["data"].items()},
        )
