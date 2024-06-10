from typing import Dict, List
from edsl.surveys.Survey import Survey

class CreateSurvey:

    def __init__(self, responses: Dict[str, List[str]]):
        self.responses = responses

    def __call__(self):
        "Iterates through the question keys and creates a survey."
        questions = []
        failures = {}
        for question_responses in self.responses.values():
            try:
                proposed_question = question_responses.to_question()
            except Exception as e:
                print(f"Could not convert to question: {question_responses}: {e}")
                failures[question_responses.question_name] = e
                continue
            else:
                questions.append(proposed_question)
        if len(failures) > 0:
            print(
                f"Attempted {len(self.responses.keys())} questions; there were {len(failures)} failures."
            )
        return Survey(questions), failures



