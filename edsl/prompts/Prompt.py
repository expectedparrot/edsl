import textwrap
from collections import namedtuple, defaultdict
from abc import ABCMeta, abstractmethod, ABC
from typing import Any, List
from enum import Enum

from jinja2 import Template, Environment, meta


class TemplateRenderError(Exception):
    "TODO: Move to exceptions file"
    pass


NEGATIVE_INFINITY = float("-inf")


class AttributeTypes(Enum):
    COMPONENT_TYPE = "component_type"
    MODEL = "model"
    QUESTION_TYPE = "question_type"


class ComponentTypes(Enum):
    """The types of attributes that a prompt can have"""

    TEST = "test"
    GENERIC = "generic"
    QUESTION_DATA = "question_data"
    QUESTION_INSTRUCTIONS = "question_instructions"
    AGENT_INSTRUCTIONS = "agent_instructions"
    AGENT_DATA = "agent_data"
    SURVEY_INSTRUCTIONS = "survey_instructions"
    SURVEY_DATA = "survey_data"


names_to_component_types = {v.value: v for k, v in ComponentTypes.__members__.items()}

C2A = {
    ComponentTypes.QUESTION_INSTRUCTIONS: [
        AttributeTypes.QUESTION_TYPE,
        AttributeTypes.MODEL,
    ]
}

PromptAttributeDefinition = namedtuple("PromptAttribute", ["name", "required"])


class RegisterPromptsMeta(ABCMeta):
    "Metaclass to register prompts"
    _registry = defaultdict(list)  # Initialize the registry as a dictionary
    _lookup = {}
    _prompts_by_component_type = defaultdict(list)

    def __init__(cls, name, bases, dct):
        """
        We can only have one prompt class per name.
        Each prompt class must have a component type from the ComponentTypes enum.

        >>> class Prompt1(PromptBase):
        ...     component_type = ComponentTypes.TEST

        >>> class Prompt1(PromptBase):
        ...     component_type = ComponentTypes.TEST
        Traceback (most recent call last):
        ...
        Exception: We already have a Prompt class named Prompt1.
        """
        super(RegisterPromptsMeta, cls).__init__(name, bases, dct)
        if "Base" in name or name == "Prompt":
            return None  # We don't want to register the base class

        if name in RegisterPromptsMeta._registry:
            raise Exception(f"We already have a Prompt class named {name}.")

        RegisterPromptsMeta._registry[name] = cls

        if (
            component_type := getattr(cls, "component_type", None)
        ) not in ComponentTypes:
            raise Exception(f"Prompt {name} is not in the list of component types")

        key = cls._create_prompt_class_key(dct, component_type)
        cls.data = key
        RegisterPromptsMeta._prompts_by_component_type[component_type].append(cls)

    @classmethod
    def _create_prompt_class_key(cls, dct, component_type) -> tuple[tuple[str, Any]]:
        attributes = [attribute.value for attribute in C2A.get(component_type, [])]
        cls_data = {key: value for key, value in dct.items() if key in attributes}
        return tuple(cls_data.items())

    @classmethod
    def _get_classes_with_scores(cls, **kwargs) -> List[tuple[float, "PromptBase"]]:
        """
        This how we find matching prompts.
        NB that _get_classes_with_scores returns a list of tuples.
        The first element of the tuple is the score, and the second element is the prompt class.
        There is a public-facing function called get_classes that returns only the prompt classes.

        The kwargs are the attributes that we want to match on. E.g., supposed you
        wanted a prompt with component_type = "question_instructions" and question_type = "multiple_choice".
        You would run:

        >>> get_classes(component_type="question_instructions", question_type="multiple_choice", model="gpt-4-1106-preview")
        [<class '__main__.MultipleChoice'>, <class '__main__.MultipleChoiceTurbo'>]

        In the above example, we have two prompts that match. Note that the order of the prompts is determined by the score and the regular MultipleChoice
        is ranked higher because it matches on the model as well.

        Scores are computed by the _score method. The score is the number of attributes that match, with their weights.
        However, if a required attribute doesn't match, then the score is -inf and it can never be selected.

        The function will throw an exception if you don't specify a component type that's in the ComponentTypes enum.

        >>> get_classes(component_type="chicken_tenders", question_type="multiple_choice")
        Traceback (most recent call last):
        ...
        Exception: You must specify a component type. It must be one of dict_keys([...])

        >>> get_classes(component_type="generic")
        []
        """
        component_type_string = kwargs.get("component_type", None)
        component_type = names_to_component_types.get(component_type_string, None)

        if component_type is None:
            raise Exception(
                f"You must specify a component type. It must be one of {names_to_component_types.keys()}"
            )

        try:
            prompts = cls._prompts_by_component_type[component_type]
        except KeyError:
            raise Exception(f"No prompts for component type {component_type}")

        with_scores = [(cls._score(kwargs, prompt), prompt) for prompt in prompts]
        with_scores = sorted(with_scores, key=lambda x: -x[0])
        # filter out the ones with -inf
        matches_with_scores = cls._filter_out_non_matches(with_scores)
        return matches_with_scores

    @classmethod
    def _filter_out_non_matches(cls, prompts_with_scores):
        return [
            (score, prompt)
            for score, prompt in prompts_with_scores
            if score > NEGATIVE_INFINITY
        ]

    @classmethod
    def get_classes(cls, **kwargs):
        "Public-facing function that returns only the prompt classes and not the scores."
        with_scores = cls._get_classes_with_scores(**kwargs)
        return [prompt for _, prompt in with_scores]

    @classmethod
    def _score(cls, kwargs, prompt):
        required_list = ["question_type"]
        score = 0
        for key, value in kwargs.items():
            if prompt_value := getattr(prompt, key, None) == value:
                score += 1
            else:
                if key in required_list:
                    score += NEGATIVE_INFINITY
        return score

    @classmethod
    def get_registered_classes(cls):
        return cls._registry


