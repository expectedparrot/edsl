import json
import html
import re

from edsl import Question
from edsl import Survey

qualtrics_codes = {
    "TE": "free_text",
    "MC": "multiple_choice",
    "Matrix": "matrix",
    "DB": "instruction",  # not quite right, but for now
    "Timing": "free_text",  # not quite right, but for now
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


class QualtricsQuestion:
    def __init__(self, question_json, debug=False):
        self.debug = debug
        self.question_json = question_json
        if self.element != "SQ":
            raise ValueError("Invalid question element type")

    @property
    def element(self):
        return self.question_json["Element"]

    @property
    def selector(self):
        return self.question_json.get("Selector", None)

    @property
    def question_name(self):
        return self.question_json["PrimaryAttribute"]

    @property
    def question_text(self):
        return clean_html(self.question_json["Payload"]["QuestionText"])

    @property
    def raw_question_type(self):
        return self.question_json["Payload"]["QuestionType"]

    @property
    def question_type(self):
        q_type = qualtrics_codes.get(self.raw_question_type, None)
        if q_type is None:
            print(f"Unknown question type: {self.raw_question_type}")
            return None
        return q_type

    @property
    def choices(self):
        if "Choices" in self.question_json["Payload"]:
            return [
                choice["Display"]
                for choice in self.question_json["Payload"]["Choices"].values()
            ]
        return None

    @property
    def answers(self):
        if "Answers" in self.question_json["Payload"]:
            return [
                choice["Display"]
                for choice in self.question_json["Payload"]["Choices"].values()
            ]
        return None

    def to_edsl(self):
        if self.question_type == "instruction":
            from edsl import Instruction

            return [Instruction(text=self.question_text, name=self.question_name)]

        if self.question_type == "free_text":
            try:
                q = Question(
                    **{
                        "question_type": self.question_type,
                        "question_text": self.question_text,
                        "question_name": self.question_name,
                    }
                )
                return [q]
            except Exception as e:
                return []

        if self.question_type == "multiple_choice":
            # Let's figure of it it's actually a checkbox question
            if self.selector == "MAVR" or self.selector == "MULTIPLE":
                try:
                    q = Question(
                        **{
                            "question_type": "checkbox",
                            "question_text": self.question_text,
                            "question_name": self.question_name,
                            "question_options": self.choices,
                        }
                    )
                    return [q]
                except Exception as e:
                    return []

            # maybe it's a linear scale!
            if "<br>" in self.choices[0]:
                option_labels = {}
                question_options = []
                for choice in self.choices:
                    if "<br>" in choice:
                        option_label, question_option = choice.split("<br>")
                        option_labels[int(question_option)] = option_label
                        question_options.append(int(question_option))
                    else:
                        question_options.append(int(choice))
                try:
                    q = Question(
                        **{
                            "question_type": "linear_scale",
                            "question_text": self.question_text,
                            "question_name": self.question_name,
                            "question_options": question_options,
                            "option_labels": option_labels,
                        }
                    )
                    return [q]
                except Exception as e:
                    if self.debug:
                        raise e
                    else:
                        print(e)
                        return []

            try:
                q = Question(
                    **{
                        "question_type": self.question_type,
                        "question_text": self.question_text,
                        "question_name": self.question_name,
                        "question_options": self.choices,
                    }
                )
                return [q]
            except Exception as e:
                return []

        if self.question_type == "matrix":
            questions = []
            for index, choice in enumerate(self.choices):
                try:
                    q = Question(
                        **{
                            "question_type": "multiple_choice",
                            "question_text": self.question_text + f" ({choice})",
                            "question_name": self.question_name + f"_{index}",
                            "question_options": self.answers,
                        }
                    )
                    questions.append(q)
                except Exception as e:
                    continue

            return questions

        raise ValueError(f"Invalid question type: {self.question_type}")


class SurveyQualtricsImport:
    def __init__(self, qsf_file_name: str):
        self.qsf_file_name = qsf_file_name
        self.question_data = self.extract_questions_from_json()

    def create_survey(self):
        questions = []
        for qualtrics_questions in self.question_data:
            questions.extend(qualtrics_questions.to_edsl())
        return Survey(questions)

    @property
    def survey_data(self):
        with open(self.qsf_file_name, "r") as f:
            survey_data = json.load(f)
        return survey_data

    def extract_questions_from_json(self):
        questions = self.survey_data["SurveyElements"]

        extracted_questions = []

        for question in questions:
            if question["Element"] == "SQ":
                extracted_questions.append(QualtricsQuestion(question))

        return extracted_questions

    def extract_blocks_from_json(self):
        blocks = []

        for element in self.survey_data["SurveyElements"]:
            if element["Element"] == "BL":
                for block_payload in element["Payload"]:
                    block_elements = [
                        BlockElement(be["Type"], be["QuestionID"])
                        for be in block_payload["BlockElements"]
                    ]
                    options_data = block_payload.get("Options", {})
                    options = BlockOptions(
                        options_data.get("BlockLocking", "false"),
                        options_data.get("RandomizeQuestions", "false"),
                        options_data.get("BlockVisibility", "Collapsed"),
                    )

                    block = SurveyBlock(
                        block_payload["Type"],
                        block_payload["Description"],
                        block_payload["ID"],
                        block_elements,
                        options,
                    )
                    blocks.append(block)

        return blocks


class SurveyBlock:
    def __init__(self, block_type, description, block_id, block_elements, options):
        self.block_type = block_type
        self.description = description
        self.block_id = block_id
        self.block_elements = block_elements
        self.options = options

    def __repr__(self):
        return f"SurveyBlock(type={self.block_type}, description={self.description}, id={self.block_id})"


class BlockElement:
    def __init__(self, element_type, question_id):
        self.element_type = element_type
        self.question_id = question_id

    def __repr__(self):
        return f"BlockElement(type={self.element_type}, question_id={self.question_id})"


class BlockOptions:
    def __init__(self, block_locking, randomize_questions, block_visibility):
        self.block_locking = block_locking
        self.randomize_questions = randomize_questions
        self.block_visibility = block_visibility

    def __repr__(self):
        return (
            f"BlockOptions(block_locking={self.block_locking}, "
            f"randomize_questions={self.randomize_questions}, "
            f"block_visibility={self.block_visibility})"
        )


if __name__ == "__main__":
    survey_creator = SurveyQualtricsImport("example.qsf")
    # print(survey_creator.question_data)
    # survey = survey_creator.create_survey()
    # info = survey.push()
    # print(info)
    # questions = survey.extract_questions_from_json()
    # for question in questions:
    #    print(question)
