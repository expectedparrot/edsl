from edsl.exceptions import QuestionSerializationError

# all question types must be registered here
# the key is the question type
# the value is a tuple of the module name and the class name
CLASS_REGISTRY = {
    "budget": ("edsl.questions.QuestionBudget", "QuestionBudget"),
    "checkbox": ("edsl.questions.QuestionCheckBox", "QuestionCheckBox"),
    "extract": ("edsl.questions.QuestionExtract", "QuestionExtract"),
    "free_text": ("edsl.questions.QuestionFreeText", "QuestionFreeText"),
    "functional": ("edsl.questions.QuestionFunctional", "QuestionFunctional"),
    "likert_five": ("edsl.questions.derived.QuestionLikertFive", "QuestionLikertFive"),
    "linear_scale": (
        "edsl.questions.derived.QuestionLinearScale",
        "QuestionLinearScale",
    ),
    "list": ("edsl.questions.QuestionList", "QuestionList"),
    "multiple_choice": (
        "edsl.questions.QuestionMultipleChoice",
        "QuestionMultipleChoice",
    ),
    "numerical": ("edsl.questions.QuestionNumerical", "QuestionNumerical"),
    "rank": ("edsl.questions.QuestionRank", "QuestionRank"),
    "top_k": ("edsl.questions.derived.QuestionTopK", "QuestionTopK"),
    "yes_no": ("edsl.questions.derived.QuestionYesNo", "QuestionYesNo"),
}

question_purpose = {
    "multiple_choice": "When options are known and limited",
    "free_text": "When options are unknown or unlimited",
    "checkbox": "When multiple options can be selected",
    "numerical": "When the answer is a single numerical value e.g., a float",
    "linear_scale": "When options are text, but can be ordered e.g., daily, weekly, monthly, etc.",
    "yes_no": "When the question can be fully answered with either a yes or a no",
}


def get_question_class(question_type: str) -> type:
    """Get the question class for a given question type."""
    if question_type not in CLASS_REGISTRY:
        raise QuestionSerializationError(
            f"No question class registered for type: {question_type}, causing `from_dict` to fail."
        )
    module_name, class_name = CLASS_REGISTRY[question_type]
    question_module = __import__(module_name, globals(), locals(), [class_name], 0)
    return getattr(question_module, class_name)
