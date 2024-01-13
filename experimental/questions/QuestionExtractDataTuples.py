import textwrap
from pydantic import BaseModel, Field, field_validator
from typing import Type, Optional, Union
from edsl.questions.Question import Question
from edsl.questions.schemas import QuestionData, AnswerData
from edsl.questions.settings import Settings


class QuestionExtractDataTuples(Question):
    """Extracts a set of specified data types from a list of texts, storing information
    extracted from each text as a tuple, and then returns a list of those tuples."""

    question_type = "extract_data_tuples"

    @property
    def instructions(self):
        return textwrap.dedent(
            """\
        You are being asked to extract certain information from a set of texts.
        {{question_text}}:
        {% for d in data %}
        {{ loop.index0 }}: {{d}}
        {% endfor %} 
        From each text, extract the following information as a new comma-separated list
        with a place for each item in order: 
        {% for e in extract_data %}
        {{e}}
        {% endfor %} 
        If a text is missing any information, put an empty string in its place in the list,
        e.g., ["extracted info 1", "extracted info 2", "", "extracted info 4"]
        Return all of the lists of extracted information in a valid JSON formatted exactly like this: 
        {"answer": [<put your lists here separated by commas>], "comment": "<put explanation here>"}         
        """
        )

    def __repr__(self):
        return f"""{self.__class__.__name__}(question_text = "{self.question_text}", extract_data = "{self.extract_data}", question_name = "{self.question_name}")"""

    @classmethod
    def construct_question_data_model(cls) -> Type[BaseModel]:
        class LocalQuestionData(QuestionData):
            """Pydantic data model for QuestionExtractData"""

            question_text: Optional[str] = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            extract_data: list[str] = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            data: list[str] = Field(
                ..., min_length=1, max_length=Settings.MAX_QUESTION_LENGTH
            )
            allow_nonresponse: bool = None

        return LocalQuestionData

    def translate_answer_code_to_answer(self, answer, scenario=None):
        """There is no answer code."""
        return answer

    def construct_answer_data_model(self) -> Type[BaseModel]:
        class LocalAnswerDataModel(AnswerData):
            answer: list[list[Union[str, int, float]]] = Field(
                ..., min_length=0, max_length=Settings.MAX_ANSWER_LENGTH
            )

            @field_validator("answer")
            def check_answer(cls, value):
                if (
                    hasattr(self, "allow_nonresponse")
                    and self.allow_nonresponse == False
                    and (value == "" or value is None)
                ):
                    raise ValueError("You must provide a response.")
                return value

        return LocalAnswerDataModel

    def simulate_answer(self):
        "Simulates a valid answer for debugging purposes (what the validator expects)"
        raise NotImplementedError

    def form_elements(self):
        raise NotImplementedError

    # def __init__(self, question_text, extract_data, question_name=None):
    #     self.question_text = question_text
    #     self.extract_data = extract_data
    #     self.question_name = question_name

    #     d = {'question_text': question_text,
    #          'exptract_data': extract_data,
    #          'question_name': question_name}

    #     super().__init__(**d)


if __name__ == "__main__":
    from edsl import Agent, Scenario, print_dict_with_rich

    letters = [
        "Dear Ada, I am writing you a letter to tell you something...",
        "Dear Paul, I am writing you a letter to tell you something...",
        "Hi Penelope, I have some updates about my recent trip...",
    ]

    q = QuestionExtractDataTuples(
        question_text="The texts are letters",
        extract_data=[
            "the first initial of the person the letter is addressed to",
            "the name of the person the letter is addressed to",
            "the number of words in the letter",
        ],
        data=letters,
        question_name="letters_names",
    )
    scenarios = [Scenario({"letter": letter}) for letter in letters]
    print(q.get_prompt())
    results = q.by(*scenarios).run()
    print(results)

    # answer = {'answer': ["Ada", "Paul"]} #, 'comment': 'They are names that I found in the letters.'}
    # print(q.validate_answer(answer))
    # print(q.get_prompt())
