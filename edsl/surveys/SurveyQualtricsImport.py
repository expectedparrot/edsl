import json
import html
import re

from edsl import Question
from edsl import Survey

qualtrics_codes = {
    "TE": "free_text",
    "MC": "multiple_choice",
}
# TE (Text Entry): Allows respondents to input a text response.
# MC (Multiple Choice): Provides respondents with a list of options to choose from.
# DB (Descriptive Text or Information): Displays text or information without requiring a response.
# Matrix: A grid-style question where respondents can evaluate multiple items using the same set of response options.


def clean_html(raw_html):
    # Unescape HTML entities
    clean_text = html.unescape(raw_html)
    # Remove HTML tags
    clean_text = re.sub(r"<.*?>", "", clean_text)
    # Replace non-breaking spaces with regular spaces
    clean_text = clean_text.replace("\xa0", " ")
    # Optionally, strip leading/trailing spaces
    clean_text = clean_text.strip()
    return clean_text


class SurveyQualtricsImport:

    def __init__(self, qsf_file_name: str):
        self.qsf_file_name = qsf_file_name
        self.question_data = self.extract_questions_from_json()

    def create_survey(self):
        survey = Survey()
        for question in self.question_data:
            if question["question_type"] == "free_text":
                try:
                    q = Question(
                        question_type="free_text",
                        question_text=question["question_text"],
                        question_name=question["question_name"],
                    )
                except Exception as e:
                    print(f"Error creating free text question: {e}")
                    continue
            elif question["question_type"] == "multiple_choice":
                try:
                    q = Question(
                        question_type="multiple_choice",
                        question_text=question["question_text"],
                        question_name=question["question_name"],
                        question_options=question["question_options"],
                    )
                except Exception as e:
                    print(f"Error creating multiple choice question: {e}")
                    continue
            else:
                # raise ValueError(f"Unknown question type: {question['question_type']}")
                print(f"Unknown question type: {question['question_type']}")
                continue

            survey.add_question(q)

        return survey

    def extract_questions_from_json(self):
        with open(self.qsf_file_name, "r") as f:
            survey_data = json.load(f)

        questions = survey_data["SurveyElements"]

        extracted_questions = []

        for question in questions:
            if question["Element"] == "SQ":
                q_id = question["PrimaryAttribute"]
                q_text = clean_html(question["Payload"]["QuestionText"])
                q_type = qualtrics_codes.get(question["Payload"]["QuestionType"])

                options = None
                if "Choices" in question["Payload"]:
                    options = [
                        choice["Display"]
                        for choice in question["Payload"]["Choices"].values()
                    ]

                extracted_questions.append(
                    {
                        "question_name": q_id,
                        "question_text": q_text,
                        "question_type": q_type,
                        "question_options": options,
                    }
                )

        return extracted_questions


if __name__ == "__main__":
    survey_creator = SurveyQualtricsImport("example.qsf")
    survey = survey_creator.create_survey()
    info = survey.push()
    print(info)
    # questions = survey.extract_questions_from_json()
    # for question in questions:
    #    print(question)
