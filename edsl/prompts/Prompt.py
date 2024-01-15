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


class CheckBox(QuestionInstuctionsBase):
    question_type = "checkbox"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted like this, selecting only the number of the option: 
        {"answer": [<put comma-separated list of answer codes here>], "comment": "<put explanation here>"}
        {% if min_selections != None and max_selections != None and min_selections == max_selections %}
        You must select exactly {{min_selections}} options.
        {% elif min_selections != None and max_selections != None %}
        Minimum number of options that must be selected: {{min_selections}}.      
        Maximum number of options that must be selected: {{max_selections}}.
        {% elif min_selections != None %}
        Minimum number of options that must be selected: {{min_selections}}.      
        {% elif max_selections != None %}
        Maximum number of options that must be selected: {{max_selections}}.      
        {% endif %}        
        """
    )


class TopK(CheckBox):
    question_type = "top_k"


class LinearScale(QuestionInstuctionsBase):
    question_type = "linear_scale"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted like this, selecting only the code of the option (codes start at 0): 
        {"answer": <put answer code here>, "comment": "<put explanation here>"}
        Only 1 option may be selected.
        """
    )


class ListQuestion(QuestionInstuctionsBase):
    question_type = "list"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        {{question_text}}

        Your response should be only a valid JSON of the following format:
        {
            "answer": <list of comma-separated words or phrases >, 
            "comment": "<put comment here>"
        }
        {% if max_list_items is not none %}
        The list must not contain more than {{ max_list_items }} items.
        {% endif %}                                           
    """
    )


class Numerical(QuestionInstuctionsBase):
    question_type = "numerical"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked a question that requires a numerical response 
        in the form of an integer or decimal (e.g., -12, 0, 1, 2, 3.45, ...).
        Your response must be in the following format:
        {"answer": "<your numerical answer here>", "comment": "<your explanation here"}
        You must only include an integer or decimal in the quoted "answer" part of your response. 
        Here is an example of a valid response:
        {"answer": "100", "comment": "This is my explanation..."}
        Here is an example of a response that is invalid because the "answer" includes words:
        {"answer": "I don't know.", "comment": "This is my explanation..."}
        If your response is equivalent to zero, your formatted response should look like this:
        {"answer": "0", "comment": "This is my explanation..."}
        
        You are being asked the following question: {{question_text}}
        {% if min_value is not none %}
        Minimum answer value: {{min_value}}
        {% endif %}
        {% if max_value is not none %}
        Maximum answer value: {{max_value}}
        {% endif %}
        """
    )


class Rank(QuestionInstuctionsBase):
    question_type = "rank"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are being asked the following question: {{question_text}}
        The options are 
        {% for option in question_options %}
        {{ loop.index0 }}: {{option}}
        {% endfor %}                       
        Return a valid JSON formatted like this, selecting the numbers of the options in order of preference, 
        with the most preferred option first, and the least preferred option last: 
        {"answer": [<put comma-separated list of answer codes here>], "comment": "<put explanation here>"}
        Exactly {{num_selections}} options must be selected.
        """
    )


class Extract(QuestionInstuctionsBase):
    question_type = "extract"
    model = "gpt-4-1106-preview"
    default_instructions = textwrap.dedent(
        """\
        You are given the following input: "{{question_text}}".
        Create an ANSWER should be formatted like this: "{{ answer_template }}",
        and it should have the same keys but values extracted from the input.
        If the value of a key is not present in the input, fill with "null".
        Return a valid JSON formatted like this: 
        {"answer": <put your ANSWER here>}
        ONLY RETURN THE JSON, AND NOTHING ELSE.
        """
    )


class Budget(QuestionInstuctionsBase):
    question_type = "budget"
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
