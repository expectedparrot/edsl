from collections import UserDict


class Answers(UserDict):
    "Helper class to hold the answers to a survey"

    def add_answer(self, response, question) -> None:
        "Adds a response to the answers dictionary"
        answer = response.get("answer")
        comment = response.pop("comment", None)
        # record the answer
        self[question.question_name] = answer
        if comment:
            self[question.question_name + "_comment"] = comment

    def replace_missing_answers_with_none(self, survey) -> None:
        "Replaces missing answers with None. Answers can be missing if the agent skips a question."
        for question_name in survey.question_names:
            if question_name not in self:
                self[question_name] = None

    def to_dict(self):
        "Returns a dictionary of the answers"
        return self.data

    @classmethod
    def from_dict(cls, d):
        "Returns an Answers object from a dictionary"
        return cls(d)
