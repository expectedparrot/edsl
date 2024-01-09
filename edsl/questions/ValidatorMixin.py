from edsl.utilities.utilities import is_valid_variable_name
from edsl.questions.settings import Settings


def is_number(value):
    return isinstance(value, int) or isinstance(value, float)


def is_number_or_none(value):
    return value is None or is_number(value)


class ValidatorMixin:
    def validate_question_name(self, value):
        if not is_valid_variable_name(value):
            raise Exception("Question name is not a valid variable name!")
        return value

    def validate_min_value(self, value):
        if not is_number_or_none(value):
            raise Exception("Min value must be a number!")
        return value

    def validate_max_value(self, value):
        if not is_number_or_none(value):
            raise Exception("Max value must be a number!")
        return value

    def validate_instructions(self, value):
        if not isinstance(value, str):
            raise Exception("Instructions must be a string!")
        return value

    def validate_question_text(self, value):
        "Validates the question text"
        if len(value) > 1000:
            raise Exception("Question is too long!")
        if len(value) < 1:
            raise Exception("Question is too short!")
        if not isinstance(value, str):
            raise Exception("Question must be a string!")
        return value

    def validate_question_options(self, value):
        "Validates the question options"
        if not isinstance(value, list):
            raise Exception("Question options must be a list!")
        if len(value) > Settings.MAX_NUM_OPTIONS:
            raise Exception("Question options are too long!")
        if len(value) < Settings.MIN_NUM_OPTIONS:
            raise Exception("Question options are too short!")
        if not all(isinstance(x, str) for x in value):
            raise Exception("Question options must be strings!")
        if len(value) != len(set(value)):
            raise Exception("Question options must be unique!")
        if not all([len(option) > 1 for option in value]):
            raise Exception("All question options must be at least 2 characters long!")
        return value

    def validate_short_names_dict(self, value):
        "Validates the short names dictionary"
        if not isinstance(value, dict):
            raise Exception("Short names dictionary must be a dictionary!")
        if not all(isinstance(x, str) for x in value.keys()):
            raise Exception("Short names dictionary keys must be strings!")
        if not all(isinstance(x, str) for x in value.values()):
            raise Exception("Short names dictionary values must be strings!")
        return value

    def validate_allow_nonresponse(self, value):
        "Validates the non response"
        if not isinstance(value, bool):
            raise Exception("Non response must be a boolean!")
        return value

    def validate_max_list_items(self, value):
        "Validates the max list items"
        if not is_number(value):
            raise Exception("Max list items must be a number!")
        return value