get_classes = RegisterPromptsMeta.get_classes


class PromptBase(ABC, metaclass=RegisterPromptsMeta):
    component_type = ComponentTypes.GENERIC

    def __init__(self, text=None):
        if text is None:
            if hasattr(self, "default_instructions"):
                text = self.default_instructions
            else:
                text = ""
        self.text = text

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
    def has_variables(self) -> bool:
        """
        >>> p = Prompt("Hello, {{person}}")
        >>> p.has_variables
        True
        >>> p = Prompt("Hello, person")
        >>> p.has_variables
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
    component_type = ComponentTypes.GENERIC


class AgentInstruction(PromptBase):
    component_type = ComponentTypes.AGENT_INSTRUCTIONS
    default_instructions = textwrap.dedent(
        """\
    You are playing the role of a human answering survey questions.
    Do not break character.
    Your traits are: {{traits}}
    """
    )


class QuestionInstuctionsBase(PromptBase):
    component_type = ComponentTypes.QUESTION_INSTRUCTIONS


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


class MultipleChoiceTurbo(QuestionInstuctionsBase):
    question_type = "multiple_choice"
    model = "gpt-3.5-turbo"
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


if __name__ == "__main__":
    pass

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    # print(RegisterPromptsMeta._prompts_by_component_type)

    relevant_prompts = get_classes(
        component_type="question_instructions", question_type="multiple_choice"
    )
    print(relevant_prompts)

    results = get_classes(
        component_type="question_instructions",
        question_type="multiple_choice",
        model="gpt-4-1106-preview",
    )
    assert results == [MultipleChoice, MultipleChoiceTurbo]

    results = get_classes(
        component_type="question_instructions",
        question_type="multiple_choice",
        model="gpt-3.5-turbo",
    )
    assert results == [MultipleChoiceTurbo, MultipleChoice]

    results = get_classes(
        component_type="agent_instructions", optionflags=doctest.ELLIPSIS
    )
    assert results == [AgentInstruction]
