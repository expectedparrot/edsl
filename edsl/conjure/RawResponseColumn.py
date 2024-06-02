from collections import UserDict
from typing import List, Dict, Optional
import textwrap
import re

from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.QuestionFreeText import QuestionFreeText

from edsl.conjure.utilities import convert_value, Missing


class KeyValidator:
    """A class to represent a key validator.

    >>> k = KeyValidator()
    >>> k.validate_key("asdf")
    True
    >>> k.validate_key("ASDF")
    False

    """

    def __set_name__(self, owner, name):
        self.name = name

    def validate_key(self, key):
        if not isinstance(key, str):
            # "Key must be a string"
            return False
        if key.lower() != key:
            # "Key must be lowercase"
            return False
        if not key.isidentifier() or not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
            # raise ValueError("Key must be a valid Python identifier")
            return False
        return True


class ReplacementFinder:
    """This class finds a replacement name for a bad question name.

    >>> r = ReplacementFinder(lookup_dict = {'Poop ': 'poop'})
    >>> r('Poop ')
    'poop'

    """

    def __init__(self, lookup_dict: Optional[dict] = None):
        if lookup_dict is None:
            lookup_dict = {}

        self.lookup_dict = lookup_dict

    def __call__(self, bad_question_name):
        """Finds a replacement name for a bad question name.
        TODO: We should add a check to see if the new name is already in use.
        """
        if bad_question_name in self.lookup_dict:
            return self.lookup_dict[bad_question_name]

        q = QuestionFreeText(
            question_text=f"""We have a survey with a question name: {bad_question_name}. 
            The question name is not a valid Python identifier.
            We need a valid Python identifier to use as a column name in a dataframe.
            What would be a better name for this question?
            Shorter is better.
            Just return the proposed identifier with no other text.
            """,
            question_name="identifier",
        )
        new_identifer = q.run().select("identifier").first().lower()
        self.lookup_dict[bad_question_name] = new_identifer
        return new_identifer

    def __repr__(self):
        return f"ReplacementFinder({self.lookup_dict})"

    def to_json(self):
        return self.lookup_dict

    @classmethod
    def from_json(cls, json_dict):
        return cls(json_dict)


get_replacement_name = ReplacementFinder({})


class CustomDict(UserDict):
    """
    This class is a dictionary that only allows lowercase keys that are valid Python identifiers.
    If a key is not a valid Python identifier, it will be replaced with a valid Python identifier.

    >>> d = CustomDict()
    >>> d = CustomDict({"7asdf": 123, "FAMILY": 12})
    >>> d
    {'q7asdf': 123, 'family': 12}
    """

    key_validator = KeyValidator()

    def __init__(self, data=None, verbose=False):
        super().__init__()
        self.verbose = verbose
        if data:
            for key, value in data.items():
                self[key] = value

    def __setitem__(self, key, value):
        if key != key.lower():
            key = key.lower()
        while not self.key_validator.validate_key(key):
            if self.verbose:
                print(f"Column heading incapable of being a key: {key}")
            if key in get_replacement_name.lookup_dict:
                key = get_replacement_name.lookup_dict[key]
            else:
                key = get_replacement_name(key)
            if self.verbose:
                print(f"New key: {key}")
        super().__setitem__(key, value)


class RawResponseColumn:
    """A class to represent a raw responses from a survey we are parsing.

    If the dataset was square, we would think of this as a column in a dataframe.

    """

    def __init__(
        self,
        question_name: str,
        raw_responses: List[str],
        answer_codebook: Dict[str, str],
        question_text: str,
    ):
        """
        :param question_name: The name of the question.
        :param raw_responses: A list of responses to the question.
        :param answer_codebook: A dictionary mapping the raw responses to the actual responses.
        :param question_text: The text of the question.

        >>> r = RawResponseColumn(question_name="Q1", raw_responses=["1", "2", "3"], answer_codebook={"1": "Yes", "2": "No"}, question_text="Do you like ice cream?")
        >>> r.responses
        ['Yes', 'No', '3']
        >>> r.question_name
        'q1'

        >>> r = RawResponseColumn(question_name="Q1", raw_responses=["1", "2", "3"], answer_codebook={"1": "Yes", "2": "No"}, question_text="Do you like ice cream?")
        >>> r.inferred_question_type
        'multiple_choice'

        """
        d = CustomDict(
            {question_name: ""}
        )  # if the question_name is not a valid Python identifier, it will be replaced with a valid Python identifier.
        self.question_name = list(d.keys())[0]
        self.raw_responses = raw_responses
        self.answer_codebook = answer_codebook
        if question_text is None or len(question_text) == 0:
            self.question_text = "Question text not available"
        else:
            self.question_text = question_text

    @staticmethod
    def edsl_question_inference(question_text, responses):
        """Infer the question type from the responses.

        TODO: Not currently used. We should use this to infer the question type.

        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText(question_text="Tell me about your childhood.", question_name = 'color')
        >>> r = RawResponseColumn.edsl_question_inference(q.question_text, ["Rather not say", "Happy!", "luge lessons and meat helmets"])
        >>> r
        'free_text'

        """
        from edsl.questions import QuestionMultipleChoice

        q = QuestionMultipleChoice(
            question_text="""We have a survey question and we are trying to infer its type.
                               The question text is: '{{question_text}}'.                                   
                               The first few responses are: '{{responses}}'.
                                """,
            question_name="infer_question_type",
            question_options=[
                "budget",
                "checkbox",
                "extract",
                "free_text",
                "likert_five",
                "linear_scale",
                "list",
                "multiple_choice",
                "numerical",
                "rank",
                "top_k",
                "yes_no",
            ],
        )
        response = (
            q.to_survey()(question_text=question_text, responses=responses)
            .select("infer_question_type")
            .first()
        )
        return response

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

        return q.to_survey()(options_list=options_list).select("ordering").first()

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
        {'Yes', 'No', '3'}
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
    # d = CustomDict()
    # d = CustomDict({"7asdf": 123, "FAMILY": 12})
    # d["a"] = 123
    # d["#_family_members"] = 4

    # d["FAMILY_MEMBERS"] = 12
    # d["0x1389"] = 123
    # print(d)
    # r = RawResponseColumn(
    #     question_name="_x family MeMbers",
    #     raw_responses=["1", "2", "3"],
    #     question_text="fake",
    #     answer_codebook={},
    # )

    # get_replacement_name
