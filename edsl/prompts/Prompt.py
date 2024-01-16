import textwrap
from abc import ABCMeta, abstractmethod, ABC
from collections import defaultdict

from typing import Any

from jinja2 import Template, Environment, meta


class TemplateRenderError(Exception):
    "TODO: Move to exceptions file"
    pass


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
        """
        >>> class Prompt1(PromptBase):
        ...     component_type = "test"

        >>> class Prompt1(PromptBase):
        ...     component_type = "test"
        Traceback (most recent call last):
        ...
        Exception: We already have a Prompt class named Prompt1
        """
        super(RegisterPromptsMeta, cls).__init__(name, bases, dct)
        if "Base" not in name and name != "Prompt":
            if name in RegisterPromptsMeta._registry:
                raise Exception(f"We already have a Prompt class named {name}")
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
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p2 = Prompt("How are you?")
        >>> p + p2
        Prompt(text='Hello, {{person}}How are you?')
        >>> p + "How are you?"
        Prompt(text='Hello, {{person}}How are you?')
        """
        if isinstance(other_prompt, str):
            return self.__class__(self.text + other_prompt)
        else:
            return self.__class__(text=self.text + other_prompt.text)

    def __str__(self):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> str(p)
        'Hello, {{person}}'
        """
        return self.text

    def __contains__(self, text_to_check):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> "person" in p
        True
        >>> "person2" in p
        False
        """
        return text_to_check in self.text

    def __repr__(self):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p
        Prompt(text='Hello, {{person}}')
        """
        return f"Prompt(text='{self.text}')"

    def template_variables(
        self,
    ) -> list[str]:
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p.template_variables()
        ['person']
        """
        return self._template_variables(self.text)

    @staticmethod
    def _template_variables(template: str) -> list[str]:
        """ """
        env = Environment()
        ast = env.parse(template)
        return list(meta.find_undeclared_variables(ast))

    @property
    def is_template(self) -> bool:
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p.is_template
        True
        >>> p = Prompt("Hello, person")
        >>> p.is_template
        False
        """
        return len(self.template_variables()) > 0

    def render(self, replacements, max_nesting=100) -> None:
        """Renders the prompt with the replacements

        >>> p = Prompt("Hello, {{person}}")
        >>> p.render({"person": "John"})
        >>> p.text
        'Hello, John'
        >>> p = Prompt("Hello, {{person}}")
        >>> p.render({"person": "Mr. {{last_name}}", "last_name": "Horton"})
        >>> p.text
        'Hello, Mr. Horton'
        >>> p.render({"person": "Mr. {{last_name}}", "last_name": "Ho{{letter}}ton"}, max_nesting = 1)
        >>> p.text
        'Hello, Mr. Horton'
        """
        self.text = self._render(self.text, replacements, max_nesting)

    @staticmethod
    def _render(text, replacements: dict[str, Any], max_nesting) -> str:
        """
        Replaces the variables in the question text with the values from the scenario.
        We allow nesting, and hence we may need to do this many times. There is a nesting limit of 100.
        TODO: I'm not sure this is necessary, actually - I think jinja2 does this for us automatically.
        When I was trying to get it to fail, I couldn't.
        """
        for _ in range(max_nesting):
            t = Template(text).render(replacements)
            if t == text:
                return t
            text = t
        raise TemplateRenderError(
            "Too much nesting - you created an infnite loop here, pal"
        )

    def to_dict(self):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p.to_dict()
        {'text': 'Hello, {{person}}', 'class_name': 'Prompt'}
        """
        return {"text": self.text, "class_name": self.__class__.__name__}

    @classmethod
    def from_dict(cls, data):
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p2 = Prompt.from_dict(p.to_dict())
        >>> p2
        Prompt(text='Hello, {{person}}')
        """
        class_name = data["class_name"]
        cls = RegisterPromptsMeta._registry.get(class_name, Prompt)
        return cls(text=data["text"])


class Prompt(PromptBase):
    component_type = ""


class AgentInstruction(PromptBase):
    component_type = "agent_instructions"
    default_instructions = textwrap.dedent(
        """\
    You are playing the role of a human answering survey questions.
    Do not break character.
    Your traits are: {{traits}}
    """
    )


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
    pass
    # q = QuestionInstuctions()
    # d = RegisterPromptsMeta._lookup
    # print(d)
    # get_classes(component_type="question_instructions")
    # import doctest
    # doctest.testmod()

    # template = "This is the template {{person}}"
    # env = Environment()
    # ast = env.parse(Template(template))
    # print(meta.find_undeclared_variables(ast))

    # template = "This is the template {{person}}"
    # env = Environment()
    # ast = env.parse(template)
    # print(meta.find_undeclared_variables(ast))

    # Traceback (most recent call last):
    # ...
    # TemplateRenderError: Too much nesting - you created an infnite loop here, pal
