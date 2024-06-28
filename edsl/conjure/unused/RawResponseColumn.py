from collections import UserDict
from typing import List, Dict, Optional
import textwrap
import re

from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.QuestionFreeText import QuestionFreeText

from edsl.conjure.utilities import convert_value, Missing
from edsl.conjure.ReplacementFinder import ReplacementFinder
from edsl.conjure.DictWithIdentifierKeys import DictWithIdentifierKeys

# get_replacement_name = ReplacementFinder({})


class RawResponseColumn:
    """A class to represent a raw responses from a survey we are parsing.

    If the dataset was square, we would think of this as a column in a dataframe.

    """

    def __init__(
        self,
        question_name: str,
        question_text: str,
        responses: List[str],
    ):
        """
        :param question_name: The name of the question.
        :param question_text: The text of the question.
        :param responses: A list of responses to the question.

        >>> r = RawResponseColumn(question_name="Q1", raw_responses=["1", "2", "3"], answer_codebook={"1": "Yes", "2": "No"}, question_text="Do you like ice cream?")
        >>> r.responses
        ['Yes', 'No', '3']
        >>> r.question_name
        'q1'

        >>> r = RawResponseColumn(question_name="Q1", raw_responses=["1", "2", "3"], answer_codebook={"1": "Yes", "2": "No"}, question_text="Do you like ice cream?")
        >>> r.inferred_question_type
        'multiple_choice'

        """
        self.question_name = question_name
        self.responses = responses
        self.question_text = question_text

    @staticmethod
    def edsl_question_inference(question_text, responses, sample_size=15):
        """Infer the question type from the responses.

        TODO: Not currently used. We should use this to infer the question type.

        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText(question_text="Tell me about your childhood.", question_name = 'color')
        >>> r = RawResponseColumn.edsl_question_inference(q.question_text, ["Rather not say", "Happy!", "luge lessons and meat helmets"])
        >>> r
        'free_text'

        """

    @property
    def responses(self):
        """Returns the responses, with the answer codebook applied."""
        if hasattr(self, "answer_codebook") is None:
            converted_responses = [convert_value(x) for x in self.raw_responses]
            return converted_responses
        else:
            return [self.answer_codebook.get(x, x) for x in self.raw_responses]

    @property
    def inferred_question_type(self):
        "Tries to infer the type of question from the responses and other information"
        max_items = 15
        options = list(self.unique_responses.keys())
        if len(options) > max_items or len(options) <= 1:
            return "free_text"
        else:
            cv = [convert_value(o) for o in options]
            return "multiple_choice"

    def get_ordering(self, options_list):
        """Returns a multiple choice question with the options in the correct order.
        For example, if the options are ["<10", "10-20", "30+", "20-30"], the question would be:
        """
        from edsl.questions.QuestionList import QuestionList

        q = QuestionList(
            question_text=textwrap.dedent(
                """\
            We have a survey question with the following options: '{{options_list}}'.
            The options might be out of order. Please put them in the correct order.
            If there is not natural order, just put then in order they were presented.
            """
            ),
            question_name="ordering",
        )

        proposed_ordering = (
            q.to_survey()(options_list=options_list).select("ordering").first()
        )
        if proposed_ordering is None:
            return options_list

        return proposed_ordering

    def to_question(self) -> QuestionBase:
        """Returns a Question object."""
        d = {}
        d["question_name"] = self.question_name
        d["question_text"] = self.question_text
        d["question_type"] = self.inferred_question_type
        if d["question_type"] == "multiple_choice":
            d["question_options"] = self.get_ordering(list(self.unique_responses))
        return QuestionBase.from_dict(d)

    @property
    def unique_responses(self) -> set:
        """Returns the unique responses for a given question; useful to build up mulitple choice questions.

        >>> r = RawResponseColumn(question_name="Q1", raw_responses=["1", "2", "3"], answer_codebook={"1": "Yes", "2": "No"}, question_text="Do you like ice cream?")
        >>> r.unique_responses
        defaultdict(<class 'int'>, {'Yes': 1, 'No': 1, '3': 1})
        """
        from collections import defaultdict

        s = defaultdict(int)
        for response in self.responses:
            if isinstance(response, Missing):
                continue
            else:
                s[str(response)] += 1
        return s

    def response_category(self):
        """Returns the inferred category of the question."""
        from edsl.questions import QuestionMultipleChoice

        q = QuestionMultipleChoice(
            question_text=textwrap.dedent(
                f"""\
            I have data from a survey. One of the column labels: {self.question_text}. 
            I want to know what the data represents."""
            ),
            question_options=[
                "Something asked of the respondent that interested the survey company",
                "A fixed characteristic of the respondent, like gender or age",
                "Measured by survey company like an internal code or start of the interview",
            ],
            question_name="opinion_or_characteristic",
        )
        result = q.run().select("opinion_or_characteristic").first()
        return result

    def __repr__(self):
        raw_response_display = self.raw_responses[0 : min(len(self.responses), 5)]
        if len(self.responses) > 5:
            raw_response_display.append("...")

        raw_response_display = self.responses[0 : min(len(self.responses), 5)]
        if len(self.responses) > 5:
            raw_response_display.append("...")

        return f"""RawResponseColumn(question_name="{self.question_name}", question_text="{self.question_text}", raw_responses={raw_response_display}, responses={raw_response_display}, unqiue_responses={self.unique_responses}, answer_codebook={self.answer_codebook})"""


if __name__ == "__main__":
    import doctest

    doctest.testmod()
