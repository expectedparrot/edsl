from typing import Dict, List
from edsl.surveys.Survey import Survey
from edsl.conjure.InputData import InputData


class CreateSurvey:
    def __init__(self, input_data: InputData):
        self.input_data = input_data

    def __call__(self):
        "Iterates through the question keys and creates a survey."
        questions = []
        failures = {}
        for question_name in self.input_data.question_names:
            question_text = self.input_data.names_to_texts[question_name]

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
