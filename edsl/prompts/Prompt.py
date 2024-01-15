import textwrap
from abc import ABCMeta, abstractmethod, ABC
from collections import defaultdict


class RegisterPromptsMeta(ABCMeta):
    "Metaclass to register prompts"
    _registry = defaultdict(list)  # Initialize the registry as a dictionary
    _lookup = {}

    component_types = {
        "question_data": [],
        "question_instructions": ["question_type", "model"],
        "agent_instructions": [],
        "agent_data": [],
        "survey_instructions": [],
        "survey_data": [],
    }

    def __init__(cls, name, bases, dct):
        super(RegisterPromptsMeta, cls).__init__(name, bases, dct)
        if "Base" not in name and name != "Prompt":
            RegisterPromptsMeta._registry[name] = cls
            attributes = tuple(
                ["component_type"]
                + RegisterPromptsMeta.component_types.get(cls.component_type, [])
            )
            values = tuple([getattr(cls, attr) for attr in attributes])
            cls._lookup[tuple(zip(attributes, values))] = cls

    @staticmethod
    def match(new_pairs, existing_pairs):
        "Checks if the new key matches the existing key"
        for new_key, new_value in new_pairs.items():
            if new_key in existing_pairs:
                if new_value != existing_pairs[new_key]:
                    return False
        return True

    @staticmethod
    def tuple_key_to_dict(pairs):
        return {key: value for key, value in pairs}

    @classmethod
    def get_classes(cls, **kwargs):
        d = cls._lookup
        values = []
        for key, value in d.items():
            if cls.match(kwargs, cls.tuple_key_to_dict(key)):
                values.append(value)
        return values

    @classmethod
    def get_registered_classes(cls):
        return cls._registry


class PromptBase(ABC, metaclass=RegisterPromptsMeta):
    def __init__(self, text=None):
        self.text = text or ""

    def __add__(self, other_prompt):
        if isinstance(other_prompt, str):
            return self.text + other_prompt
        else:
            return self.__class__(text=self.text + other_prompt.text)

    def __str__(self):
        return self.text

    def __contains__(self, text_to_check):
        return text_to_check in self.text

    def __repr__(self):
        return f"Prompt(text='{self.text}')"


class Prompt(PromptBase):
    component_type = "agent_instructions"


class QuestionInstuctionsBase(PromptBase):
    component_type = "question_instructions"

    def __init__(self, text=None):
        if text is None:
            text = self.default_instructions
        super().__init__(text=text)


class MultipleChoice(QuestionInstuctionsBase):
    question_type = "multiple_choice"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}
        Return a valid JSON formatted like this, selecting only the number of the option:
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.
        """
    )


# For now
class LikertFive(MultipleChoice):
    question_type = "likert_five"


class YesNo(MultipleChoice):
    question_type = "yes_no"


class FreeText(QuestionInstuctionsBase):
    question_type = "free_text"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        Return a valid JSON formatted like this: 
        {"answer": "<put free text answer here>"}
        """
    )


get_classes = RegisterPromptsMeta.get_classes


if __name__ == "__main__":
    # q = QuestionInstuctions()
    d = RegisterPromptsMeta._lookup
    print(d)
    get_classes(component_type="question_instructions")
