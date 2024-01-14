import textwrap

from edsl.exceptions import QuestionSerializationError
from edsl.exceptions import QuestionCreationValidationError
from edsl.questions.Question import RegisterQuestionsMeta

# from edsl.questions.QuestionFreeText import QuestionFreeText
# registry = RegisterQuestionsMeta.get_registered_classes()
# q2c = RegisterQuestionsMeta.question_names_to_classes()


class Meta(type):
    def __repr__(cls):
        lines = "\n".join(cls.available())
        return textwrap.dedent(
            f"""\
        Available questions: 
        {lines}        
        """
        )


class QuestionBase(metaclass=Meta):
    def __new__(cls, question_type, *args, **kwargs):
        get_question_classes = RegisterQuestionsMeta.question_types_to_classes()

        subclass = get_question_classes.get(question_type, None)
        if subclass is None:
            raise ValueError(
                f"No question registered with question_type {question_type}"
            )

        # Create an instance of the selected subclass
        instance = object.__new__(subclass)
        instance.__init__(*args, **kwargs)
        return instance

    @classmethod
    def available(cls):
        return list(RegisterQuestionsMeta.question_types_to_classes().keys())


def get_question_class(question_type):
    q2c = RegisterQuestionsMeta.question_types_to_classes()
    if question_type not in q2c:
        raise ValueError(
            f"The question type, {question_type}, is not recognized. Recognied types are: {q2c.keys()}"
        )
    return q2c.get(question_type)


# all question types must be registered here
# the key is the question type
# the value is a tuple of the module name and the class name
# CLASS_REGISTRY = {
#     "budget": ("edsl.questions.QuestionBudget", "QuestionBudget"),
#     "checkbox": ("edsl.questions.QuestionCheckBox", "QuestionCheckBox"),
#     "extract": ("edsl.questions.QuestionExtract", "QuestionExtract"),
#     "free_text": ("edsl.questions.QuestionFreeText", "QuestionFreeText"),
#     "functional": ("edsl.questions.QuestionFunctional", "QuestionFunctional"),
#     "likert_five": ("edsl.questions.derived.QuestionLikertFive", "QuestionLikertFive"),
#     "linear_scale": (
#         "edsl.questions.derived.QuestionLinearScale",
#         "QuestionLinearScale",
#     ),
#     "list": ("edsl.questions.QuestionList", "QuestionList"),
#     "multiple_choice": (
#         "edsl.questions.QuestionMultipleChoice",
#         "QuestionMultipleChoice",
#     ),
#     "numerical": ("edsl.questions.QuestionNumerical", "QuestionNumerical"),
#     "rank": ("edsl.questions.QuestionRank", "QuestionRank"),
#     "top_k": ("edsl.questions.derived.QuestionTopK", "QuestionTopK"),
#     "yes_no": ("edsl.questions.derived.QuestionYesNo", "QuestionYesNo"),
# }

question_purpose = {
    "multiple_choice": "When options are known and limited",
    "free_text": "When options are unknown or unlimited",
    "checkbox": "When multiple options can be selected",
    "numerical": "When the answer is a single numerical value e.g., a float",
    "linear_scale": "When options are text, but can be ordered e.g., daily, weekly, monthly, etc.",
    "yes_no": "When the question can be fully answered with either a yes or a no",
}


if __name__ == "__main__":
    print(QuestionBase.available())

    q = QuestionBase(
        "free_text", question_text="How are you doing?", question_name="test"
    )
    results = q.run()
